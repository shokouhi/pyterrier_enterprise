# src/sample_and_eval.py
import argparse
import random
import re
from pathlib import Path

import pandas as pd
import pyterrier as pt
from ir_measures import AP, nDCG, P, R  # metric objects

_QREL_RE = re.compile(r"^(\S+)\s+(\S+)\s+(.*)\s+(-?\d+)\s*$")
FIELDY = re.compile(r'\b(?:site|filetype|inurl|intitle|ext):\S+', re.IGNORECASE)
ONLY_ALNUM = re.compile(r"[A-Za-z0-9]+")

def clean_query(q: str) -> str:
    if not isinstance(q, str):
        return ""
    q = FIELDY.sub(" ", q)
    q = q.replace('"', " ").replace("'", " ")
    toks = ONLY_ALNUM.findall(q.lower())
    return " ".join(toks).strip()

def read_queries(map_path: Path | None, topics_path: Path | None) -> pd.DataFrame:
    if map_path:
        df = pd.read_csv(map_path, sep="\t", dtype=str)
        qcol = "canonical_query" if "canonical_query" in df.columns else "query"
        df = df[["qid", qcol]].rename(columns={qcol: "query"})
    else:
        df = pd.read_csv(topics_path, sep="\t", header=None, names=["qid", "query"], dtype=str)
    df["qid"] = df["qid"].astype(str)
    df["query"] = df["query"].fillna("").str.strip()
    return df[df["query"] != ""].drop_duplicates(subset=["qid"])

