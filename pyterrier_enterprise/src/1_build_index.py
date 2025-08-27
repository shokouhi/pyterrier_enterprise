import pyterrier as pt
from pathlib import Path
from src.config import settings
from src.extract import iter_docs

def main():
    doc_root = Path(settings.doc_dir)
    wiki_root = Path(settings.wiki_dir)
    index_root = Path(settings.index_dir)

    if not doc_root.exists():
        raise SystemExit(f"Missing DOC_DIR: {doc_root}")
    if not wiki_root.exists():
        raise SystemExit(f"Missing WIKI_DIR: {wiki_root}")

    index_root.mkdir(parents=True, exist_ok=True)

    # Heap tune; explicit init to avoid deprecation warning
    pt.java.set_memory_limit(2048)
    pt.java.init()

    def _gen():
        yield from iter_docs(doc_root, settings.max_bytes_per_file)
        yield from iter_docs(wiki_root, settings.max_bytes_per_file)

    indexer = pt.IterDictIndexer(
        str(index_root),
        fields=["text", "title"],          # <-- TEXT fields for BM25
        meta={
            "docno": 2048,
            "path": 2048,
            "title": 1024,
            "content": 4096,               # optional: store full content for API
            "content_type": 256,
            "modified": 64,
        },
        blocks=False
    )

    print(f"Indexing into: {index_root}")
    indexref = indexer.index(_gen())
    print("Index complete.")
    print("IndexRef:", indexref)

if __name__ == "__main__":
    main()
