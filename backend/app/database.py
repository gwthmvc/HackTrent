from __future__ import annotations

import logging
from contextlib import contextmanager
from threading import Lock
from typing import Iterator

from psycopg import Connection, Error as PsycopgError
from psycopg_pool import ConnectionPool

from .config import Settings
from .errors import DatabaseNotConfiguredError, DatabaseUnavailableError

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pool: ConnectionPool | None = None
        self._pool_lock = Lock()

    @property
    def configured(self) -> bool:
        return self._settings.database_url is not None

    def _get_pool(self) -> ConnectionPool:
        if not self._settings.database_url:
            raise DatabaseNotConfiguredError

        if self._pool is None:
            with self._pool_lock:
                if self._pool is None:
                    self._pool = ConnectionPool(
                        conninfo=self._settings.database_url.get_secret_value(),
                        min_size=0,
                        max_size=4,
                        open=False,
                        timeout=self._settings.database_connect_timeout_seconds,
                        kwargs={
                            "connect_timeout": self._settings.database_connect_timeout_seconds,
                            "sslmode": "require",
                        },
                    )
                    self._pool.open(wait=False)

        return self._pool

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        try:
            with self._get_pool().connection(
                timeout=self._settings.database_connect_timeout_seconds,
            ) as connection:
                yield connection
        except DatabaseNotConfiguredError:
            raise
        except PsycopgError as error:
            logger.error("TigerData operation failed (%s)", error.__class__.__name__)
            raise DatabaseUnavailableError from error

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
