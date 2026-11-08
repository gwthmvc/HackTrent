from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Protocol

from psycopg import sql
from psycopg.rows import dict_row

from .config import Settings
from .database import Database
from .errors import SchemaVerificationError


@dataclass(frozen=True, slots=True)
class PositionRecord:
    vehicle_id: str
    agency: str
    route_id: str | None
    latitude: float
    longitude: float
    observed_at: datetime


class TransitPositionReader(Protocol):
    def latest_positions(self, agency_value: str) -> list[PositionRecord]: ...


@dataclass(frozen=True, slots=True)
class VerifiedBusPositionsSchema:
    agency: str
    vehicle_id: str
    route: str
    latitude: str
    longitude: str
    observed_at: str


COLUMN_CANDIDATES = {
    "agency": ("agency_id", "agency"),
    "vehicle_id": ("vehicle_id", "vehicle"),
    "route": ("route_id", "route_short_name", "route"),
    "latitude": ("latitude", "lat"),
    "longitude": ("longitude", "lon", "lng"),
    "observed_at": ("observed_at", "timestamp", "recorded_at", "created_at"),
}


class TigerDataTransitRepository:
    def __init__(self, database: Database, settings: Settings) -> None:
        self._database = database
        self._settings = settings
        self._verified_schema: VerifiedBusPositionsSchema | None = None
        self._schema_lock = Lock()

    def _resolve_column(
        self,
        columns: dict[str, tuple[str, str]],
        logical_name: str,
        override: str | None,
    ) -> str:
        candidates = (override,) if override else COLUMN_CANDIDATES[logical_name]
        selected = next((candidate for candidate in candidates if candidate in columns), None)
        if selected is None:
            expected = override or ", ".join(COLUMN_CANDIDATES[logical_name])
            raise SchemaVerificationError(
                f"bus_positions is missing a {logical_name} column; checked: {expected}",
            )
        return selected

    def _inspect_schema(self) -> VerifiedBusPositionsSchema:
        with self._database.connection() as connection:
            with connection.transaction():
                connection.execute("SET TRANSACTION READ ONLY")
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT column_name, data_type, udt_name
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = %s
                        ORDER BY ordinal_position
                        """,
                        (self._settings.tigerdata_schema, self._settings.bus_positions_table),
                    )
                    column_rows = cursor.fetchall()
                    cursor.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM timescaledb_information.hypertables
                            WHERE hypertable_schema = %s AND hypertable_name = %s
                        ) AS is_hypertable
                        """,
                        (self._settings.tigerdata_schema, self._settings.bus_positions_table),
                    )
                    hypertable_row = cursor.fetchone()

        if not column_rows:
            raise SchemaVerificationError(
                f"{self._settings.tigerdata_schema}.{self._settings.bus_positions_table} was not found",
            )
        if not hypertable_row or not hypertable_row["is_hypertable"]:
            raise SchemaVerificationError("bus_positions exists but is not a TimescaleDB hypertable")

        columns = {
            row["column_name"]: (row["data_type"], row["udt_name"])
            for row in column_rows
        }
        verified = VerifiedBusPositionsSchema(
            agency=self._resolve_column(columns, "agency", self._settings.agency_column),
            vehicle_id=self._resolve_column(columns, "vehicle_id", self._settings.vehicle_id_column),
            route=self._resolve_column(columns, "route", self._settings.route_column),
            latitude=self._resolve_column(columns, "latitude", self._settings.latitude_column),
            longitude=self._resolve_column(columns, "longitude", self._settings.longitude_column),
            observed_at=self._resolve_column(columns, "observed_at", self._settings.observed_at_column),
        )

        numeric_types = {"smallint", "integer", "bigint", "numeric", "real", "double precision", "decimal"}
        if columns[verified.latitude][0] not in numeric_types or columns[verified.longitude][0] not in numeric_types:
            raise SchemaVerificationError("latitude and longitude columns must use numeric database types")
        if columns[verified.observed_at][0] != "timestamp with time zone":
            raise SchemaVerificationError("the observation timestamp column must be timestamp with time zone")

        return verified

    def _schema(self) -> VerifiedBusPositionsSchema:
        if self._verified_schema is None:
            with self._schema_lock:
                if self._verified_schema is None:
                    self._verified_schema = self._inspect_schema()
        return self._verified_schema

    def latest_positions(self, agency_value: str) -> list[PositionRecord]:
        verified = self._schema()
        identifiers = {
            key: sql.Identifier(value)
            for key, value in {
                "agency": verified.agency,
                "vehicle": verified.vehicle_id,
                "route": verified.route,
                "latitude": verified.latitude,
                "longitude": verified.longitude,
                "observed": verified.observed_at,
                "schema": self._settings.tigerdata_schema,
                "table": self._settings.bus_positions_table,
            }.items()
        }
        query = sql.SQL(
            """
            SELECT vehicle_id, agency, route_id, latitude, longitude, observed_at
            FROM (
                SELECT DISTINCT ON ({vehicle})
                    {vehicle}::text AS vehicle_id,
                    {agency}::text AS agency,
                    NULLIF({route}::text, '') AS route_id,
                    {latitude}::double precision AS latitude,
                    {longitude}::double precision AS longitude,
                    {observed} AS observed_at
                FROM {schema}.{table}
                WHERE lower({agency}::text) = lower(%s)
                    AND {vehicle} IS NOT NULL
                    AND {latitude} IS NOT NULL
                    AND {longitude} IS NOT NULL
                    AND {observed} IS NOT NULL
                    AND {observed} >= current_timestamp - (%s * interval '1 hour')
                ORDER BY {vehicle}, {observed} DESC
            ) AS latest
            ORDER BY observed_at DESC
            LIMIT %s
            """
        ).format(**identifiers)

        with self._database.connection() as connection:
            with connection.transaction():
                connection.execute("SET TRANSACTION READ ONLY")
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        query,
                        (
                            agency_value,
                            self._settings.transit_lookback_hours,
                            self._settings.transit_max_vehicles,
                        ),
                    )
                    rows = cursor.fetchall()

        return [PositionRecord(**row) for row in rows]
