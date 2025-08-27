from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from pathlib import Path
import pyterrier as pt

from src.config import settings

app = FastAPI(title="PyTerrier BM25 API", version="1.0.0")

# CORS
allow_origins = settings.cors_allow_origins or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy init
_pt_ready = False
_index = None
_br = None

def ensure_pyterrier():
    global _pt_ready, _index, _br
    if _pt_ready:
        return
    # Heap + init
    pt.java.set_memory_limit(2048)
    pt.java.init()

    # Open index
    index_path = Path(settings.index_dir)
    if not index_path.exists():
        raise RuntimeError(f"Index not found at {index_path}. Run `python -m src.build_index` first.")
    _index = pt.IndexFactory.of(str(index_path))
    _br = pt.BatchRetrieve(_index, wmodel="BM25")
    _pt_ready = True

@app.get("/health")
def health():
    return {
        "ok": True,
        "index_dir": settings.index_dir,
        "index_exists": Path(settings.index_dir).exists()
    }

@app.get("/search")
def search(
    q: str = Query(..., description="Query string"),
    top: int = Query(10, ge=1, le=100),
    fields: Optional[str] = Query("title,content", description="Comma-separated fields to return")
):
    ensure_pyterrier()

    import pandas as pd
    qdf = pd.DataFrame([{"qid": "1", "query": q}])
    res = _br.transform(qdf).sort_values(["qid", "rank"]).head(top)

    # Pull stored metadata from the index
    meta = _index.getMetaIndex()
    requested = [f.strip() for f in (fields or "").split(",") if f.strip()]
    allowed = {"title", "content", "path", "content_type", "modified"}
    requested = [f for f in requested if f in allowed]

    out = []
    for _, row in res.iterrows():
        docid = int(row["docid"])
        item = {
            "docno": row["docno"],
            "rank": int(row["rank"]),
            "score": float(row["score"]),
        }
        for f in requested:
            try:
                item[f] = meta.getItem(f, docid)
            except Exception:
                item[f] = None
        out.append(item)

    return {"query": q, "count": len(out), "value": out}
