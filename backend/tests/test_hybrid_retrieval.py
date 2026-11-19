from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete, func, select, text, update
from sqlalchemy.orm import sessionmaker

from app.db.models import InformationRecord, RetrievalChunk, RetrievalState
from app.services.agent.context import conversation_context
from app.services.agent.retrieval import search_information
from app.services.retrieval.chunks import split_record
from app.services.retrieval.config import RetrievalSettings
from app.services.retrieval.embeddings import EmbeddingClient, EmbeddingError
from app.services.retrieval.indexing import process_batch, rebuild
from evaluation.retrieval import DATASET, load_dataset, seed

BACKEND = Path(__file__).resolve().parents[1]
NOW = datetime.fromisoformat("2026-11-18T14:30:00+08:00")


@pytest.fixture(params=["sqlite", "postgresql"])
def database(request, tmp_path):
    if request.param == "postgresql":
        if not request.config.getoption("--local-postgres"):
            pytest.skip("requires --local-postgres")
        from app.db.local import local_database

        with local_database(tmp_path / "retrieval-postgres") as url:
            engine = create_engine(url)
            try:
                yield sessionmaker(engine, expire_on_commit=False)
            finally:
                engine.dispose()
    else:
        engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'retrieval.db'}")
        config = Config(str(BACKEND / "alembic.ini"))
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        try:
            yield sessionmaker(engine, expire_on_commit=False)
        finally:
            engine.dispose()


def corpus(factory, *, distractors=0):
    data = load_dataset(DATASET)
    data["distractor_count"] = distractors
    with factory() as session:
        seed(session, data)
    return data


class FakeEncoder:
    def __init__(self, *, failure=False, callback=None):
        self.failure = failure
        self.callback = callback
        self.calls = 0

    def encode(self, texts, *, query=False):
        self.calls += 1
        if self.callback:
            callback, self.callback = self.callback, None
            callback()
        if self.failure:
            raise EmbeddingError("embedding_unavailable")
        # A controlled direction for exercising SQL, not a semantic-quality model.
        return [[1.0, 0.0, 0.0] for _ in texts]


def test_full_corpus_and_structured_filters(database):
    corpus(database, distractors=501)
    cases = {
        "图书续借办理指引": {"library-renewal"},
        "MATH101 的授课老师是谁": {"math-101"},
        "想问MATH101的老师是谁": {"math-101"},
        "想问MATH1010的老师是谁": set(),
        "二教101现在上什么课": {"math-101"},
        "第二教学楼1101现在上什么课": {"math-1101"},
        "三教101现在上什么课": {"physics-101"},
        "今天图书馆有什么古籍修复讲座": {"repair-today"},
        "明天二教101上什么课": {"math-tomorrow"},
        "二教999现在上什么课": set(),
        "明天图书馆古籍修复讲座几点开始": set(),
    }
    with database() as session:
        for question, expected in cases.items():
            rows = search_information(session, question, now=NOW, settings=RetrievalSettings())
            assert {row.source_id for row in rows} == expected, question
        pinned = session.scalar(
            select(InformationRecord.id).where(InformationRecord.source_id == "math-1101")
        )
        rows = search_information(session, "二教101现在上什么课", now=NOW, pinned_ids=(pinned,))
        assert {row.source_id for row in rows} == {"math-101"}


def test_explicit_date_prefix_preserves_exact_building_and_room(database):
    corpus(database)
    modes = ["keyword"]
    if database.kw["bind"].dialect.name == "postgresql":
        modes.append("hybrid")
        process_batch(database, RetrievalSettings(dimensions=3), client=FakeEncoder())
    cases = {
        "11月18日二教101上什么课？": {"math-101"},
        "请问2026年11月18日第二教学楼1101上什么课？": {"math-1101"},
        "2026-11-18，三教101上什么课？": {"physics-101"},
        "１１月１８号　二教１０１上什么课？": {"math-101"},
        "11月18日二教999上什么课？": set(),
        "11月19日二教101上什么课？": {"math-tomorrow"},
        "11月18日清华二教101上什么课？": set(),
    }
    with database() as session:
        for mode in modes:
            for question, expected in cases.items():
                rows = search_information(
                    session,
                    question,
                    now=NOW,
                    settings=RetrievalSettings(mode=mode, dimensions=3),
                    embedding_client=FakeEncoder(),
                )
                assert {row.source_id for row in rows} == expected, (mode, question)


