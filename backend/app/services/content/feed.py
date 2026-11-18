from sqlalchemy.orm import Session

from app.schemas.content_feed import ContentArticle, ContentPage, ContentQuery
from app.schemas.information import InformationQuery
from app.services.content.provider import InformationProvider


def excerpt(content: str) -> str:
    # Adapters supply text, not HTML. Parsing again would erase comparisons and
    # generic type parameters. Clients must render this excerpt as text as well.
    text = " ".join(content.split())
    return text[:300] + ("…" if len(text) > 300 else "")


def list_articles(session: Session, query: ContentQuery) -> ContentPage:
    records = InformationProvider(session).list(
        InformationQuery(**query.model_dump(exclude={"limit"}), limit=query.limit + 1)
    )
    return ContentPage(
        items=[
            ContentArticle(
                **record.model_dump(
                    include={
                        "id",
                        "title",
                        "platform",
                        "source_name",
                        "source_url",
                        "published_at",
                        "fetched_at",
                    }
                ),
                excerpt=excerpt(record.content),
            )
            for record in records[: query.limit]
        ],
        next_offset=query.offset + query.limit if len(records) > query.limit else None,
    )
