"""Run reproducible retrieval evaluation in a disposable SQLite database."""

import argparse
import hashlib
import json
import math
import platform
import statistics
from collections import defaultdict
from datetime import datetime
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import InformationRecord
from app.db.models.base import Base
from app.services.content.catalog import register_places
from evaluation.keyword_baseline import search_information as baseline_search

DATASET = Path(__file__).with_name("campus.json")


def load_dataset(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    documents = [item["id"] for item in data["documents"]]
    queries = [item["id"] for item in data["queries"]]
    if len(documents) != len(set(documents)) or len(queries) != len(set(queries)):
        raise ValueError("document and query IDs must be unique")
    if not queries:
        raise ValueError("at least one query is required")
    for query in data["queries"]:
        labels = query["relevant"]
        if len(labels) != len(set(labels)) or not set(labels) <= set(documents):
            raise ValueError(f"invalid relevance labels: {query['id']}")
    if datetime.fromisoformat(data["now"]).tzinfo is None:
        raise ValueError("evaluation clock must include a timezone")
    if not isinstance(data["distractor_count"], int) or data["distractor_count"] < 0:
        raise ValueError("distractor_count must be a nonnegative integer")
    return data


def seed(session: Session, data: dict) -> None:
    register_places(session)
    recent = datetime.fromisoformat(data["now"])
    old = datetime.fromisoformat("2026-09-01T00:00:00+08:00")
    middle = datetime.fromisoformat("2026-11-10T00:00:00+08:00")
    for document in data["documents"]:
        fetched = old if document.get("old") else recent
        session.add(
            InformationRecord(
                id=uuid5(NAMESPACE_URL, f"livelife-evaluation:{document['id']}"),
                platform="evaluation",
                source_id=document["id"],
                source_url=f"https://example.test/evaluation/{document['id']}",
                source_name="人工构造的校园检索样本",
                title=document["title"],
                content=document["content"],
                raw_content=document["content"],
                raw_payload={"synthetic": True},
                fetched_at=fetched,
                first_fetched_at=fetched,
                processed_at=fetched,
                published_at=fetched,
                activity_location=document.get("location"),
                activity_start_at=datetime.fromisoformat(document["start"])
                if document.get("start")
                else None,
                activity_end_at=datetime.fromisoformat(document["end"])
                if document.get("end")
                else None,
            )
        )
    for number in range(data["distractor_count"]):
        identity = f"distractor-{number}"
        session.add(
            InformationRecord(
                id=uuid5(NAMESPACE_URL, f"livelife-evaluation:{identity}"),
                platform="evaluation",
                source_id=identity,
                source_url=f"https://example.test/evaluation/{identity}",
                title=f"归档编号 {number}",
                content="本条仅供归档核验，无可回答的校园业务事实。",
                raw_content="本条仅供归档核验，无可回答的校园业务事实。",
                raw_payload={"synthetic": True},
                fetched_at=middle,
                first_fetched_at=middle,
                processed_at=middle,
            )
        )
    session.commit()


def score_query(query: dict, retrieved: list[str]) -> dict:
    # Multiple chunks of one document count once; assess the first 8 records.
    returned = list(dict.fromkeys(retrieved))[:8]
    relevant = set(query["relevant"])
    hits = len(relevant.intersection(returned))
    return {
        **query,
        "retrieved": returned,
        "hits": hits,
        "recall_at_8": hits / len(relevant) if relevant else None,
        "irrelevant_count": len(returned) - hits,
        "irrelevant_ratio": (len(returned) - hits) / len(returned) if returned else None,
    }


def summarize(rows: list[dict]) -> dict:
    answerable = [row for row in rows if row["relevant"]]
    unanswered = [row for row in rows if not row["relevant"]]
    returned = sum(len(row["retrieved"]) for row in answerable)
    irrelevant = sum(row["irrelevant_count"] for row in answerable)
    latencies = sorted(row["latency_ms"] for row in rows)
    return {
        "query_count": len(rows),
        "answerable_count": len(answerable),
        "macro_recall_at_8": statistics.mean(row["recall_at_8"] for row in answerable)
        if answerable
        else None,
        "irrelevant_ratio_answerable": irrelevant / returned if returned else None,
        "no_answer_count": len(unanswered),
        "no_answer_with_candidates": sum(bool(row["retrieved"]) for row in unanswered),
        "latency_p50_ms": statistics.median(latencies) if latencies else None,
        "latency_p95_ms": latencies[math.ceil(len(latencies) * 0.95) - 1] if latencies else None,
    }


def evaluate(data: dict, search=baseline_search) -> dict:
    # Never connect to DATABASE_URL or mutate an existing database.
    with TemporaryDirectory(prefix="livelife-retrieval-") as directory:
        engine = create_engine(f"sqlite+pysqlite:///{Path(directory) / 'evaluation.db'}")
        try:
            Base.metadata.create_all(engine)
            with Session(engine) as session:
                seed(session, data)
                rows = run_queries(session, data, search)
        finally:
            engine.dispose()
    return report(data, rows)


def run_queries(session, data, search, *, diagnostics=None):
    rows = []
    for query in data["queries"]:
        started = perf_counter()
        results = search(session, query["question"], limit=8)
        elapsed = (perf_counter() - started) * 1000
        rows.append(
            {
                **score_query(query, [item.source_id for item in results]),
                "latency_ms": elapsed,
                **({"retrieval": dict(diagnostics)} if diagnostics is not None else {}),
            }
        )
    return rows


def report(data, rows):
    categories = defaultdict(list)
    for row in rows:
        categories[row["category"]].append(row)
    return {
        "dataset_version": data["version"],
        "dataset_sha256": hashlib.sha256(
            json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest(),
        "synthetic": True,
        "evaluation_now": data["now"],
        "document_count": len(data["documents"]) + data["distractor_count"],
        "host": {"system": platform.system(), "machine": platform.machine()},
        "summary": summarize(rows),
        "categories": {name: summarize(items) for name, items in categories.items()},
        "queries": rows,
    }


def compare_postgres(data, embedding_pid=None):
    from dataclasses import replace

    from app.db.local import local_database
    from app.services.agent.retrieval import search_information
    from app.services.retrieval.config import get_retrieval_settings
    from app.services.retrieval.indexing import process_batch
    from evaluation.resources import MemorySampler

    settings = replace(get_retrieval_settings(), mode="hybrid")
    if not settings.base_url or not settings.model_revision:
        raise ValueError("set EMBEDDING_BASE_URL and pin EMBEDDING_MODEL_REVISION")
    with TemporaryDirectory(prefix="livelife-retrieval-pg-") as directory:
        with local_database(Path(directory) / "postgres") as url:
            engine = create_engine(url)
            factory = sessionmaker(engine, expire_on_commit=False)
            try:
                with factory() as session:
                    seed(session, data)
                with MemorySampler(embedding_pid) as memory:
                    started = perf_counter()
                    indexed = 0
                    while True:
                        batch = process_batch(factory, settings)
                        indexed += batch["indexed"]
                        if batch["failed"]:
                            raise RuntimeError("index build failed; inspect worker error codes")
                        if not batch["selected"]:
                            break
                    index_seconds = perf_counter() - started
                    modes = {}
                    for mode in ("baseline", "keyword", "hybrid"):
                        diagnostics = {} if mode != "baseline" else None
                        search = (
                            baseline_search
                            if mode == "baseline"
                            else partial(
                                search_information,
                                now=datetime.fromisoformat(data["now"]),
                                settings=replace(settings, mode=mode),
                                diagnostics=diagnostics,
                            )
                        )
                        with factory() as session:
                            rows = run_queries(session, data, search, diagnostics=diagnostics)
                        modes[mode] = report(data, rows)
            finally:
                engine.dispose()
    return {
        "model": settings.model,
        "model_revision": settings.model_revision,
        "profile": settings.profile,
        "dimensions": settings.dimensions,
        "min_similarity": settings.min_similarity,
        "indexed_records": indexed,
        "index_seconds": index_seconds,
        "sampled_peak_rss_bytes": memory.peaks,
        "rss_sample_interval_seconds": 0.1,
        "gpu_memory": "not_measured",
        "reports": modes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument(
        "--mode", choices=("baseline", "current", "compare-postgres"), default="baseline"
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--embedding-pid", type=int)
    args = parser.parse_args()
    search = baseline_search
    data = load_dataset(args.dataset)
    if args.mode == "current":
        from app.services.agent.retrieval import search_information
        from app.services.retrieval.config import RetrievalSettings

        search = partial(
            search_information,
            now=datetime.fromisoformat(data["now"]),
            settings=RetrievalSettings(),
        )
    result = {
        "mode": args.mode,
        **(
            compare_postgres(data, args.embedding_pid)
            if args.mode == "compare-postgres"
            else evaluate(data, search)
        ),
    }
    serialized = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")


if __name__ == "__main__":
    main()
