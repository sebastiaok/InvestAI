from __future__ import annotations

import argparse

from app.rag.vector_store import build_vector_store


def main():
    parser = argparse.ArgumentParser(description="Build FAISS index from research documents.")
    parser.add_argument("--input", default="./data/research", help="Input directory for research docs")
    parser.add_argument("--store", default="./data/vector_store/faiss", help="Output path for FAISS index")
    args = parser.parse_args()

    build_vector_store(input_dir=args.input, store_dir=args.store)
    print(f"Index built successfully: input={args.input} store={args.store}")


if __name__ == "__main__":
    main()