def test_long_context_cannot_recall_sources_before_topic_switch(database):
    from uuid import uuid4

    from test_agent import ACCOUNT_ID, seed_account, settings

    from app.db.models import AgentSession
    from app.services.agent.service import _context_rows, create_session

    seed_account(database)
    corpus(database)
    created = create_session(database, settings(), "topic-boundary", user_id=ACCOUNT_ID)
    with database.begin() as session:
        original = session.scalar(
            select(InformationRecord).where(InformationRecord.source_id == "repair-yesterday")
        )
        payloads = [
            {"role": "user", "content": "古籍修复讲座在哪里？"},
            {
                "role": "assistant",
                "content": "在图书馆。[S1]",
                "citations": [
                    {"rank": 1, "information_id": str(original.id), "title": original.title}
                ],
            },
            {"role": "user", "content": "换个话题，智华楼414有什么报告？"},
            {"role": "assistant", "content": "目前未找到可靠资料。"},
        ]
        for question in (
            "报告主办方是哪家？",
            "还有其他安排吗？",
            "有没有海报？",
            "能给出链接吗？",
        ):
            payloads.extend(
                [
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": "目前未找到可靠资料。"},
                ]
            )
        session.get(AgentSession, created["session_id"]).messages = [
            {"id": str(uuid4()), "status": "completed", "citations": [], **payload}
            for payload in payloads
        ]
    with database() as session:
        for question in ("需要提前报名吗？", "这个古籍修复讲座呢？"):
            messages = _context_rows(session, created["session_id"], question)
            history, query, pinned = conversation_context(messages, question, NOW)
            assert not pinned
            assert not any("古籍修复" in message["content"] for message in history[:-1])
            assert "古籍修复讲座在哪里" not in query
        # A retry of the original turn must not see a later topic switch.
        messages = _context_rows(session, created["session_id"], "这个讲座呢？", before_sequence=3)
        _, _, pinned = conversation_context(messages, "这个讲座呢？", NOW)
        assert pinned == (original.id,)
    with database.begin() as session:
        current = session.scalar(
            select(InformationRecord).where(InformationRecord.source_id == "math-101")
        )
        conversation = session.get(AgentSession, created["session_id"])
        messages = conversation.messages
        messages[3] = {
            **messages[3],
            "content": "新话题的原始资料。[S1]",
            "citations": [{"information_id": str(current.id), "title": current.title}],
        }
        conversation.messages = messages
    with database() as session:
        messages = _context_rows(session, created["session_id"], "需要提前报名吗？")
        _, _, pinned = conversation_context(messages, "需要提前报名吗？", NOW)
        assert pinned == (current.id,)


