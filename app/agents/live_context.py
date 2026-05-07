from __future__ import annotations

import json
from typing import Any, Dict, List, Set, Tuple


def citations_from_live_payload(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    if not isinstance(payload, dict):
        return []
    items: List[Dict[str, str]] = []
    source = payload.get("source") or ""
    if not source:
        return []
    url = str(payload.get("url", "") or "")
    title = str(payload.get("ticker") or payload.get("title") or "")
    items.append({"source": str(source), "url": url, "title": title})
    nested = payload.get("items") or []
    if isinstance(nested, list):
        for entry in nested[:3]:
            if isinstance(entry, dict) and entry.get("url"):
                items.append(
                    {
                        "source": str(source),
                        "url": str(entry.get("url", "")),
                        "title": str(entry.get("title", "")),
                    }
                )
    return items


def merge_agent_citations(*lists: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen: Set[Tuple[str, str, str]] = set()
    merged: List[Dict[str, str]] = []
    for lst in lists:
        for row in lst:
            key = (row.get("url", ""), row.get("source", ""), row.get("title", ""))
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)
    return merged


def live_data_fallback_banner(*payloads: Dict[str, Any]) -> str:
    names = []
    for p in payloads:
        if isinstance(p, dict):
            src = str(p.get("source", "") or "")
            if "mock" in src.lower() or src.endswith("_fallback"):
                names.append(src)
    if not names:
        return ""
    return (
        "주의: 아래 데이터 중 일부는 실시간 조회 실패로 폴백된 값입니다. "
        + f"(출처 플래그: {', '.join(names)})"
    )


def format_live_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return json.dumps({}, ensure_ascii=False)
