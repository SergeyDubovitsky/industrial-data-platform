from __future__ import annotations

import http.client
import os
from dataclasses import dataclass
from urllib.parse import urlencode

from idp_telemetry_store.migrations import MigrationError


@dataclass(frozen=True)
class ClickHouseSettings:
    host: str
    http_port: int
    database: str
    user: str
    password: str
    secure: bool

    @classmethod
    def from_env(cls) -> ClickHouseSettings:
        return cls(
            host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            http_port=int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123")),
            database=os.getenv("CLICKHOUSE_DATABASE", "idp"),
            user=os.getenv("CLICKHOUSE_USER", "idp"),
            password=os.getenv("CLICKHOUSE_PASSWORD", "change-me-local-clickhouse"),
            secure=os.getenv("CLICKHOUSE_SECURE", "false").lower()
            in {"1", "true", "yes", "on"},
        )


class HttpClickHouseClient:
    def __init__(self, settings: ClickHouseSettings) -> None:
        self._settings = settings

    def execute(self, sql: str) -> str:
        params = urlencode(
            {
                "database": self._settings.database,
                "user": self._settings.user,
                "password": self._settings.password,
            }
        )
        response_body = ""
        for statement in _split_statements(sql):
            response_body = self._execute_statement(statement, params)
        return response_body

    def _execute_statement(self, sql: str, params: str) -> str:
        connection_cls = (
            http.client.HTTPSConnection
            if self._settings.secure
            else http.client.HTTPConnection
        )
        connection = connection_cls(
            self._settings.host,
            self._settings.http_port,
            timeout=30,
        )
        try:
            connection.request(
                "POST",
                f"/?{params}",
                body=sql.encode("utf-8"),
                headers={"Content-Type": "text/plain; charset=utf-8"},
            )
            response = connection.getresponse()
            body = response.read().decode("utf-8")
        finally:
            connection.close()

        if response.status >= 400:
            raise MigrationError(
                f"ClickHouse query failed with HTTP {response.status}: {body}"
            )
        return body


def _split_statements(sql: str) -> list[str]:
    statements = [statement.strip() for statement in sql.split(";")]
    return [statement for statement in statements if statement]
