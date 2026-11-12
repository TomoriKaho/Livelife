"""Resolve extracted campus location text against the shared place catalogue."""

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MapPlaceRecord, PlaceAliasRecord
from app.schemas.information import LocationResolution, MapPlace


def normalize_location(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text).casefold())


def room_and_floor(suffix: str) -> tuple[str | None, str | None]:
    suffix = suffix.lstrip(" ,，:：")
    floor_match = re.match(r"(?:地下)?第?[一二三四五六七八九十0-9]+(?:层|楼)", suffix)
    floor = floor_match[0] if floor_match else None
    if floor_match:
        suffix = suffix[floor_match.end() :].lstrip(" ,，:：")
    room_match = re.match(
        r"(?:(?:培训)?教室|会议室|房间)?([a-z]?\d{2,4}[a-z]?)(?![年月日:])(?=$|[^a-z0-9])",
        suffix,
    )
    room = room_match[1].upper() if room_match else None
    # A single room field cannot represent a list or range of rooms.
    if room_match and re.match(r"(?:室)?[/、,，和及至-][a-z]?\d", suffix[room_match.end() :]):
        room = None
    return room, floor


class LocationResolver:
    def __init__(self, session: Session) -> None:
        self.places = {p.id: p for p in session.scalars(select(MapPlaceRecord))}
        self.aliases = [(normalize_location(p.name), p.id) for p in self.places.values()]
        self.aliases.extend(
            (normalize_location(a.alias), a.place_id)
            for a in session.scalars(select(PlaceAliasRecord))
        )

    def resolve(self, text: str | None, explicit_place_id: str | None = None) -> LocationResolution:
        normalized = normalize_location(text or "")
        matches = []
        for alias, place_id in self.aliases:
            for match in re.finditer(re.escape(alias), normalized):
                prefix = normalized[: match.start()]
                # Match extracted locations or delimited mentions, not suffixes of other
                # institutions (e.g. 清华图书馆 must not resolve to 北大图书馆).
                if prefix and not (
                    prefix[-1] in " ,，:：;；、/+(（和及在于"
                    or prefix.endswith(("北京大学", "北大"))
                ):
                    continue
                matches.append((match.start(), match.end(), alias, place_id))
        # Prefer a full building name over shorter aliases contained in that name.
        matches = [
            m
            for m in matches
            if not any(n[0] <= m[0] and m[1] <= n[1] and n[1] - n[0] > m[1] - m[0] for n in matches)
        ]
        candidates = sorted({m[3] for m in matches})
        method = "alias"
        if explicit_place_id is not None:
            # Accept old Demo building IDs while new entries use independent place IDs.
            explicit = (
                [explicit_place_id]
                if explicit_place_id in self.places
                else [p.id for p in self.places.values() if p.building_id == explicit_place_id]
            )
            if len(explicit) != 1:
                raise ValueError("place_id must identify one registered place")
            candidates = explicit
            method = "explicit"
        if len(candidates) != 1:
            return LocationResolution(
                status="ambiguous" if candidates else "unmatched",
                candidates=tuple(candidates),
                evidence=text,
            )
        place_id = candidates[0]
        matched = [m for m in matches if m[3] == place_id]
        room, floor = (None, None)
        alias = None
        if len({(m[0], m[1]) for m in matched}) == 1:
            match = matched[0]
            alias = match[2]
            room, floor = room_and_floor(normalized[match[1] :])
        return LocationResolution(
            status="matched",
            place_id=place_id,
            room=room,
            floor=floor,
            precision="building",
            method=method,
            matched_alias=alias,
            evidence=text,
        )

    def place(self, place_id: str | None) -> MapPlace | None:
        record = self.places.get(place_id)
        return MapPlace.model_validate(record) if record is not None else None
