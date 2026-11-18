"""Conservative, deterministic campus time/place constraints shared by both retrievers."""

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, true

from app.db.models import InformationRecord as I
from app.services.content.locations import LocationResolver, normalize_location

ZONE = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class QueryConstraints:
    clause: object
    aliases: tuple[str, ...] = ()
    structured: bool = False


def constraints(session, question: str, now: datetime | None = None) -> QueryConstraints:
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("retrieval clock must include a timezone")
    local = now.astimezone(ZONE)
    normalized = normalize_location(question)
    clauses = []
    if any(word in normalized for word in ("现在", "此刻", "正在")):
        clauses.append(and_(I.activity_start_at <= now, I.activity_end_at > now))
    elif any(word in normalized for word in ("今天", "今日", "今晚", "明天", "明日", "昨天")):
        shift = (
            1
            if any(w in normalized for w in ("明天", "明日"))
            else -1
            if "昨天" in normalized
            else 0
        )
        day = local.date() + timedelta(days=shift)
        evening = "今晚" in normalized or "晚上" in normalized
        start = datetime.combine(day, time(18 if evening else 0), ZONE)
        end = datetime.combine(day + timedelta(days=1), time.min, ZONE)
        overlapping = and_(
            I.activity_start_at < end,
            or_(
                I.activity_end_at > start,
                and_(I.activity_end_at.is_(None), I.activity_start_at >= start),
            ),
        )
        clauses.append(
            overlapping
            if evening
            else or_(overlapping, and_(I.activity_start_at.is_(None), I.activity_date == day))
        )
    resolver = LocationResolver(session)
    # Strip explicit question/time prefixes, preserving the resolver's foreign-place
    # and ambiguity rules. Unknown place names are never guessed from embeddings.
    location_text = re.sub(
        r"^(?:(?:请问|想知道|查询|看看|今天|今日|今晚|明天|明日|昨天|现在|此刻|在|去)\s*)+",
        "",
        unicodedata.normalize("NFKC", question),
    )
    resolved = resolver.resolve(location_text)
    aliases = ()
    if resolved.status == "ambiguous":
        # An ambiguous building cannot establish an exact room/location constraint.
        clauses.append(I.id.is_(None))
    elif resolved.status == "unmatched" and re.search(
        r"(?:教|楼|教室|会议室)[a-z]?\d{2,4}", normalized
    ):
        # Missing catalogue or an unknown explicit room must not silently become
        # an unconstrained semantic query across other classrooms.
        clauses.append(I.id.is_(None))
    elif resolved.status == "matched":
        # Shared aliases such as 教学楼 cannot identify a particular building.
        owners = {}
        for alias, place_id in resolver.aliases:
            owners.setdefault(alias, set()).add(place_id)
        aliases = tuple(sorted(a for a, ids in owners.items() if ids == {resolved.place_id}))
        location = func.lower(func.coalesce(I.activity_location, ""))
        for char in (" ", "\t", "\n", "\r", "\u3000"):
            location = func.replace(location, char, "")
        for digit in range(10):
            location = func.replace(location, chr(0xFF10 + digit), str(digit))
        alias_pattern = (
            "(?:" + "|".join(re.escape(a) for a in sorted(aliases, key=len, reverse=True)) + ")"
        )
        clauses.append(or_(I.place_id == resolved.place_id, location.regexp_match(alias_pattern)))
        if resolved.room:
            # The room must follow the selected building; a bare 101 elsewhere in
            # the article or inside 1101 is not evidence for this room.
            pattern = (
                alias_pattern
                + r"(?:(?:地下)?第?[一二三四五六七八九十0-9]+(?:层|楼))?"
                + r"(?:(?:培训)?教室|会议室|房间)?"
                + re.escape(resolved.room.lower())
                + r"(?=$|[^a-z0-9])"
            )
            clauses.append(location.regexp_match(pattern))
    codes = re.findall(
        r"(?<![a-z0-9])[a-z]{2,}\d{2,}[a-z]?(?![a-z0-9])",
        unicodedata.normalize("NFKC", question).lower(),
    )
    for code in codes:
        pattern = r"(^|[^a-z0-9])" + re.escape(code) + r"($|[^a-z0-9])"
        clauses.append(
            or_(
                func.lower(I.title).regexp_match(pattern),
                func.lower(I.content).regexp_match(pattern),
            )
        )
    return QueryConstraints(and_(*clauses) if clauses else true(), aliases, bool(clauses))
