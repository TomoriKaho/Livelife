"""Extractive within-conversation recall; old answers never become new evidence."""

import json
import re
from uuid import UUID
from zoneinfo import ZoneInfo

from app.services.agent.retrieval import _terms


def _topic_switch(question):
    return any(marker in question for marker in ("换个话题", "换一个话题", "另一个问题", "改问"))


def _follow_up(question):
    if _topic_switch(question):
        return False
    if any(
        word in question
        for word in (
            "这个",
            "这门",
            "这位",
            "那门",
            "之前",
            "刚才",
            "它",
            "那个",
            "这场",
            "那场",
            "前一个",
            "后一个",
            "前者",
            "后者",
        )
    ):
        return True
    # Bounded elliptical questions, not arbitrary new questions with shared words.
    compact = re.sub(r"[\s，,。.!！?？]", "", question)
    return bool(
        re.fullmatch(
            r"(?:那|那么|所以|请问)?(?:现在|此刻)?"
            r"(?:(?:还)?(?:能|能否|能不能|可以|来得及|有机会)(?:去)?(?:参加|报名|入场|听)"
            r"|(?:需要|要|用不用|需不需要)(?:提前)?(?:报名|预约|带什么|带啥|带电脑)"
            r"|(?:有|有没有)(?:回放|录像)|几点(?:开始|结束)|在哪里|在哪)"
            r"(?:吗|么|呢|啊)?",
            compact,
        )
    )


def _referenced_sources(message):
    sources = message.get("citations", [])
    used = {int(rank) for rank in re.findall(r"\[S(\d+)\]", message.get("content", ""))}
    # When the answer cites specific records, don't pin every candidate it received.
    return [s for n, s in enumerate(sources, 1) if not used or s.get("rank", n) in used]


def conversation_context(messages, question, now, location=None):
    # A follow-up to a new topic must not revive the previous topic's source anchor.
    topic_start = next(
        (
            i
            for i in range(len(messages) - 1, -1, -1)
            if messages[i]["role"] == "user" and _topic_switch(messages[i]["content"])
        ),
        0,
    )
    messages = messages[topic_start:]
    terms = _terms(question)
    recent_start = max(0, len(messages) - 8)
    anchors = set()
    # Recall the latest source-backed task, even after >8 intervening messages.
    cited = next(
        (i for i in range(len(messages) - 1, -1, -1) if messages[i].get("citations")), None
    )
    if cited is not None:
        anchors.add(cited)
        if cited:
            anchors.add(cited - 1)
    ranked = sorted(
        range(recent_start),
        key=lambda i: sum(term in messages[i].get("content", "").casefold() for term in terms),
        reverse=True,
    )
    for i in ranked[:2]:
        if any(term in messages[i].get("content", "").casefold() for term in terms):
            anchors.add(i)
    selected = sorted(anchors | set(range(recent_start, len(messages))))
    history = [
        {"role": messages[i]["role"], "content": messages[i]["content"], "priority": i in anchors}
        for i in selected
    ]
    follow_up = _follow_up(question)
    pinned = []
    hints = []
    if follow_up:
        hints.extend(message["content"][:500] for message in messages[-2:])
        for i in sorted(anchors):
            if messages[i]["role"] == "user":
                hints.append(messages[i]["content"][:500])
            for source in _referenced_sources(messages[i]):
                try:
                    pinned.append(UUID(str(source["information_id"])))
                except (KeyError, ValueError):
                    continue
                hints.append(source.get("title") or "")
    runtime = {
        "received_at": now.isoformat(),
        "time_zone": "Asia/Shanghai",
        "local_time": now.astimezone(ZoneInfo("Asia/Shanghai")).isoformat(),
    }
    if location and -10000 <= now.timestamp() * 1000 - location["timestamp"] <= 120000:
        runtime["location"] = location
    # Ephemeral: neither the coordinate snapshot nor this wrapper is persisted.
    history.append(
        {
            "role": "user",
            "content": question
            + "\n<current_context>"
            + json.dumps(runtime, ensure_ascii=False)
            + "</current_context>",
        }
    )
    return history, " ".join([question] + hints), tuple(dict.fromkeys(pinned))