def read_qrels(qrels_path: Path) -> pd.DataFrame:
    recs = []
    with open(qrels_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line:
                continue
            m = _QREL_RE.match(line)
            if not m:
                continue
            qid, _, docno, label = m.groups()
            recs.append((qid, docno, int(label)))
    if not recs:
        raise RuntimeError(f"No qrels parsed from {qrels_path}")
    df = pd.DataFrame(recs, columns=["qid", "docno", "label"])
    df["qid"] = df["qid"].astype(str)
    df["docno"] = df["docno"].astype(str)
    return df

def parse_metric(token: str):
    tok = token.strip()
    if "@" in tok:
        name, k = tok.split("@", 1)
        name = name.strip().lower()
        try:
            k = int(k.strip())
        except ValueError:
            raise ValueError(f"Invalid cutoff in metric: {token}")
    else:
        name, k = tok.lower(), None

    if name in ("map", "ap"):
        return AP() if k is None else (AP() @ k)
    if name in ("ndcg", "ndcg10", "ndcgs"):
        return nDCG if k is None else (nDCG @ k)
    if name in ("p", "prec", "precision"):
        if k is None:
            raise ValueError("Precision requires a cutoff, e.g. P@10")
        return P @ k
    if name in ("r", "recall"):
        if k is None:
            raise ValueError("Recall requires a cutoff, e.g. R@100")
        return R @ k
    raise ValueError(f"Unknown metric: {token}")

def main():
    ap = argparse.ArgumentParser(description="Sample queries, run BM25, and evaluate with qrels.")
    ap.add_argument("--index", required=True, help="PyTerrier index directory")
    ap.add_argument("--qrels", required=True, help="qrels: qid 0 docno label")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--map", dest="map_path", help="query_id_map.tsv (qid<TAB>canonical_query)")
    g.add_argument("--topics", dest="topics_path", help="topics.tsv (qid<TAB>query)")
    ap.add_argument("--n", type=int, default=50, help="sample size")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--k", type=int, default=1000, help="retrieval depth")
    ap.add_argument("--metrics", nargs="+", default=["AP", "nDCG@10", "P@10", "R@100"])
    ap.add_argument("--run_out", default="./runs/sample_bm25.trec")
    ap.add_argument("--metrics_out", default="./runs/sample_metrics.csv")
    ap.add_argument("--tag", default="BM25")
    args = ap.parse_args()

    pt.java.init()

    index_path = Path(args.index)
    if not index_path.exists():
        raise FileNotFoundError(f"Index not found: {index_path}")

    # Read & clean all queries
    queries = read_queries(Path(args.map_path) if args.map_path else None,
                           Path(args.topics_path) if args.topics_path else None)
    queries["query"] = queries["query"].map(clean_query)
    queries = queries[queries["query"] != ""].drop_duplicates(subset=["qid"]).reset_index(drop=True)
    if queries.empty:
        raise RuntimeError("All queries became empty after cleaning.")

    # Sample once
    random.seed(args.seed)
    n_sample = min(args.n, len(queries))
    topics = queries.sample(n=n_sample, random_state=args.seed).copy().reset_index(drop=True)

    # Show a peek
    print("Sampled queries (qid → query):")
    for _, r in topics.head(10).iterrows():
        print(f"  {r['qid']} → {r['query']}")

    if topics.empty:
        raise RuntimeError("No queries found after cleaning/sampling.")

    # Read qrels, then subset to sampled qids
    qrels = read_qrels(Path(args.qrels))
    qrels_sample = qrels[qrels["qid"].isin(topics["qid"])].copy()
    if qrels_sample.empty:
        print("Warning: no qrels found for the sampled qids. Evaluation will report NaNs.")

    # Final topic hygiene for Terrier
    topics = topics.loc[:, ["qid", "query"]].copy()
    topics["qid"] = topics["qid"].astype(str)
    topics["query"] = topics["query"].astype(str).map(str.strip)
    topics = topics[(topics["query"] != "") & topics["query"].notna()].reset_index(drop=True)

    def _token_ok(s: str) -> bool:
        return any(len(t) >= 2 for t in s.split())

    bad_mask = ~topics["query"].map(_token_ok)
    if bad_mask.any():
        bad_examples = topics.loc[bad_mask, "qid"].tolist()[:10]
        print(f"Dropping {bad_mask.sum()} queries with no acceptable tokens. Example qids: {bad_examples}")
        topics = topics.loc[~bad_mask].reset_index(drop=True)

    if topics.empty:
        raise RuntimeError("No valid queries remain after cleaning; increase --n or change --seed.")

    # Retriever (BM25)
# replace your retr = pt.terrier.Retriever(...controls=...) % args.k
    retr = pt.terrier.Retriever(index_path.as_posix(), wmodel="BM25") % args.k
# or (also fine)
# retr = pt.BatchRetrieve(index_path.as_posix(), wmodel="BM25") % args.k


    # Metrics
    metric_objs = [parse_metric(m) for m in args.metrics]

    # Run experiment
    res = pt.Experiment(
        [retr],
        topics,
        qrels_sample,
        eval_metrics=metric_objs,
        names=[args.tag],
        verbose=True,
    )

    # Save TREC run (rank starts at 1)
# Also save a TREC run for the sampled topics
    run_df = retr.transform(topics)

    # Ensure required columns exist
    missing = {"qid", "docno", "score"} - set(run_df.columns)
    if missing:
        raise RuntimeError(f"Retriever output missing columns: {missing}")

    run_df = run_df.sort_values(["qid", "score"], ascending=[True, False]).copy()
    run_df["rank"] = run_df.groupby("qid").cumcount() + 1  # 1-based for TREC

    # Build TREC lines (vectorized; avoids Series attribute pitfalls)
    trec_lines = run_df.apply(
        lambda r: f"{r['qid']} Q0 {r['docno']} {int(r['rank'])} {float(r['score']):.6f} {args.tag}",
        axis=1,
    ).tolist()

    out_run = Path(args.run_out)
    out_run.parent.mkdir(parents=True, exist_ok=True)
    out_run.write_text("\n".join(trec_lines) + ("\n" if trec_lines else ""), encoding="utf-8")


    # Save metrics CSV
    out_metrics = Path(args.metrics_out)
    out_metrics.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(out_metrics, index=False)

    # Summary
    sample_qids = list(topics["qid"])
    print("=== Sample & Eval Summary ===", flush=True)
    print(f"Sampled queries : {len(sample_qids)}", flush=True)
    print(f"Index           : {index_path}", flush=True)
    print(f"Run             : {out_run}", flush=True)
    print(f"Metrics CSV     : {out_metrics}", flush=True)
    print(res.to_string(index=False), flush=True)

if __name__ == "__main__":
    main()
