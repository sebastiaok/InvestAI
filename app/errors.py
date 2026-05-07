from __future__ import annotations


class AppHTTPError(Exception):
    """표준 에러 코드·HTTP 상태를 동반하는 애플리케이션 예외 베이스."""

    http_status = 500
    error_code = "INTERNAL_ERROR"

    def __init__(self, message: str, *, detail: str | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail


class InputValidationAppError(AppHTTPError):
    """요청 본문/도메인 규칙 위반."""

    http_status = 422
    error_code = "INPUT_VALIDATION_ERROR"


class LLMInvocationError(AppHTTPError):
    """LLM 제공자 호출 실패(네트워크, 인증, 할당량, 권한 등)."""

    def __init__(
        self,
        message: str,
        *,
        subtype: str = "unknown",
        detail: str | None = None,
        original_type: str | None = None,
    ):
        super().__init__(message, detail=detail)
        self.subtype = subtype
        self.original_type = original_type

    http_status = 502
    error_code = "LLM_INVOCATION_FAILED"


class LLMJSONParseError(AppHTTPError):
    """LLM 응답 JSON 파싱 실패 또는 tool arguments JSON 불가."""

    http_status = 422
    error_code = "LLM_JSON_PARSE_ERROR"

    def __init__(self, message: str, *, snippet: str | None = None, stage: str | None = None):
        super().__init__(message)
        self.snippet = snippet
        self.stage = stage