def test_dated_event_with_current_participation_question(database):
    # Same title on adjacent days/years: semantic similarity cannot choose the date.
    days = {
        "past": "2026-11-17",
        "today": "2026-11-18",
        "future": "2026-11-19",
        "last-year": "2025-11-17",
        "new-year": "2027-01-01",
    }
    documents = [
        {
            "id": key,
            "title": "文献管理软件讲座",
            "content": "文献管理软件的功能与使用。",
            "location": "图书馆培训教室208",
            "start": day + "T14:00:00+08:00",
            "end": day + "T16:00:00+08:00",
        }
        for key, day in days.items()
    ]
    with database() as session:
        seed(session, {"now": NOW.isoformat(), "documents": documents, "distractor_count": 0})
    cases = {
        "11月17日文献管理软件讲座在哪里举办？现在还能参加吗？": {"past"},
        "１１月１７日文献管理软件讲座在哪里？此刻还可以参加吗？": {"past"},
        "昨天文献管理软件讲座在哪里？现在还能报名吗？": {"past"},
        "明天文献管理软件讲座在哪里？现在能报名吗？": {"future"},
        "2025年11月17日文献管理软件讲座在哪里？现在还能参加吗？": {"last-year"},
        "2026-11-17文献管理软件讲座在哪里举办？现在还能参加吗？": {"past"},
        "11月17号文献管理软件讲座在哪里举办？": {"past"},
        "文献管理软件讲座现在还能参加吗？": {"today"},
        "文献管理软件讲座现在正在进行吗？": {"today"},
        "昨天报名的文献管理软件讲座现在正在进行吗？": {"today"},
        "11月17日文献管理软件讲座现在还能参加吗？哪些正在进行？": {"today"},
        "11月31日文献管理软件讲座在哪里？现在还能参加吗？": set(),
        "9999年12月31日文献管理软件讲座在哪里？现在还能参加吗？": set(),
        "11月17日和11月19日文献管理软件讲座在哪里？现在还能参加吗？": set(),
    }
    modes = ["keyword"]
    if database.kw["bind"].dialect.name == "postgresql":
        modes.append("hybrid")
        process_batch(database, RetrievalSettings(dimensions=3), client=FakeEncoder())
    with database() as session:
        for mode in modes:
            settings = RetrievalSettings(mode=mode, dimensions=3)
            for question, expected in cases.items():
                diagnostics = {}
                rows = search_information(
                    session,
                    question,
                    now=NOW,
                    settings=settings,
                    embedding_client=FakeEncoder(),
                    diagnostics=diagnostics,
                )
                assert {row.source_id for row in rows} == expected, (mode, question)
                assert diagnostics["mode"] == mode
            # Relative dates use Beijing time across both UTC midnight and the year boundary.
            rows = search_information(
                session,
                "昨天文献管理软件讲座在哪里？现在还能参加吗？",
                now=datetime.fromisoformat("2027-01-01T16:30:00+00:00"),
                settings=settings,
                embedding_client=FakeEncoder(),
            )
            assert {row.source_id for row in rows} == {"new-year"}


def test_follow_up_rereads_past_notice_without_relaxing_new_time_or_room(database):
    corpus(database)
    with database() as session:
        record = session.scalar(
            select(InformationRecord).where(InformationRecord.source_id == "repair-yesterday")
        )
        identity = record.id
    messages = [
        {"role": "user", "content": "昨天的古籍修复讲座在哪？"},
        {
            "role": "assistant",
            "content": "图书馆208。[S1]",
            "citations": [
                {"rank": 1, "information_id": str(identity), "title": "古籍修复讲座回顾"},
            ],
        },
    ]
    modes = ["keyword"]
    if database.kw["bind"].dialect.name == "postgresql":
        modes.append("hybrid")
        process_batch(database, RetrievalSettings(dimensions=3), client=FakeEncoder())
    for mode in modes:
        config = RetrievalSettings(mode=mode, dimensions=3)
        with database() as session:
            for question in ("那现在还能参加吗？", "这个讲座现在还有机会参加吗？"):
                _, query, pinned = conversation_context(messages, question, NOW)
                diagnostics = {}
                rows = search_information(
                    session,
                    query,
                    pinned_ids=pinned,
                    now=NOW,
                    constraint_question=question,
                    settings=config,
                    embedding_client=FakeEncoder(),
                    diagnostics=diagnostics,
                )
                assert [r.id for r in rows] == [identity]
                assert diagnostics["mode"] == mode
                assert "活动已经结束" in rows[0].content
            for question in (
                "这个讲座现在正在进行吗？",
                "这个讲座明天几点开始？",
                "这个讲座在图书馆999吗？",
            ):
                _, query, pinned = conversation_context(messages, question, NOW)
                rows = search_information(
                    session,
                    query,
                    pinned_ids=pinned,
                    now=NOW,
                    constraint_question=question,
                    settings=config,
                    embedding_client=FakeEncoder(),
                )
                assert identity not in [r.id for r in rows]
    with database.begin() as session:
        session.execute(delete(InformationRecord).where(InformationRecord.id == identity))
    with database() as session:
        _, query, pinned = conversation_context(messages, "那现在还能参加吗？", NOW)
        rows = search_information(
            session,
            query,
            pinned_ids=pinned,
            now=NOW,
            constraint_question="那现在还能参加吗？",
            settings=config,
            embedding_client=FakeEncoder(),
        )
        # History cannot revive deleted sources or substitute a different event.
        assert not rows


