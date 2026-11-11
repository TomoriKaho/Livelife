"""Run an isolated, local demonstration of the information service."""

import argparse
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from math import cos, radians
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated
from uuid import UUID

import uvicorn
from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import event, select

from app.db.models import MapPlaceRecord, PlaceAliasRecord
from app.db.session import Database
from app.schemas.information import (
    Information,
    InformationInput,
    InformationQuery,
    MapPlace,
    ShortText,
)
from app.schemas.location import NearbyEventsRequest, ResolvedPlace
from app.services.content import InformationAggregator, InformationProvider
from app.services.content.locations import LocationResolver, normalize_location
from app.services.content.retrieval import RetrievalDocument, retrieval_document
from app.services.ingestion import collect_information
from app.services.ingestion.wechat import WeChatSnapshotSource

BACKEND = Path(__file__).resolve().parents[1]
CAMPUS = BACKEND.parent / "frontend/src/assets/maps/campus.json"
# Place identity is independent of the map snapshot's building ID.
PLACE_SEEDS = {
    "pku:yanyuan:library": ("r3249649", ["图书馆", "北大图书馆"]),
    "pku:yanyuan:hall": ("188711087", ["讲堂", "百讲", "百周年纪念讲堂"]),
    "pku:yanyuan:science-teaching": ("444991872", ["理教", "理科教学楼", "黄廷方楼", "教学楼"]),
    "pku:yanyuan:teaching-1": ("226702307", ["一教", "第一教学楼", "教学楼"]),
    "pku:yanyuan:teaching-2": ("240825557", ["二教", "第二教学楼", "李兆基楼", "教学楼"]),
    "pku:yanyuan:teaching-3": ("240825556", ["三教", "第三教学楼", "刘卿楼", "教学楼"]),
    "pku:yanyuan:teaching-4": ("240825555", ["四教", "第四教学楼", "教学楼"]),
    "pku:yanyuan:ancient-library": ("628032101", ["古籍图书馆"]),
}


def demo_places() -> list[MapPlace]:
    campus = json.loads(CAMPUS.read_text(encoding="utf-8"))
    origin_lon, origin_lat = campus["origin"]
    places = []
    buildings = {building["id"]: building for building in campus["buildings"]}
    for place_id, (building_id, _aliases) in PLACE_SEEDS.items():
        building = buildings[building_id]
        points = building["points"]
        ring = points[:-1] if points[0] == points[-1] else points
        x = sum(point[0] for point in ring) / len(ring)
        z = sum(point[1] for point in ring) / len(ring)
        # Inverse of frontend/src/pages/map/geometry.mjs:project.
        places.append(
            MapPlace(
                id=place_id,
                building_id=building_id,
                name=building["name"],
                longitude=origin_lon + x / (111_320 * cos(radians(origin_lat))),
                latitude=origin_lat - z / 111_320,
            )
        )
    return places


def demo_items() -> list[InformationInput]:
    # Short editorial summaries transcribed from the linked official pages.
    captured_at = datetime.fromisoformat("2026-11-09T19:29:47+00:00")
    return [
        InformationInput(
            platform="pku_website",
            source_id="library:0a32a64919294d338dd72b58de36d348",
            source_url="https://lib.pku.edu.cn/hdrl/0a32a64919294d338dd72b58de36d348.htm",
            source_name="北京大学图书馆",
            title="数据可视化快速入门：工具、示例和学习资源",
            content="图书馆讲座，介绍数据可视化工具、示例和学习资源。讲座同步在线举行。",
            activity_start_at="2026-11-09T15:10:00+08:00",
            activity_end_at="2026-11-09T16:40:00+08:00",
            activity_location="图书馆培训教室208+在线",
            fetched_at=captured_at,
        ),
        InformationInput(
            platform="pku_website",
            source_id="hall:e1020fa7bc6f463facebacabd50c5340",
            source_url=("https://hall.pku.edu.cn/hdgp/zxyc/l/e1020fa7bc6f463facebacabd50c5340.htm"),
            source_name="北京大学百周年纪念讲堂",
            title="尤泓斐2026年北大艺术之旅 致敬威尔第专场",
            content="北京大学会议中心主办的威尔第作品演出，曲目包含歌剧选段。",
            activity_start_at="2026-11-07T19:00:00+08:00",
            activity_location="讲堂李莹厅",
            fetched_at=captured_at,
        ),
    ] + [
        InformationInput(
            platform="demo",
            source_id=f"location:{index}",
            title=f"地点解析演示 · {location}",
            content="用于验证地点解析与附近筛选的合成活动。",
            activity_location=location,
            activity_start_at="2026-11-11T19:00:00+08:00",
            fetched_at=captured_at,
        )
        for index, location in enumerate(["理教 106", "教学楼106", "报告厅"])
    ]


