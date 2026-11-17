"""Extractive within-conversation recall; old answers never become new evidence."""

import json
from uuid import UUID
from zoneinfo import ZoneInfo

from app.services.agent.retrieval import _terms


def conversation_context(messages, question, now, location=None):
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
    follow_up = any(
        word in question for word in ("这个", "这门", "这位", "那门", "之前", "刚才", "它", "那个")
    )
    pinned = []
    hints = []
    if follow_up:
        hints.extend(message["content"][:500] for message in messages[-2:])
        for i in sorted(anchors):
            if messages[i]["role"] == "user":
                hints.append(messages[i]["content"][:500])
            for source in messages[i].get("citations", []):
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
    return history, " ".join(hints + [question]), tuple(dict.fromkeys(pinned))