def test_index_updates_deletes_retries_and_rebuild(database):
    corpus(database)
    settings = RetrievalSettings(dimensions=3)
    failing = FakeEncoder(failure=True)
    first = process_batch(database, settings, client=failing, now=NOW)
    assert first["failed"] == 18
    assert process_batch(database, settings, client=failing, now=NOW)["selected"] == 0
    working = FakeEncoder()
    assert (
        process_batch(database, settings, client=working, now=NOW + timedelta(seconds=3))["indexed"]
        == 18
    )
    assert process_batch(database, settings, client=working)["selected"] == 0
    with database.begin() as session:
        row = session.scalar(
            select(InformationRecord).where(InformationRecord.source_id == "math-101")
        )
        identity = row.id
        row.content = "课程变更后的公开资料。"
    with database() as session:
        state = session.get(RetrievalState, identity)
        assert state.revision == 2 and state.indexed_revision == 1
    assert process_batch(database, settings, client=working)["indexed"] == 1
    with database() as session:
        assert session.get(RetrievalChunk, (identity, 0)).body == "课程变更后的公开资料。"
    with database.begin() as session:
        session.execute(delete(InformationRecord).where(InformationRecord.id == identity))
    with database() as session:
        assert session.get(RetrievalState, identity) is None
        assert session.get(RetrievalChunk, (identity, 0)) is None
    assert rebuild(database) == 17
    assert process_batch(database, settings, client=working)["indexed"] == 17
    with database() as session:
        assert session.scalar(select(func.count()).select_from(RetrievalChunk)) == 17


def test_late_encoding_and_failed_information_transaction(database):
    corpus(database)
    with database() as session:
        identity = session.scalar(
            select(RetrievalState.information_id).order_by(RetrievalState.information_id)
        )

    def change_while_encoding():
        with database.begin() as session:
            session.execute(
                update(InformationRecord)
                .where(InformationRecord.id == identity)
                .values(content="新的正文")
            )

    result = process_batch(
        database,
        RetrievalSettings(dimensions=3),
        client=FakeEncoder(callback=change_while_encoding),
        batch_size=1,
    )
    assert result["superseded"] == 1
    with database() as session:
        assert session.get(RetrievalChunk, (identity, 0)) is None
    with pytest.raises(RuntimeError), database.begin() as session:
        session.execute(
            update(InformationRecord)
            .where(InformationRecord.id == identity)
            .values(content="应当回滚")
        )
        raise RuntimeError("rollback")
    with database() as session:
        assert session.get(RetrievalState, identity).revision == 2
        assert session.get(InformationRecord, identity).content == "新的正文"


def test_hybrid_failure_keeps_keywords_and_transaction_usable(database, caplog):
    corpus(database)
    config = RetrievalSettings(mode="hybrid", dimensions=3)
    with database() as session:
        rows = search_information(
            session, "图书续借办理指引", settings=config, embedding_client=FakeEncoder(failure=True)
        )
        assert rows[0].source_id == "library-renewal"
        assert "embedding_unavailable" in caplog.text
        assert session.scalar(select(func.count()).select_from(InformationRecord)) == 18


def test_vector_sql_error_falls_back_without_aborting_caller(database, monkeypatch):
    corpus(database)

    def broken_query(session, *args):
        session.execute(text("SELECT livelife_nonexistent_function()"))

    monkeypatch.setattr("app.services.agent.retrieval._vector_candidates", broken_query)
    diagnostics = {}
    with database.begin() as session:
        rows = search_information(
            session,
            "图书续借办理指引",
            settings=RetrievalSettings(mode="hybrid", dimensions=3),
            embedding_client=FakeEncoder(),
            diagnostics=diagnostics,
        )
        assert rows[0].source_id == "library-renewal"
        assert diagnostics["reason"] == "vector_query_failed"
        assert session.scalar(text("SELECT 1")) == 1


