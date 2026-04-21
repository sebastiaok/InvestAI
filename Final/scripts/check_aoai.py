from __future__ import annotations

import os
import sys

import httpx
from dotenv import load_dotenv
from openai import AzureOpenAI


def main() -> int:
    load_dotenv()

    endpoint = os.getenv("AOAI_ENDPOINT", "").strip()
    api_key = os.getenv("AOAI_API_KEY", "").strip()
    deployment = os.getenv("AOAI_DEPLOY_GPT4O_MINI", "").strip()
    api_version = os.getenv("AOAI_API_VERSION", "2024-02-15-preview").strip()

    missing = [
        name
        for name, value in [
            ("AOAI_ENDPOINT", endpoint),
            ("AOAI_API_KEY", api_key),
            ("AOAI_DEPLOY_GPT4O_MINI", deployment),
        ]
        if not value
    ]
    if missing:
        print(f"[FAIL] Missing env vars: {', '.join(missing)}")
        return 1

    try:
        client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
            http_client=httpx.Client(trust_env=False, timeout=20.0),
        )
        response = client.chat.completions.create(
            model=deployment,
            messages=[{"role": "user", "content": "reply with: pong"}],
            temperature=0,
            max_tokens=5,
        )
        content = (response.choices[0].message.content or "").strip()
        print("[OK] Azure OpenAI reachable")
        print(f"[INFO] Deployment: {deployment}")
        print(f"[INFO] Response: {content}")
        return 0
    except Exception as exc:
        print("[FAIL] Azure OpenAI connectivity check failed")
        print(f"[ERROR] {exc.__class__.__name__}: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
