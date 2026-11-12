from datetime import UTC, datetime

import pytest

from app.services.ingestion.official_events import parse_article

NOW = datetime(2026, 11, 12, tzinfo=UTC)


def article(body):
    return '<meta name="ArticleTitle" content="测试活动">' + body


def test_library_uses_event_time_and_complete_body_address():
    record = parse_article(
        "library",
        "https://lib.pku.edu.cn/hdrl/test.htm",
        article(
            "<p>发布时间：2026-11-01 12:00</p><p>时 间：2026-11-13 15:10 至 "
            "2026-11-13 17:00</p><p>地 点：科学报告厅</p>"
            "<p>地点：北京大学图书馆北配楼科学报告厅</p>"
        ),
        NOW,
    )
    assert record.activity_start_at.isoformat() == "2026-11-13T07:10:00+00:00"
    assert record.activity_end_at.isoformat() == "2026-11-13T09:00:00+00:00"
    assert record.activity_location == "北京大学图书馆北配楼科学报告厅"
    assert record.published_at is None
    assert record.raw_payload["parser_version"] == "pku-official-v1"


def test_hall_does_not_invent_end_time():
    record = parse_article(
        "hall",
        "https://hall.pku.edu.cn/test.htm",
        article("<p>时间：2026年11月13日（周五）19:00</p><p>地点：讲堂李莹厅</p>"),
        NOW,
    )
    assert record.activity_end_at is None
    assert record.activity_start_at.hour == 11


def test_math_keeps_multi_room_evidence():
    record = parse_article(
        "math",
        "https://math.pku.edu.cn/test.htm",
        article("<p>时间：2026-11-12 10:00-11:00</p><p>地点：智华楼四元厅-224,225室</p>"),
        NOW,
    )
    assert record.activity_location == "智华楼四元厅-224,225室"
    assert record.source_id == "test:event:1"


@pytest.mark.parametrize("body", ["请验证后访问", article("时间：待定 地点：待定")])
def test_missing_evidence_is_not_imported(body):
    with pytest.raises(ValueError):
        parse_article("library", "https://lib.pku.edu.cn/test.htm", body, NOW)


def test_external_url_is_rejected():
    with pytest.raises(ValueError):
        parse_article("library", "https://example.com/test.htm", "", NOW)
