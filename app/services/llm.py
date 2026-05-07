from __future__ import annotations

import json
import re
from typing import Any, Dict, List

import httpx
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from openai import APIConnectionError, APIError, APITimeoutError, AuthenticationError, AzureOpenAI, OpenAI, PermissionDeniedError, RateLimitError

from app.config import OPENAI_API_KEY, OPENAI_API_VERSION, OPENAI_ENDPOINT, OPENAI_MODEL
from app.errors import LLMInvocationError, LLMJSONParseError

if OPENAI_ENDPOINT:
    client = AzureOpenAI(
        api_key=OPENAI_API_KEY,
        azure_endpoint=OPENAI_ENDPOINT.strip(),
        api_version=OPENAI_API_VERSION,
        http_client=httpx.Client(trust_env=False),
    )
else:
    client = OpenAI(api_key=OPENAI_API_KEY, http_client=httpx.Client(trust_env=False))


def _wrap_llm_exception(exc: Exception) -> LLMInvocationError:
    if isinstance(exc, LLMInvocationError):
        return exc
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return LLMInvocationError(str(exc), subtype="connection", original_type=type(exc).__name__)
    if isinstance(exc, AuthenticationError):
        return LLMInvocationError(str(exc), subtype="authentication", original_type=type(exc).__name__)
    if isinstance(exc, PermissionDeniedError):
        return LLMInvocationError(str(exc), subtype="permission_denied", original_type=type(exc).__name__)
    if isinstance(exc, RateLimitError):
        return LLMInvocationError(str(exc), subtype="rate_limit", original_type=type(exc).__name__)
    if isinstance(exc, APIError):
        return LLMInvocationError(str(exc), subtype="api_error", original_type=type(exc).__name__)
    return LLMInvocationError(str(exc), subtype="unknown", original_type=type(exc).__name__)


def _to_openai_messages(langchain_messages: List[Any]) -> List[Dict[str, str]]:
    role_map = {"human": "user", "ai": "assistant", "system": "system"}
    payload: List[Dict[str, str]] = []
    for message in langchain_messages:
        role = role_map.get(getattr(message, "type", "human"), "user")
        payload.append({"role": role, "content": str(message.content)})
    return payload


def _invoke_chat_completion(prompt_value: Any, temperature: float = 0.2, json_mode: bool = False) -> str:
    messages = _to_openai_messages(prompt_value.to_messages())
    params: Dict[str, Any] = {
        "model": OPENAI_MODEL,
        "temperature": temperature,
        "messages": messages,
    }
    if json_mode:
        params["response_format"] = {"type": "json_object"}
    try:
        response = client.chat.completions.create(**params)
        return response.choices[0].message.content or ""
    except Exception as exc:
        raise _wrap_llm_exception(exc) from exc


def run_prompt_chain(system_prompt: str, user_template: str, variables: Dict[str, Any], temperature: float = 0.2) -> str:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", user_template),
        ]
    )
    chain = prompt | RunnableLambda(lambda pv: _invoke_chat_completion(pv, temperature=temperature)) | StrOutputParser()
    return chain.invoke(variables)


def run_prompt_chain_json(system_prompt: str, user_template: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", user_template),
        ]
    )
    chain = prompt | RunnableLambda(lambda pv: _invoke_chat_completion(pv, temperature=0.1, json_mode=True))
    content = chain.invoke(variables)
    try:
        return json.loads(content or "{}")
    except json.JSONDecodeError as exc:
        raise LLMJSONParseError(
            "LLM 응답을 JSON으로 파싱하지 못했습니다.",
            snippet=(content or "")[:800],
            stage="json_chat_response",
        ) from exc


def chat(system_prompt: str, user_prompt: str) -> str:
    return run_prompt_chain(
        system_prompt=system_prompt,
        user_template="{user_prompt}",
        variables={"user_prompt": user_prompt},
        temperature=0.2,
    )


def json_chat(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    return run_prompt_chain_json(
        system_prompt=system_prompt,
        user_template="{user_prompt}",
        variables={"user_prompt": user_prompt},
    )


def parse_json_object_from_assistant_text(text: str) -> Dict[str, Any]:
    """도구 사용 후 모델이 마크다운 코드펜스나 전후 설명과 함께 JSON을 내보낸 경우 파싱한다."""
    s = (text or "").strip()
    if not s:
        raise ValueError("empty assistant text")
    if s.startswith("```"):
        body = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
        body = re.sub(r"\s*```\s*$", "", body)
        s = body.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end > start:
        return json.loads(s[start : end + 1])
    raise ValueError("assistant text did not contain a parseable JSON object")


def chat_with_tools(
    system_prompt: str, user_prompt: str, tools: list[BaseTool], max_steps: int = 3
) -> Dict[str, Any]:
    openai_tools = [convert_to_openai_tool(tool) for tool in tools]
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    tool_traces: list[dict[str, Any]] = []

    for _ in range(max_steps):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0.2,
                messages=messages,
                tools=openai_tools,
                tool_choice="auto",
            )
        except Exception as exc:
            raise _wrap_llm_exception(exc) from exc
        message = response.choices[0].message
        content = message.content or ""
        tool_calls = message.tool_calls or []
        if not tool_calls:
            return {"answer": content, "tool_traces": tool_traces}

        messages.append(
            {
                "role": "assistant",
                "content": content,
                "tool_calls": [tc.model_dump() for tc in tool_calls],
            }
        )

        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            raw_args = tool_call.function.arguments or "{}"
            try:
                arguments = json.loads(raw_args)
            except json.JSONDecodeError as exc:
                raise LLMJSONParseError(
                    "도구 호출 인자 JSON 파싱에 실패했습니다.",
                    snippet=raw_args[:800],
                    stage="tool_arguments",
                ) from exc
            selected = next((tool for tool in tools if tool.name == tool_name), None)
            if selected is None:
                result: Any = {"error": f"Unknown tool {tool_name}"}
            else:
                result = selected.invoke(arguments)
            result_text = json.dumps(result, ensure_ascii=False)
            tool_traces.append({"tool": tool_name, "result": result})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": result_text,
                }
            )

    return {"answer": "", "tool_traces": tool_traces}
