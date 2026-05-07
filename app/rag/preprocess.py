from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader


def clean_text(text: str) -> str:
    cleaned = text.replace("\x00", " ")
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def detect_doc_type(path: Path) -> str:
    lower_name = path.name.lower()
    if "report" in lower_name:
        return "report"
    if "news" in lower_name:
        return "news_snapshot"
    return "research_note"


def detect_ticker(path: Path) -> str:
    # simple heuristic: UPPER token like AAPL or 005930.KS in file name
    match = re.search(r"\b([A-Z]{1,6}(?:\.[A-Z]{1,3})?)\b", path.stem)
    if match:
        return match.group(1)
    return "UNKNOWN"


def hash_chunk(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def load_text_documents(input_dir: str) -> list[Document]:
    root = Path(input_dir)
    docs: list[Document] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".txt", ".md", ".pdf"}:
            continue
        if path.suffix.lower() == ".pdf":
            try:
                reader = PdfReader(str(path))
                raw = "\n".join((page.extract_text() or "") for page in reader.pages)
            except Exception:
                continue
        else:
            raw = path.read_text(encoding="utf-8", errors="ignore")
        cleaned = clean_text(raw)
        if len(cleaned) < 60:
            continue
        docs.append(
            Document(
                page_content=cleaned,
                metadata={
                    "source_id": path.stem,
                    "source_path": str(path),
                    "doc_type": detect_doc_type(path),
                    "ticker": detect_ticker(path),
                    "section": "body",
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        )
    return docs


def chunk_documents(documents: Iterable[Document], chunk_size: int = 900, chunk_overlap: int = 120) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_documents(list(documents))
    for index, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = index
        chunk.metadata["hash"] = hash_chunk(chunk.page_content)
    return chunks
