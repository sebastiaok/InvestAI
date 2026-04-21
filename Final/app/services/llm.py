from __future__ import annotations

import json
from typing import Any, Dict

import httpx
from openai import AzureOpenAI, OpenAI

from app.config import OPENAI_API_KEY, OPENAI_API_VERSION, OPENAI_ENDPOINT, OPENAI_MODEL

if OPENAI_ENDPOINT:
    client = AzureOpenAI(
        api_key=OPENAI_API_KEY,
        azure_endpoint=OPENAI_ENDPOINT,
        api_version=OPENAI_API_VERSION,
        http_client=httpx.Client(trust_env=False),
    )
else:
    client = OpenAI(api_key=OPENAI_API_KEY, http_client=httpx.Client(trust_env=False))


def chat(system_prompt: str, user_prompt: str) -> str:
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content or ""


def json_chat(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)