def test_real_vector_query_deduplicates_and_excludes_stale_profiles(database):
    if database.kw["bind"].dialect.name != "postgresql":
        pytest.skip("native pgvector query")
    corpus(database)
    config = RetrievalSettings(mode="hybrid", dimensions=3, min_similarity=0.9)
    encoder = FakeEncoder()
    process_batch(database, config, client=encoder)
    with database() as session:
        rows = search_information(
            session, "二教101现在上什么课", now=NOW, settings=config, embedding_client=encoder
        )
        assert [row.source_id for row in rows] == ["math-101"]
        citation = rows[0].citation(1)
        assert citation["activity_location"] == "第二教学楼101"
        assert citation["source_url"].endswith("math-101")
        assert citation["activity_start_at"] is not None
        rows = search_information(
            session,
            "不存在的语义测试",
            settings=replace(config, model_revision="new"),
            embedding_client=encoder,
        )
        assert rows == ()
    with database.begin() as session:
        session.execute(
            update(InformationRecord)
            .where(InformationRecord.source_id == "math-101")
            .values(content="替换")
        )
    with database() as session:
        from app.services.agent.retrieval import _vector_candidates
        from app.services.retrieval.constraints import constraints

        rows = _vector_candidates(
            session, constraints(session, "二教101现在上什么课", NOW), [1, 0, 0], config
        )
        assert rows == []
        # Roll back a real PostgreSQL failure to a savepoint, preserving caller state.
        with pytest.raises(Exception), session.begin_nested():
            session.execute(text("SELECT 'invalid'::vector"))
        assert session.scalar(text("SELECT 1")) == 1


def test_chunk_offsets_and_context(database):
    corpus(database)
    with database() as session:
        row = session.scalar(
            select(InformationRecord).where(InformationRecord.source_id == "math-101")
        )
        row.content = "第一段。\n" * 40 + "教室和时间仍需参考条目元数据。\n" * 40
        chunks = split_record(row, RetrievalSettings(chunk_chars=120, overlap_chars=20))
        assert len(chunks) > 2
        covered = set()
        for chunk in chunks:
            covered.update(range(chunk.start, chunk.end))
            assert chunk.body == row.content[chunk.start : chunk.end]
            assert chunk.information_id == row.id and chunk.source_url == row.source_url
            assert "第二教学楼101" in chunk.text and "2026-11-18" in chunk.text
            assert str(row.id) not in chunk.text and row.source_url not in chunk.text
        assert covered == set(range(len(row.content)))


@pytest.mark.parametrize("mode", ["keyword", "hybrid"])
def test_deep_match_keeps_introductory_facts_without_duplicate_sources(database, monkeypatch, mode):
    corpus(database)
    settings = RetrievalSettings(mode=mode, dimensions=3, chunk_chars=120, overlap_chars=20)
    with database.begin() as session:
        row = session.scalar(
            select(InformationRecord).where(InformationRecord.source_id == "library-renewal")
        )
        row.content = (
            "主讲人：测试讲者。\n" + "讲座背景介绍。\n" * 40 + "专题：贝叶斯劝说与信号博弈。\n"
        )
        identity = row.id

    def deep_match(session, *args):
        row = session.get(InformationRecord, identity)
        return [(row, split_record(row, settings)[-1].body, 0.1)]

    monkeypatch.setattr("app.services.agent.retrieval._vector_candidates", deep_match)
    with database() as session:
        rows = search_information(
            session,
            "贝叶斯劝说与信号博弈",
            settings=settings,
            embedding_client=FakeEncoder(),
        )
        assert len(rows) == 1
        assert rows[0].id == identity
        assert "主讲人：测试讲者" in rows[0].content
        assert "专题：贝叶斯劝说与信号博弈" in rows[0].content
        assert rows[0].content.count("主讲人：测试讲者") == 1

        rows = search_information(
            session, "主讲人测试讲者", settings=replace(settings, mode="keyword")
        )
        assert rows[0].content.count("主讲人：测试讲者") == 1


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"model": "wrong-model", "data": [{"index": 0, "embedding": [1, 0, 0]}]},
        {"data": []},
        {"data": [{"index": 0, "embedding": [0, 0, 0]}]},
        {"data": [{"index": 1, "embedding": [1, 0, 0]}]},
        {"data": [{"index": 0, "embedding": [1, 0]}]},
        {"data": [{"index": 0, "embedding": [True, 0, 0]}]},
    ],
)
def test_embedding_contract_rejects_invalid_vectors(payload):
    client = EmbeddingClient(
        RetrievalSettings(base_url="https://embedding.example.test/v1", dimensions=3),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)),
    )
    with pytest.raises(EmbeddingError):
        client.encode(["公开资料"])


