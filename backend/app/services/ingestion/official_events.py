"""Explicit, bounded collection from three PKU publishers; no API-startup crawling."""

import argparse
import hashlib
import json
import re
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from app.db.session import Database
from app.schemas.information import InformationInput
from app.services.content.aggregation import InformationAggregator
from app.services.content.catalog import register_places
from app.services.content.locations import LocationResolver

SOURCES = {
    "library": ("lib.pku.edu.cn", "北京大学图书馆"),
    "hall": ("hall.pku.edu.cn", "北京大学百周年纪念讲堂"),
    "math": ("math.pku.edu.cn", "北京大学数学科学学院"),
}
MANIFEST = Path(__file__).with_name("official_events.json")
VERSION = "pku-official-v1"


class ArticleHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.meta = {}
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style"}:
            self.skip += 1
        if tag == "meta":
            self.meta[attrs.get("name", "")] = attrs.get("content", "")
        if tag in {"p", "div", "br", "h2", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip - 1)
        if tag in {"p", "div", "h2", "li"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    @property
    def text(self):
        return "\n".join(" ".join(x.split()) for x in "".join(self.parts).splitlines() if x.strip())


def required(pattern, text):
    match = re.search(pattern, text)
    if match is None:
        raise ValueError(f"Source layout changed / missing evidence: {pattern}")
    return match


def parse_article(source: str, url: str, html: str, fetched_at: datetime) -> InformationInput:
    host, name = SOURCES[source]
    if urlsplit(url).scheme != "https" or urlsplit(url).hostname != host:
        raise ValueError("URL is not an allowed direct publisher")
    document = ArticleHTML()
    document.feed(html)
    text = document.text
    title = document.meta.get("ArticleTitle", "").strip()
    if not title or title == "null":
        raise ValueError("Missing article title; possible verification page")
    end = None
    if source == "library":
        evidence = required(
            r"时\s*间：\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*至\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})",
            text,
        )
        start, end = (datetime.fromisoformat(v + "+08:00") for v in evidence.groups())
        # Prefer the complete address in the body, rather than a context-free room name.
        location = required(r"地点：\s*([^\n]*图书馆[^\n]*)", text).group(1)
    elif source == "math":
        evidence = required(
            r"时间：\s*(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})", text
        )
        date, begin, finish = evidence.groups()
        start = datetime.fromisoformat(f"{date}T{begin}+08:00")
        end = datetime.fromisoformat(f"{date}T{finish}+08:00")
        location = required(r"地点：\s*([^\n]+)", text).group(1)
    else:
        evidence = required(
            r"时间：\s*(\d{4})年(\d{1,2})月(\d{1,2})日[^\n\d]*(\d{1,2}):(\d{2})", text
        )
        year, month, day, hour, minute = map(int, evidence.groups())
        start = datetime.fromisoformat(f"{year:04}-{month:02}-{day:02}T{hour:02}:{minute:02}+08:00")
        location = required(r"地点：\s*([^\n]+)", text).group(1)
    # Keep the factual event excerpt in searchable content; complete HTML stays in local snapshots.
    content = f"{title}\n{evidence.group(0)}\n地点：{location}"
    return InformationInput(
        platform=f"pku_{source}",
        source_id=Path(urlsplit(url).path).stem + ":event:1",
        source_url=url,
        source_name=name,
        title=title,
        content=content,
        fetched_at=fetched_at,
        activity_location=location,
        activity_start_at=start,
        activity_end_at=end,
        activity_date=start.date(),
        raw_payload={
            "article_url": url,
            "event_key": "1",
            "parser_version": VERSION,
            "html_sha256": hashlib.sha256(html.encode()).hexdigest(),
            "time_evidence": evidence.group(0),
            "location_evidence": location,
            "review_status": "parsed",
            "timezone": "Asia/Shanghai",
        },
    )


def collect(manifest: Path, output: Path) -> list[InformationInput]:
    entries = json.loads(manifest.read_text(encoding="utf-8"))
    if not 1 <= len(entries) <= 20:
        raise ValueError("Choose 1–20 article URLs per batch")
    output.mkdir(parents=True, exist_ok=True)
    records, failures = [], []
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        for entry in entries:
            source, url = entry["source"], entry["url"]
            if urlsplit(url).hostname != SOURCES[source][0] or urlsplit(url).scheme != "https":
                raise ValueError("Only configured publisher URLs are accepted")
            try:
                for attempt in range(3):
                    try:
                        response = client.get(url)
                        response.raise_for_status()
                        break
                    except (httpx.TransportError, httpx.HTTPStatusError):
                        if attempt == 2:
                            raise
                        time.sleep(attempt + 1)
                html = response.content.decode("utf-8")
                fetched = datetime.now(UTC)
                digest = hashlib.sha256(html.encode()).hexdigest()
                (output / f"{digest}.html").write_text(html, encoding="utf-8")
                record = parse_article(source, url, html, fetched)
                records.append(record)
                print(f"Collected {source}: {record.title}")
            except (ValueError, httpx.HTTPError) as exc:
                failures.append({"url": url, "error": str(exc)})
            time.sleep(0.3)
    (output / "records.json").write_text(
        json.dumps([r.model_dump(mode="json") for r in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output / "failures.json").write_text(
        json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if failures:
        raise ValueError(
            f"{len(failures)} articles require review; no database import. See {output}"
        )
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--output", type=Path, default=Path(".local/official-events"))
    parser.add_argument(
        "--import-records", type=Path, help="Replay previously collected records without network"
    )
    parser.add_argument("--write", action="store_true", help="Explicitly import into DATABASE_URL")
    args = parser.parse_args()
    records = (
        [InformationInput.model_validate(r) for r in json.loads(args.import_records.read_text())]
        if args.import_records
        else collect(args.manifest, args.output)
    )
    if args.write:
        database = Database.from_environment()
        if database.session_factory is None:
            raise RuntimeError("Set a migrated development DATABASE_URL first")
        try:
            with database.session_factory.begin() as session:
                register_places(session)
                resolver = LocationResolver(session)
                unresolved = [
                    r.source_id
                    for r in records
                    if resolver.resolve(r.activity_location).status != "matched"
                ]
                if unresolved:
                    raise ValueError(f"Review unresolved places before importing: {unresolved}")
            with database.session_factory() as session:
                result = InformationAggregator(session).ingest(records)
            print(
                f"Imported {len(result)} events from {len({r.platform for r in result})} publishers"
            )
        finally:
            database.close()


if __name__ == "__main__":
    main()
