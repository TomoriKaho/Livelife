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
    assert record.raw_payload["parser_version"] == "pku-official-v2"
    assert record.raw_payload["text_scope"] == "event_excerpt"


def test_library_spaced_location_and_article_text_exclude_page_chrome():
    record = parse_article(
        "library",
        "https://lib.pku.edu.cn/hdrl/test.htm",
        article(
            '<nav>导航干扰</nav><div class="info_box"><div class="info">'
            "<div>时 间：2026-11-19 15:10 至 2026-11-19 16:40</div>"
            "<div>地 点：图书馆培训教室208+在线</div><div>主讲人：测试老师</div>"
            '</div></div><div class="article fs16"><p>介绍科研检索与知识整理。</p>'
            "<div><p>请自备电脑。</p></div><script>脚本干扰</script>"
            '<style>样式干扰</style><img src="poster.png"/></div><footer>页脚干扰</footer>'
        ),
        NOW,
    )
    assert record.activity_location == "图书馆培训教室208+在线"
    assert "主讲人：测试老师" in record.content
    assert "介绍科研检索与知识整理。" in record.content
    assert "请自备电脑。" in record.content
    assert "干扰" not in record.content
    assert record.raw_payload["text_scope"] == "article_containers"


@pytest.mark.parametrize(
    ("source", "host", "container", "time"),
    [
        ("math", "math.pku.edu.cn", "capusList", "2026-11-19 16:00-17:00"),
        ("hall", "hall.pku.edu.cn", "infoBox", "2026年11月19日（周四）19:00"),
    ],
)
def test_publisher_article_containers_preserve_details(source, host, container, time):
    record = parse_article(
        source,
        f"https://{host}/test.htm",
        article(
            f'<div class="{container}"><p>时间：{time}</p><p>地点：测试厅</p>'
            "<p>讲者：测试人</p><div>摘要：测试主题。</div></div><div>页脚干扰</div>"
        ),
        NOW,
    )
    assert "讲者：测试人" in record.content
    assert "摘要：测试主题。" in record.content
    assert "页脚干扰" not in record.content


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