def test_embedding_indices_and_query_instruction():
    import json

    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0, 3, 0]},
                    {"index": 0, "embedding": [2, 0, 0]},
                ]
            },
        )

    client = EmbeddingClient(
        RetrievalSettings(base_url="https://embedding.example.test/v1", dimensions=3),
        transport=httpx.MockTransport(respond),
    )
    assert client.encode(["甲", "乙"], query=True) == [[1, 0, 0], [0, 1, 0]]
    assert requests[0]["input"][0].startswith("Instruct:")
    client.encode(["甲", "乙"])
    assert requests[1]["input"] == ["甲", "乙"]


@pytest.mark.parametrize("vector", [[float("nan"), 0, 0], [float("inf"), 0, 0], [10**400, 0, 0]])
def test_embedding_rejects_nonfinite_and_overflow(vector):
    from app.services.retrieval.embeddings import validate_vector

    with pytest.raises(EmbeddingError):
        validate_vector(vector, 3)


def test_embedding_preflight_releases_locks_and_duplicate_skips_model(database, monkeypatch):
    from uuid import uuid4

    from sqlalchemy import event
    from test_agent import ACCOUNT_ID, seed_account, settings

    from app.db.models import AgentIpWindow
    from app.services.agent.service import begin_request, create_session, finish_request

    seed_account(database)
    corpus(database)
    config = settings(requests_per_minute=1)
    created = create_session(database, config, "retrieval", user_id=ACCOUNT_ID)
    connections = 0
    engine = database.kw["bind"]

    def checked_out(*args):
        nonlocal connections
        connections += 1

    def checked_in(*args):
        nonlocal connections
        connections -= 1

    def outside_transaction():
        assert connections == 0

    encoder = FakeEncoder(callback=outside_transaction)
    monkeypatch.setattr("app.services.agent.service.EmbeddingClient", lambda settings: encoder)
    monkeypatch.setattr(
        "app.services.agent.service.get_retrieval_settings",
        lambda: RetrievalSettings(mode="hybrid", dimensions=3),
    )
    event.listen(engine, "checkout", checked_out)
    event.listen(engine, "checkin", checked_in)
    request_id = uuid4()
    arguments = dict(
        token=created["session_token"],
        user_id=ACCOUNT_ID,
        content="图书续借办理指引",
        client_request_id=request_id,
        ip="retrieval",
    )
    try:
        result = begin_request(database, config, **arguments)
        assert encoder.calls == 1
        finish_request(
            database,
            config,
            token=created["session_token"],
            user_id=ACCOUNT_ID,
            request_id=result["assistant_message"]["request_id"],
            answer="请参考续借说明",
            status="completed",
            input_tokens=0,
            output_tokens=0,
            estimated_usage=False,
        )
        repeated = begin_request(database, config, **arguments)
        assert repeated["duplicate"]
        assert encoder.calls == 1
        with database() as session:
            # Creation, one encoded request, one replay; no double admission charge.
            assert session.scalar(select(AgentIpWindow.request_count)) == 3
    finally:
        event.remove(engine, "checkout", checked_out)
        event.remove(engine, "checkin", checked_in)


def test_ip_limit_rejects_embedding_before_model_call_and_resets_next_hour(database, monkeypatch):
    from datetime import UTC
    from uuid import uuid4

    from test_agent import ACCOUNT_ID, seed_account, settings

    from app.db.models import AgentIpWindow
    from app.services.agent.service import AgentError, begin_request, create_session

    seed_account(database)
    config = settings(ip_requests_per_hour=1)
    created = create_session(database, config, "embedding-limit", user_id=ACCOUNT_ID)
    encoder = FakeEncoder()
    monkeypatch.setattr("app.services.agent.service.EmbeddingClient", lambda _: encoder)
    monkeypatch.setattr(
        "app.services.agent.service.get_retrieval_settings",
        lambda: RetrievalSettings(mode="hybrid", dimensions=3),
    )
    arguments = dict(
        token=created["session_token"],
        user_id=ACCOUNT_ID,
        content="图书续借办理指引",
        ip="embedding-limit",
    )
    for _ in range(3):
        with pytest.raises(AgentError, match="ip_rate_limited"):
            begin_request(database, config, client_request_id=uuid4(), **arguments)
    assert encoder.calls == 0
    with database.begin() as session:
        window = session.scalar(select(AgentIpWindow))
        assert window.request_count == 1
        window.window_start = datetime.now(UTC) - timedelta(hours=1)
    result = begin_request(database, config, client_request_id=uuid4(), **arguments)
    assert not result["duplicate"] and encoder.calls == 1
    with database() as session:
        assert session.scalar(select(AgentIpWindow.request_count)) == 1


