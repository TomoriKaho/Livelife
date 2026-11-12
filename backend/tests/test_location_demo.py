from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.content_demo import create_demo


@pytest.fixture(scope="module")
def client():
    with TestClient(create_demo()) as client:
        yield client


@pytest.mark.parametrize(
    "text,place_id,room,floor",
    [
        ("理教 １０６", "pku:yanyuan:science-teaching", "106", None),
        ("北京大学理科教学楼二层B106教室", "pku:yanyuan:science-teaching", "B106", "二层"),
        ("图书馆培训教室208+在线", "pku:yanyuan:library", "208", None),
        ("第二教学楼（李兆基楼）207", "pku:yanyuan:teaching-2", "207", None),
        ("古籍图书馆", "pku:yanyuan:ancient-library", None, None),
        ("理教106/107", "pku:yanyuan:science-teaching", None, None),
        ("理教，2026年11月11日", "pku:yanyuan:science-teaching", None, None),
    ],
)
def test_resolves_aliases_with_evidence_and_building_precision(client, text, place_id, room, floor):
    response = client.get("/places/resolve", params={"text": text})
    assert response.status_code == 200
    result = response.json()
    resolution = result["resolution"]
    assert resolution["status"] == "matched"
    assert resolution["place_id"] == place_id
    assert resolution["room"] == room
    assert resolution["floor"] == floor
    assert resolution["evidence"] == text
    assert resolution["precision"] == "building"
    assert result["place"]["coordinate_system"] == "WGS84"
    assert result["place"]["id"] != result["place"]["building_id"]


@pytest.mark.parametrize("text", ["报告厅", "清华图书馆", "十一教106", "昌平校区理教106"])
def test_unknown_locations_do_not_receive_a_coordinate(client, text):
    result = client.get("/places/resolve", params={"text": text}).json()
    assert result["resolution"]["status"] == "unmatched"
    assert result["place"] is None


@pytest.mark.parametrize("text", ["教学楼106", "理教106、二教207"])
def test_ambiguity_returns_candidates_without_selecting_one(client, text):
    result = client.get("/places/resolve", params={"text": text}).json()
    assert result["resolution"]["status"] == "ambiguous"
    assert len(result["resolution"]["candidates"]) >= 2
    assert result["place"] is None


def test_ingestion_resolves_places_before_nearby_search_and_agent_read(client):
    articles = client.get("/information", params={"platform": "demo"}).json()
    resolved = next(item for item in articles if item["activity_location"] == "理教 106")
    assert resolved["location_resolution"]["room"] == "106"
    assert {item["location_resolution"]["status"] for item in articles} == {
        "matched",
        "ambiguous",
        "unmatched",
    }
    place = resolved["place"]
    # This is the exact CurrentLocation shape exported by PR #82.
    payload = {
        "location": {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "accuracy": 500,
            "timestamp": datetime.now(UTC).timestamp() * 1000,
            "heading": 90,
        },
        "radius_m": 1,
        "filters": {"platform": "demo", "keyword": "理教"},
    }
    response = client.post("/events/nearby", json=payload)
    assert response.status_code == 200
    assert response.json() == [resolved]
    payload["location"]["latitude"] += 0.002
    # Accuracy does not silently expand the user's search radius.
    assert client.post("/events/nearby", json=payload).json() == []
    chunks = client.get(f"/information/{resolved['id']}/chunks").json()
    assert chunks["information"]["location_resolution"] == resolved["location_resolution"]
    assert "理教" in client.get(f"/places/{place['id']}/aliases").json()


def test_nearby_rejects_stale_positions_and_invalid_coordinates(client):
    payload = {
        "location": {
            "latitude": 39.99,
            "longitude": 116.30,
            "accuracy": 10,
            "timestamp": datetime.now(UTC).timestamp() * 1000,
        },
        "radius_m": 100,
    }
    assert client.post("/events/nearby", json=payload).status_code == 200
    payload["location"]["timestamp"] = (datetime.now(UTC) - timedelta(minutes=3)).timestamp() * 1000
    assert client.post("/events/nearby", json=payload).status_code == 422

    payload["location"]["timestamp"] = datetime.now(UTC).timestamp() * 1000
    payload["location"]["latitude"] = 100
    assert client.post("/events/nearby", json=payload).status_code == 422
    payload["location"]["latitude"] = 39.99
    payload["filters"] = {"latitude": 39.99, "longitude": 116.30, "radius_m": 500}
    assert client.post("/events/nearby", json=payload).status_code == 422


def test_ingest_update_and_legacy_building_ids_use_same_catalogue(client):
    now = datetime.now(UTC)
    article = {
        "platform": "demo",
        "source_id": "update-location",
        "content": "合成测试条目",
        "fetched_at": now.isoformat(),
        "activity_location": "理教106",
        "place_id": "444991872",
    }
    response = client.post("/information", json=article)
    assert response.status_code == 200
    saved = response.json()
    assert saved["place_id"] == "pku:yanyuan:science-teaching"
    assert saved["location_resolution"]["room"] == "106"
    assert saved["location_resolution"]["method"] == "explicit"
    article.pop("place_id")
    article["activity_location"] = "报告厅"
    article["fetched_at"] = (now + timedelta(seconds=1)).isoformat()
    updated = client.post("/information", json=article).json()
    assert updated["id"] == saved["id"]
    assert updated["place_id"] is None and updated["place"] is None
    assert updated["location_resolution"]["room"] is None
    assert updated["location_resolution"]["status"] == "unmatched"
    article["fetched_at"] = now.isoformat()
    article["activity_location"] = "理教106"
    assert client.post("/information", json=article).json() == updated
    article["source_id"] = "bad-place"
    article["place_id"] = "unknown"
    assert client.post("/information", json=article).status_code == 422
    assert client.get("/information", params={"keyword": "合成测试条目"}).json() == [updated]
