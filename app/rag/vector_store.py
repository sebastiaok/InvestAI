from __future__ import annotations

from pathlib import Path

from langchain_community.vectorstores import FAISS

from app.rag.embeddings_factory import build_embeddings
from app.rag.preprocess import chunk_documents, load_text_documents


DEFAULT_RESEARCH_DIR = "./data/research"
DEFAULT_VECTOR_STORE_DIR = "./data/vector_store/faiss"


def build_vector_store(input_dir: str = DEFAULT_RESEARCH_DIR, store_dir: str = DEFAULT_VECTOR_STORE_DIR) -> FAISS:
    documents = load_text_documents(input_dir)
    if not documents:
        raise ValueError(f"No research documents found in {input_dir}")
    chunks = chunk_documents(documents)
    embeddings = build_embeddings()
    store = FAISS.from_documents(chunks, embeddings)
    Path(store_dir).mkdir(parents=True, exist_ok=True)
    store.save_local(store_dir)
    return store


def load_vector_store(store_dir: str = DEFAULT_VECTOR_STORE_DIR) -> FAISS:
    embeddings = build_embeddings()
    return FAISS.load_local(store_dir, embeddings, allow_dangerous_deserialization=True)


def build_or_load_vector_store(
    input_dir: str = DEFAULT_RESEARCH_DIR, store_dir: str = DEFAULT_VECTOR_STORE_DIR
) -> FAISS:
    path = Path(store_dir)
    if path.exists():
        return load_vector_store(store_dir=store_dir)
    return build_vector_store(input_dir=input_dir, store_dir=store_dir)