def test_concurrent_embedding_reserves_last_ip_slot_before_releasing_transaction(
    database, monkeypatch
):
    if database.kw["bind"].dialect.name != "postgresql":
        pytest.skip("concurrent PostgreSQL admission")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from uuid import uuid4

    from test_agent import ACCOUNT_ID, seed_account, settings

    from app.db.models import AgentIpWindow
    from app.services.agent.service import AgentError, begin_request, create_session

    seed_account(database)
    config = settings(ip_requests_per_hour=3)
    first = create_session(database, config, "concurrent-embedding", user_id=ACCOUNT_ID)
    second = create_session(database, config, "concurrent-embedding", user_id=ACCOUNT_ID)
    entered, release = Event(), Event()

    def wait_for_competitor():
        entered.set()
        assert release.wait(timeout=10)

    encoder = FakeEncoder(callback=wait_for_competitor)
    monkeypatch.setattr("app.services.agent.service.EmbeddingClient", lambda _: encoder)
    monkeypatch.setattr(
        "app.services.agent.service.get_retrieval_settings",
        lambda: RetrievalSettings(mode="hybrid", dimensions=3),
    )
    arguments = dict(user_id=ACCOUNT_ID, content="图书续借办理指引", ip="concurrent-embedding")
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(
            begin_request,
            database,
            config,
            token=first["session_token"],
            client_request_id=uuid4(),
            **arguments,
        )
        try:
            assert entered.wait(timeout=10)
            with database() as session:
                assert session.scalar(select(AgentIpWindow.request_count)) == 3
            with pytest.raises(AgentError, match="ip_rate_limited"):
                begin_request(
                    database,
                    config,
                    token=second["session_token"],
                    client_request_id=uuid4(),
                    **arguments,
                )
            assert encoder.calls == 1
        finally:
            release.set()
        assert not pending.result(timeout=10)["duplicate"]
    with database() as session:
        assert session.scalar(select(AgentIpWindow.request_count)) == 3


def test_late_admission_failure_does_not_refund_embedding_ip_slot(database, monkeypatch):
    from uuid import uuid4

    from test_agent import ACCOUNT_ID, seed_account, settings

    from app.db.models import AgentIpWindow
    from app.services.agent.service import AgentError, begin_request, create_session

    seed_account(database)
    config = settings(
        ip_requests_per_hour=2,
        daily_token_quota=1,
        llm_base_url="https://unused.invalid/v1",
        llm_api_key="synthetic",
        llm_model="synthetic",
    )
    created = create_session(database, config, "late-admission", user_id=ACCOUNT_ID)
    encoder = FakeEncoder()
    monkeypatch.setattr("app.services.agent.service.EmbeddingClient", lambda _: encoder)
    monkeypatch.setattr(
        "app.services.agent.service.get_retrieval_settings",
        lambda: RetrievalSettings(mode="hybrid", dimensions=3),
    )
    arguments = dict(
        token=created["session_token"],
        user_id=ACCOUNT_ID,
        content="图书续借办理指引",
        ip="late-admission",
    )
    with pytest.raises(AgentError, match="token_quota_exceeded"):
        begin_request(database, config, client_request_id=uuid4(), **arguments)
    with pytest.raises(AgentError, match="ip_rate_limited"):
        begin_request(database, config, client_request_id=uuid4(), **arguments)
    assert encoder.calls == 1
    with database() as session:
        assert session.scalar(select(AgentIpWindow.request_count)) == 2
