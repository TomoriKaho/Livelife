"""Small pgvector SQL type with a text representation for SQLite unit tests."""

import json

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator, UserDefinedType


class Vector(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw):
        return "VECTOR"


class Embedding(TypeDecorator):
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(Vector() if dialect.name == "postgresql" else Text())

    def process_bind_param(self, value, dialect):
        return json.dumps(value, allow_nan=False) if value is not None else None

    def process_result_value(self, value, dialect):
        return json.loads(value) if isinstance(value, str) else value
