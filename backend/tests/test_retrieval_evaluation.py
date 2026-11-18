import pytest

from evaluation.retrieval import DATASET, evaluate, load_dataset, score_query, summarize


def test_metrics_deduplicate_records_and_separate_unanswerable_queries():
    first = {
        **score_query({"relevant": ["a", "b"]}, ["a", "a", "c"]),
        "latency_ms": 10,
    }
    second = {**score_query({"relevant": []}, ["c"]), "latency_ms": 20}
    missing = {**score_query({"relevant": ["b"]}, []), "latency_ms": 30}
    assert first["recall_at_8"] == 0.5
    assert first["irrelevant_ratio"] == 0.5
    assert second["recall_at_8"] is None
    assert missing["recall_at_8"] == 0
    assert missing["irrelevant_ratio"] is None
    summary = summarize([first, second, missing])
    assert summary["macro_recall_at_8"] == 0.25
    assert summary["irrelevant_ratio_answerable"] == 0.5
    assert summary["no_answer_count"] == 1
    assert summary["no_answer_with_candidates"] == 1
    assert summary["latency_p95_ms"] == 30


def test_dataset_and_baseline_expose_old_record_window():
    data = load_dataset(DATASET)
    assert len(data["queries"]) >= 20
    assert data["distractor_count"] > 500
    result = evaluate(data)
    assert result["categories"]["old"]["macro_recall_at_8"] == 0
    assert result["categories"]["exact"]["macro_recall_at_8"] == pytest.approx(1)
    assert result["summary"]["no_answer_count"] == 5
    assert result["document_count"] == 519
