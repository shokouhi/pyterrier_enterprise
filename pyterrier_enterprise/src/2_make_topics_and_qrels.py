import argparse, csv, hashlib, io, sys, re
from pathlib import Path
from urllib.parse import urlparse, unquote

def build_wiki_index(wiki_dir: Path) -> dict[str, Path]:
    idx = {}
    for p in list(wiki_dir.glob("*.htm")) + list(wiki_dir.glob("*.html")):
        name = p.name  # e.g., "3669476_Kernel-Mode_Driver_Framework.html"
        if "_" in name:
            wiki_id = name.split("_", 1)[0]
            # prefer first seen; if there are multiple, keep the shortest filename
            if wiki_id not in idx or len(p.name) < len(idx[wiki_id].name):
                idx[wiki_id] = p
    return idx


def log(msg: str, *, flush=True):
    print(msg, flush=flush)

def canon_query(q: str) -> str:
    # normalize for dedup (same string across rows -> same qid)
    return " ".join((q or "").strip().split()).lower()

def qid_for(cq: str) -> str:
    # stable id: 12 hex chars -> int string
    return str(int(hashlib.sha1(cq.encode("utf-8")).hexdigest()[:12], 16))

def basename_from_url(u: str) -> str:
    p = urlparse(u or "")
    return Path(unquote(p.path)).name if p.path else ""

def find_wiki_html(wiki_dir: Path, wiki_id: str):
    # simple: first file that starts with "<id>_"
    for cand in list(wiki_dir.glob(f"{wiki_id}_*.htm")) + list(wiki_dir.glob(f"{wiki_id}_*.html")):
        return cand
    return None

def file_nonempty(p: Path) -> bool:
    try:
        return p.exists() and p.is_file() and p.stat().st_size > 0
    except Exception:
        return False

def open_tsv_utf8(path: Path):
    # robust open: try utf-8 then BOM/utf-16 fallbacks
    try:
        return open(path, "r", encoding="utf-8", newline="")
    except UnicodeError:
        raw = open(path, "rb").read()
        for enc in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "cp1252"):
            try:
                return io.StringIO(raw.decode(enc))
            except Exception:
                pass
        raise

