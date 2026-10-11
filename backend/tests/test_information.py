from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import InformationRecord
from app.repositories.sql.information import InformationRepository
from app.schemas.information import InformationInput, InformationQuery
from app.services.content import InformationAggregator, InformationProvider
from app.services.ingestion import collect_information

NOW = datetime(2026, 10, 11, 4, tzinfo=UTC)
BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def sessions(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    # Exercise the real migration, then read through independent connections.
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'information.db').as_posix()}")
    config = Config(str(BACKEND / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    try:
        yield sessionmaker(engine, expire_on_commit=False)
    finally:
        engine.dispose()


def item(source_id: str = "account:article-1", **changes) -> InformationInput:
    values = {
        "platform": "wechat",
        "source_id": source_id,
        "source_url": "https://example.com/articles/1",
        "content": "  校园讲座\n报名开放。  ",
        "fetched_at": NOW,
    }
    values.update(changes)
    return InformationInput(**values)


def ingest(sessions, *records):
    with sessions() as session:
        return InformationAggregator(session).ingest(records)


def lookup(sessions, query=None):
    with sessions() as session:
        return InformationProvider(session).list(query)


@pytest.mark.parametrize(
    "changes",
    [
        {"content": " \n "},
        {"source_id": " "},
        {"platform": "WeChat!"},
        {"fetched_at": datetime(2026, 10, 11)},
        {"published_at": "2026-10-11T09:00:00"},
        {"source_url": "file:///private/data"},
        {"activity_start_at": NOW, "activity_end_at": NOW},
        {"activity_start_at": NOW, "activity_end_at": NOW - timedelta(hours=1)},
        {"activity_location": " "},
        {"unexpected_field": True},
    ],
)
def test_invalid_input_is_rejected(changes):
    with pytest.raises(ValidationError):
        item(**changes)


def test_persists_normalized_information_and_preserves_latest_raw_snapshot(sessions):
    original = item(
        fetched_at="2026-10-11T12:00:00+08:00",
        title="  示例讲座  ",
        raw_payload={"source_text": "原始字段", "nested": [1, None, True]},
    )
    (result,) = ingest(sessions, original)
    (loaded,) = lookup(sessions)
    assert loaded == result
    assert loaded.content == "校园讲座\n报名开放。"
    assert loaded.title == "示例讲座"
    assert loaded.fetched_at == NOW
    assert loaded.fetched_at.tzinfo == UTC
    assert loaded.first_fetched_at == NOW
    assert loaded.processed_at.tzinfo == UTC
    assert loaded.activity_location is None
    assert loaded.activity_start_at is None
    assert loaded.published_at is None
    assert loaded.model_dump(mode="json")["fetched_at"] == "2026-10-11T04:00:00Z"
    assert "raw_payload" not in loaded.model_dump()
    with sessions() as session:
        raw = session.get(InformationRecord, result.id)
        assert raw.raw_content == original.content
        assert raw.raw_payload == original.raw_payload


def test_retries_and_late_arrivals_keep_identity_and_newest_observation(sessions):
    (first,) = ingest(sessions, item())
    newer = item(content="新版", fetched_at=NOW + timedelta(hours=1))
    (updated,) = ingest(sessions, newer)
    assert updated.id == first.id
    assert updated.first_fetched_at == first.fetched_at
    assert updated.content == "新版"
    for replay in (newer, item(), item(content="同时间冲突", fetched_at=newer.fetched_at)):
        (unchanged,) = ingest(sessions, replay)
        assert unchanged == updated
    assert len(lookup(sessions)) == 1


def test_platform_namespaces_and_same_batch_duplicates(sessions):
    latest = item(content="新内容", fetched_at=NOW + timedelta(hours=2))
    results = ingest(sessions, latest, item(), item(platform="zhihu"))
    assert len(results) == 2
    assert results[0].content == "新内容"
    assert results[0].platform == "wechat"
    assert results[1].platform == "zhihu"
    assert results[0].id != results[1].id


def test_new_snapshot_clears_obsolete_activity_fields_and_replaces_raw_data(sessions):
    (first,) = ingest(
        sessions,
        item(
            activity_location="旧地点",
            activity_start_at=NOW,
            raw_payload={"version": 1},
        ),
    )
    (updated,) = ingest(
        sessions,
        item(
            content="  修改后的正文  ",
            fetched_at=NOW + timedelta(hours=1),
            raw_payload={"version": 2},
        ),
    )
    assert updated.id == first.id
    assert updated.activity_location is None
    assert updated.activity_start_at is None
    with sessions() as session:
        raw = session.get(InformationRecord, first.id)
        assert raw.raw_content == "  修改后的正文  "
        assert raw.raw_payload == {"version": 2}


def test_ingestion_does_not_commit_or_rollback_a_callers_active_transaction(sessions):
    with sessions() as session:
        with session.begin():
            with pytest.raises(InvalidRequestError):
                InformationAggregator(session).ingest([item()])
            assert session.in_transaction()
    assert lookup(sessions) == ()


def test_postgresql_upsert_compiles_with_atomic_conflict_and_timestamp_guard():
    session = Mock(spec=Session)
    session.get_bind.return_value.dialect = postgresql.dialect()
    InformationRepository(session).upsert(item(), NOW)
    statement = session.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (platform, source_id) DO UPDATE" in sql
    assert "WHERE information_items.fetched_at < excluded.fetched_at" in sql


def test_database_failure_rolls_back_the_entire_batch(sessions, monkeypatch):
    with sessions() as session:
        service = InformationAggregator(session)
        original = service.repository.upsert

        def fail_second(record, processed_at):
            if record.source_id == "second":
                raise RuntimeError("simulated storage failure")
            original(record, processed_at)

        monkeypatch.setattr(service.repository, "upsert", fail_second)
        with pytest.raises(RuntimeError, match="storage failure"):
            service.ingest([item("first"), item("second")])
        assert not session.in_transaction()
    assert lookup(sessions) == ()


def test_invalid_batch_and_fetch_failure_do_not_persist_partial_results(sessions):
    class BrokenSource:
        platform = "wechat"

        def fetch(self):
            yield item()
            raise OSError("source unavailable")

    with sessions() as session:
        aggregator = InformationAggregator(session)
        with pytest.raises(OSError, match="source unavailable"):
            collect_information(BrokenSource(), aggregator)
        with pytest.raises(ValidationError):
            aggregator.ingest([item(), {"content": "invalid record"}])
    assert lookup(sessions) == ()


def test_source_adapter_can_feed_information_and_rejects_wrong_platform(sessions):
    class ExampleSource:
        platform = "wechat"

        def fetch(self):
            return [item()]

    with sessions() as session:
        results = collect_information(ExampleSource(), InformationAggregator(session))
        assert len(results) == 1
    with sessions() as session:
        source = ExampleSource()
        source.platform = "xiaohongshu"
        with pytest.raises(ValueError, match="platform"):
            collect_information(source, InformationAggregator(session))
    assert len(lookup(sessions)) == 1


def test_empty_and_oversized_batches(sessions):
    with sessions() as session:
        aggregator = InformationAggregator(session)
        assert aggregator.ingest([]) == ()
        with pytest.raises(ValueError, match="1000"):
            aggregator.ingest(item(str(index)) for index in range(1001))
    assert lookup(sessions) == ()


def test_get_returns_detached_data_or_none(sessions):
    (saved,) = ingest(sessions, item())
    with sessions() as session:
        provider = InformationProvider(session)
        assert provider.get(saved.id) == saved
        assert provider.get(uuid4()) is None
    assert saved.content
    with pytest.raises(ValidationError):
        saved.content = "cannot mutate shared data"


def test_filters_platform_fetch_window_and_literal_location(sessions):
    ingest(
        sessions,
        item("first", activity_location="理教 100% 展厅"),
        item("second", fetched_at=NOW + timedelta(hours=1), activity_location="理教 100 展厅"),
        item("third", platform="zhihu", fetched_at=NOW + timedelta(hours=2)),
    )
    records = lookup(
        sessions,
        InformationQuery(
            platform="wechat", fetched_after=NOW, fetched_before=NOW + timedelta(hours=1)
        ),
    )
    assert [record.source_id for record in records] == ["first"]
    literal = lookup(sessions, InformationQuery(activity_location="100%"))
    assert [record.source_id for record in literal] == ["first"]


def test_calendar_overlap_uses_half_open_windows_and_never_infers_missing_times(sessions):
    start = NOW
    end = NOW + timedelta(hours=2)
    ingest(
        sessions,
        item("spanning", activity_start_at=start - timedelta(days=1), activity_end_at=end),
        item("ends_at_start", activity_start_at=start - timedelta(hours=1), activity_end_at=start),
        item("starts_at_end", activity_start_at=end, activity_end_at=end + timedelta(hours=1)),
        item("point_at_start", activity_start_at=start),
        item("unknown_end_in_past", activity_start_at=start - timedelta(days=1)),
        item("end_only", activity_end_at=end),
        item("unknown"),
    )
    records = lookup(sessions, InformationQuery(activity_after=start, activity_before=end))
    assert {record.source_id for record in records} == {"spanning", "point_at_start"}
    assert len(lookup(sessions)) == 7


def test_calendar_query_preserves_local_date_boundaries(sessions):
    ingest(
        sessions,
        item("before", activity_start_at="2026-10-10T23:59:00+08:00"),
        item("inside", activity_start_at="2026-10-11T00:00:00+08:00"),
        item("after", activity_start_at="2026-10-12T00:00:00+08:00"),
    )
    records = lookup(
        sessions,
        InformationQuery(
            activity_after="2026-10-11T00:00:00+08:00",
            activity_before="2026-10-12T00:00:00+08:00",
        ),
    )
    assert [record.source_id for record in records] == ["inside"]


def test_pagination_has_deterministic_tie_breaking(sessions):
    ingest(sessions, *(item(str(index)) for index in range(5)))
    all_records = lookup(sessions)
    first = lookup(sessions, InformationQuery(limit=2))
    second = lookup(sessions, InformationQuery(limit=3, offset=2))
    assert first + second == all_records
    assert [record.id for record in all_records] == sorted(
        (record.id for record in all_records), reverse=True
    )


@pytest.mark.parametrize(
    "query",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"fetched_after": NOW, "fetched_before": NOW},
        {"activity_after": NOW, "activity_before": NOW - timedelta(hours=1)},
        {"activity_after": datetime(2026, 10, 11)},
    ],
)
def test_invalid_queries_are_rejected(query):
    with pytest.raises(ValidationError):
        InformationQuery(**query)


def test_internal_information_services_do_not_add_http_routes():
    from app.main import app

    paths = set(app.openapi()["paths"])
    assert paths == {"/test/hello", "/health/live", "/health/ready"}


def test_record_remains_unique_after_repeated_ingestion(sessions):
    ingest(sessions, *(item() for _ in range(10)))
    with sessions() as session:
        assert len(session.scalars(select(InformationRecord)).all()) == 1
