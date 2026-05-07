from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from app.rag.preprocess import chunk_documents, clean_text, hash_chunk
from app.rag.vector_store import build_vector_store


def prepare_documents_from_inputs(inputs: list[dict[str, Any]]) -> tuple[list[Document], list[str]]:
    documents: list[Document] = []
    warnings: list[str] = []

    for item in inputs:
        filename = (item.get("filename") or "unknown.txt").strip()
        content = item.get("content") or ""
        cleaned = clean_text(content)
        if len(cleaned) < 60:
            warnings.append(f"Skipped short content: {filename}")
            continue

        source_id = Path(filename).stem
        documents.append(
            Document(
                page_content=cleaned,
                metadata={
                    "source_id": source_id,
                    "source_path": f"./data/research/{filename}",
                    "doc_type": item.get("doc_type") or "research_note",
                    "ticker": item.get("ticker") or "UNKNOWN",
                    "section": item.get("section") or "body",
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        )
    return documents, warnings


def save_raw_documents(inputs: list[dict[str, Any]], research_dir: str = "./data/research") -> list[str]:
    root = Path(research_dir)
    root.mkdir(parents=True, exist_ok=True)
    saved_paths: list[str] = []
    for item in inputs:
        filename = (item.get("filename") or "").strip()
        content = item.get("content") or ""
        if not filename or not content:
            continue
        safe_name = filename.replace("/", "_")
        if not (safe_name.endswith(".txt") or safe_name.endswith(".md")):
            safe_name += ".md"
        path = root / safe_name
        path.write_text(content, encoding="utf-8")
        saved_paths.append(str(path))
    return saved_paths


def build_chunk_previews(chunks: list[Document], limit: int = 20) -> list[dict[str, Any]]:
    previews: list[dict[str, Any]] = []
    for chunk in chunks[:limit]:
        previews.append(
            {
                "source_id": chunk.metadata.get("source_id", "unknown"),
                "ticker": chunk.metadata.get("ticker", "UNKNOWN"),
                "doc_type": chunk.metadata.get("doc_type", "research_note"),
                "chunk_index": int(chunk.metadata.get("chunk_index", 0)),
                "hash": chunk.metadata.get("hash", hash_chunk(chunk.page_content)),
                "text_preview": chunk.page_content[:180],
            }
        )
    return previews


def ingest_documents(
    inputs: list[dict[str, Any]],
    chunk_size: int = 900,
    chunk_overlap: int = 120,
    save_to_research_dir: bool = True,
    rebuild_index: bool = True,
) -> dict[str, Any]:
    documents, warnings = prepare_documents_from_inputs(inputs)
    chunks = chunk_documents(documents, chunk_size=chunk_size, chunk_overlap=chunk_overlap) if documents else []

    saved_files: list[str] = []
    if save_to_research_dir:
        saved_files = save_raw_documents(inputs)

    if rebuild_index and save_to_research_dir:
        try:
            build_vector_store(input_dir="./data/research", store_dir="./data/vector_store/faiss")
        except Exception as exc:
            warnings.append(f"Index build failed: {exc.__class__.__name__}")

    return {
        "input_documents": len(inputs),
        "accepted_documents": len(documents),
        "generated_chunks": len(chunks),
        "saved_files": saved_files,
        "chunk_previews": build_chunk_previews(chunks),
        "warnings": warnings,
    }
