"""Conservative, deterministic campus time/place constraints shared by both retrievers."""

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, true

from app.db.models import InformationRecord as I
from app.services.content.locations import LocationResolver, normalize_location

ZONE = ZoneInfo("Asia/Shanghai")
DATE_PATTERNS = (
    r"(?<![\d年])(?:(\d{4})年)?(\d{1,2})月(\d{1,2})(?:日|号)",
    r"(?<![\d-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\d-])",
)


@dataclass(frozen=True)
class QueryConstraints:
    clause: object
    aliases: tuple[str, ...] = ()
    structured: bool = False


def _event_day(text: str, local: datetime) -> tuple[date | None, bool]:
    """Resolve one supported day; reject invalid or ambiguous date anchors."""
    days = set()
    for pattern in DATE_PATTERNS:
        for year, month, day in re.findall(pattern, text):
            try:
                candidate = date(int(year) if year else local.year, int(month), int(day))
            except ValueError:
                return None, True
            if candidate == date.max:  # No representable next-day exclusive bound.
                return None, True
            days.add(candidate)
    for word, shift in (
        ("今天", 0),
        ("今日", 0),
        ("今晚", 0),
        ("明天", 1),
        ("明日", 1),
        ("昨天", -1),
    ):
        if word in text:
            days.add(local.date() + timedelta(days=shift))
    return (next(iter(days)) if len(days) == 1 else None), len(days) > 1


def constraints(
    session, question: str, now: datetime | None = None, *, reference_ids: tuple = ()
) -> QueryConstraints:
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("retrieval clock must include a timezone")
    local = now.astimezone(ZONE)
    normalized = normalize_location(question)
    clauses = []
    day, invalid_day = _event_day(normalized, local)
    time_text = normalized
    participation = False
    if day is not None or invalid_day or reference_ids:
        # A dated event plus a participation question needs the event notice first.
        # Only consume this bounded intent; another ongoing request stays strict.
        time_text, count = re.subn(
            r"(?:现在|此刻)(?:还)?(?:能否|能不能|可不可以|可以|能|来得及|有机会)"
            r"(?:再|去)?(?:参加|报名|入场|赶上|听)",
            "",
            time_text,
        )
        participation = bool(count)
    if participation and reference_ids:
        # Only re-read the referenced events; never broaden a current-state question
        # to arbitrary old notices. Room/date constraints still apply below.
        clauses.append(I.id.in_(reference_ids))
    if any(word in time_text for word in ("现在", "此刻", "正在")):
        clauses.append(and_(I.activity_start_at <= now, I.activity_end_at > now))
    elif invalid_day:
        clauses.append(I.id.is_(None))
    elif day is not None:
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
    prefixes = r"请问|想知道|查询|看看|今天|今日|今晚|明天|明日|昨天|现在|此刻|在|去|" + "|".join(
        DATE_PATTERNS
    )
    location_text = re.sub(
        rf"^(?:(?:{prefixes})[,，:：]?)+",
        "",
        normalized,
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