def create_demo(wechat_json: Path | None = None) -> FastAPI:
    database: Database
    places = demo_places()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        nonlocal database
        with TemporaryDirectory(prefix="livelife-content-") as directory:
            database = Database(f"sqlite+pysqlite:///{directory}/demo.db")
            assert database.engine is not None and database.session_factory is not None

            @event.listens_for(database.engine, "connect")
            def enable_foreign_keys(connection, _record) -> None:
                connection.execute("PRAGMA foreign_keys=ON")

            try:
                config = Config(str(BACKEND / "alembic.ini"))
                with database.engine.begin() as connection:
                    config.attributes["connection"] = connection
                    command.upgrade(config, "head")
                with database.session_factory.begin() as session:
                    session.add_all(
                        [
                            MapPlaceRecord(**place.model_dump(exclude={"coordinate_system"}))
                            for place in places
                        ]
                    )
                    session.flush()
                    session.add_all(
                        [
                            PlaceAliasRecord(place_id=place_id, alias=normalize_location(alias))
                            for place_id, (_building_id, aliases) in PLACE_SEEDS.items()
                            for alias in set(aliases)
                        ]
                    )
                with database.session_factory() as session:
                    InformationAggregator(session).ingest(demo_items())
                if wechat_json is not None:
                    with database.session_factory() as session:
                        collect_information(
                            WeChatSnapshotSource(wechat_json), InformationAggregator(session)
                        )
                yield
            finally:
                database.close()

    app = FastAPI(title="Livelife 信息系统 Demo", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:8775", "http://localhost:8775"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Accept"],
    )

    @app.get("/places")
    def list_places() -> list[MapPlace]:
        with database.session_factory() as session:
            return [
                MapPlace.model_validate(p)
                for p in session.scalars(select(MapPlaceRecord).order_by(MapPlaceRecord.id))
            ]

    @app.get("/places/resolve")
    def resolve_place(text: Annotated[ShortText, Query()]) -> ResolvedPlace:
        with database.session_factory() as session:
            resolver = LocationResolver(session)
            resolution = resolver.resolve(text)
            return ResolvedPlace(resolution=resolution, place=resolver.place(resolution.place_id))

    @app.get("/places/{place_id}/aliases")
    def place_aliases(place_id: str) -> list[str]:
        with database.session_factory() as session:
            if session.get(MapPlaceRecord, place_id) is None:
                raise HTTPException(status_code=404, detail="Place not found")
            return list(
                session.scalars(
                    select(PlaceAliasRecord.alias)
                    .where(PlaceAliasRecord.place_id == place_id)
                    .order_by(PlaceAliasRecord.alias)
                )
            )

    @app.get("/information")
    def list_information(query: Annotated[InformationQuery, Query()]) -> tuple[Information, ...]:
        with database.session_factory() as session:
            return InformationProvider(session).list(query)

    @app.post("/information")
    def ingest_information(record: InformationInput) -> Information:
        with database.session_factory() as session:
            try:
                return InformationAggregator(session).ingest([record])[0]
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/events")
    def list_events(query: Annotated[InformationQuery, Query()]) -> tuple[Information, ...]:
        """Return events with a known start and a mapped place."""
        return list_information(query.model_copy(update={"events_only": True}))

    @app.post("/events/nearby")
    def nearby_events(request: NearbyEventsRequest) -> tuple[Information, ...]:
        age_ms = datetime.now(UTC).timestamp() * 1000 - request.location.timestamp
        if age_ms > 120_000 or age_ms < -10_000:
            raise HTTPException(status_code=422, detail="Refresh location before searching nearby")
        try:
            query = request.query()
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return list_information(query)

    @app.get("/information/{information_id}/chunks")
    def get_chunks(information_id: UUID) -> RetrievalDocument:
        with database.session_factory() as session:
            information = InformationProvider(session).get(information_id)
        if information is None:
            raise HTTPException(status_code=404, detail="Information not found")
        return retrieval_document(information)

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18763)
    parser.add_argument("--wechat-json", type=Path)
    args = parser.parse_args()
    uvicorn.run(create_demo(args.wechat_json), host="127.0.0.1", port=args.port)
