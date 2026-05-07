from __future__ import annotations

import json

from app.config import OPENAI_EMBED_MODEL, OPENAI_ENDPOINT, OPENAI_MODEL
from app.services.llm import client


def main():
    print("endpoint:", OPENAI_ENDPOINT.strip())
    print("chat_model:", OPENAI_MODEL)
    print("embed_model:", OPENAI_EMBED_MODEL)

    result = {"chat": None, "embedding": None}

    try:
        chat_resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": "ping"}],
            temperature=0,
            max_tokens=8,
        )
        result["chat"] = {
            "ok": True,
            "content": (chat_resp.choices[0].message.content or "").strip(),
        }
    except Exception as exc:
        result["chat"] = {"ok": False, "error_type": exc.__class__.__name__, "error": str(exc)}

    try:
        emb_resp = client.embeddings.create(
            model=OPENAI_EMBED_MODEL,
            input=["ping embedding"],
        )
        result["embedding"] = {
            "ok": True,
            "dim": len(emb_resp.data[0].embedding),
        }
    except Exception as exc:
        result["embedding"] = {"ok": False, "error_type": exc.__class__.__name__, "error": str(exc)}

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