def main():
    ap = argparse.ArgumentParser(description="Build topics (qid↔query) and qrels from SuggestedQueriesDone.tsv")
    ap.add_argument("--tsv", required=True)
    ap.add_argument("--doc_dir", required=True)
    ap.add_argument("--wiki_dir", required=True)
    ap.add_argument("--topics_out", required=True)
    ap.add_argument("--qrels_out", required=True)
    ap.add_argument("--map_out", required=True)
    ap.add_argument("--doc_rel", type=int, default=4)
    ap.add_argument("--wiki_rel", type=int, default=1)
    ap.add_argument("--max_queries_per_row", type=int, default=5)
    ap.add_argument("--verbose", action="store_true", help="Print per-row progress")
    args = ap.parse_args()

    tsv_path = Path(args.tsv)
    doc_dir  = Path(args.doc_dir)
    wiki_dir = Path(args.wiki_dir)
    topics_out = Path(args.topics_out)
    qrels_out  = Path(args.qrels_out)
    map_out    = Path(args.map_out)

    # Ensure output folder exists
    topics_out.parent.mkdir(parents=True, exist_ok=True)
    qrels_out.parent.mkdir(parents=True, exist_ok=True)
    map_out.parent.mkdir(parents=True, exist_ok=True)

    # Sanity checks
    if not tsv_path.exists():
        log(f"ERROR: TSV not found -> {tsv_path}"); sys.exit(2)
    if not doc_dir.exists():
        log(f"ERROR: DOC_DIR not found -> {doc_dir}"); sys.exit(2)
    if not wiki_dir.exists():
        log(f"ERROR: WIKI_DIR not found -> {wiki_dir}"); sys.exit(2)

    log("=== make_topics_and_qrels ===")
    log(f"TSV      : {tsv_path.resolve()}")
    log(f"DOC_DIR  : {doc_dir}")
    log(f"WIKI_DIR : {wiki_dir}")
    log(f"OUT      : topics={topics_out}, qrels={qrels_out}, map={map_out}")

    # Accumulators
    queries_seen: dict[str, tuple[str,str]] = {}  # canon -> (qid, first_seen_original)
    qrels_lines: list[tuple[str,str,int]] = []    # (qid, docno, rel)

    wiki_lookup = build_wiki_index(wiki_dir)


    total_rows = 0
    with_docs  = 0
    with_wiki  = 0
    rows_with_any = 0
    missing_doc = empty_doc = 0
    missing_wiki = empty_wiki = 0

    f = open_tsv_utf8(tsv_path)
    reader = csv.reader(f, delimiter="\t")
    for row in reader:
        if not row or len(row) < 4:
            continue
        # detect & skip header (first cell not all digits)
        if total_rows == 0 and not row[0].strip().isdigit():
            if args.verbose: log("Header row detected, skipping")
            continue

        total_rows += 1
        wiki_id, wiki_title, wiki_url, tgt_url, *query_cols = row
        # use only up to N query columns
        query_cols = [q for q in query_cols[:args.max_queries_per_row] if q and q.strip()]

        # Map document path
        doc_ok = False
        docno = None
        base = basename_from_url(tgt_url)
        if base:
            docno = str((doc_dir / f"{wiki_id}_{base}"))
            p = Path(docno)
            if not p.exists():
                missing_doc += 1
            elif not file_nonempty(p):
                empty_doc += 1
            else:
                doc_ok = True
                with_docs += 1
        else:
            missing_doc += 1

        # Map wiki path
        wiki_ok = False
        wpath = wiki_lookup.get(wiki_id)

        if wpath is None:
            missing_wiki += 1
        elif not file_nonempty(wpath):
            empty_wiki += 1
        else:
            wiki_ok = True
            with_wiki += 1
            wdoc = str(wpath)

        # Assign qids and add qrels
        if query_cols:
            for q in query_cols:
                cq = canon_query(q)
                if not cq:
                    continue
                if cq not in queries_seen:
                    queries_seen[cq] = (qid_for(cq), q)
                qid = queries_seen[cq][0]
                if doc_ok:
                    qrels_lines.append((qid, docno, args.doc_rel))
                if wiki_ok:
                    qrels_lines.append((qid, wdoc, args.wiki_rel))
            if doc_ok or wiki_ok:
                rows_with_any += 1

        if args.verbose and total_rows % 20 == 0:
            log(f"[{total_rows}] queries_seen={len(queries_seen)} qrels={len(qrels_lines)}")

    f.close()

    # Write topics
    with open(topics_out, "w", encoding="utf-8", newline="") as ft:
        w = csv.writer(ft, delimiter="\t", lineterminator="\n")
        for cq,(qid,orig) in sorted(queries_seen.items(), key=lambda kv: kv[1][0]):
            w.writerow([qid, orig])

    # Write qrels
    with open(qrels_out, "w", encoding="utf-8") as fq:
        for qid, docno, rel in qrels_lines:
            fq.write(f"{qid} 0 {docno} {rel}\n")

    # Write map (for audit)
    with open(map_out, "w", encoding="utf-8", newline="") as fm:
        w = csv.writer(fm, delimiter="\t", lineterminator="\n")
        w.writerow(["qid","canonical_query"])
        for cq,(qid,_) in sorted(queries_seen.items(), key=lambda kv: kv[1][0]):
            w.writerow([qid, cq])

    # Always print a summary
    log("=== Summary ===")
    log(f"Rows processed      : {total_rows}")
    log(f"Rows w/ any files   : {rows_with_any}")
    log(f"Unique queries      : {len(queries_seen)}")
    log(f"Qrels lines         : {len(qrels_lines)}")
    log(f"Docs OK             : {with_docs}   (missing={missing_doc}, empty={empty_doc})")
    log(f"Wiki OK             : {with_wiki}   (missing={missing_wiki}, empty={empty_wiki})")
    log(f"topics.tsv bytes    : {topics_out.stat().st_size if topics_out.exists() else 0}")
    log(f"targets.qrels bytes : {qrels_out.stat().st_size if qrels_out.exists() else 0}")
    log(f"query_id_map bytes  : {map_out.stat().st_size if map_out.exists() else 0}")
    log("Done.")
    
if __name__ == "__main__":
    main()
