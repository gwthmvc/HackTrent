from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


# Always load backend/.env regardless of the directory the server is started from.
BACKEND_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    environment: str = "development"
    database_url: SecretStr | None = Field(
        default=None,
        validation_alias="TIGERDATA_DATABASE_URL",
    )
    database_connect_timeout_seconds: int = Field(
        default=10,
        validation_alias="DATABASE_CONNECT_TIMEOUT_SECONDS",
        ge=1,
        le=60,
    )
    tigerdata_schema: str = Field(default="public", validation_alias="TIGERDATA_SCHEMA")
    bus_positions_table: str = Field(
        default="bus_positions",
        validation_alias="TIGERDATA_BUS_POSITIONS_TABLE",
    )
    agency_values: dict[str, str] = Field(
        default_factory=lambda: {"kingston": "kingston", "durham": "durham"},
        validation_alias="TIGERDATA_AGENCY_VALUES",
    )
    transit_stale_after_seconds: int = Field(default=300, ge=30, le=86_400)
    transit_max_vehicles: int = Field(default=200, ge=1, le=2_000)
    transit_lookback_hours: int = Field(default=24, ge=1, le=168)
    gtfs_durham_feed_url: str = "https://maps.durham.ca/OpenDataGTFS/GTFS_Durham_TXT.zip"
    gtfs_cache_dir: Path = BACKEND_ENV_FILE.parent / "data" / "gtfs"
    gtfs_request_timeout_seconds: float = Field(default=30, gt=0, le=120)
    gtfs_max_archive_bytes: int = Field(default=50_000_000, ge=1_000_000, le=200_000_000)
    gtfs_max_uncompressed_bytes: int = Field(default=300_000_000, ge=10_000_000, le=1_000_000_000)
    gtfs_user_agent: str = "SmartMoveOntario/0.1 (HackTrent educational project)"
    gtfs_default_stop_radius_meters: int = Field(default=800, ge=100, le=3_000)
    gtfs_max_journeys: int = Field(default=5, ge=1, le=20)

    agency_column: str | None = Field(default=None, validation_alias="TIGERDATA_AGENCY_COLUMN")
    vehicle_id_column: str | None = Field(default=None, validation_alias="TIGERDATA_VEHICLE_ID_COLUMN")
    route_column: str | None = Field(default=None, validation_alias="TIGERDATA_ROUTE_COLUMN")
    latitude_column: str | None = Field(default=None, validation_alias="TIGERDATA_LATITUDE_COLUMN")
    longitude_column: str | None = Field(default=None, validation_alias="TIGERDATA_LONGITUDE_COLUMN")
    observed_at_column: str | None = Field(default=None, validation_alias="TIGERDATA_OBSERVED_AT_COLUMN")

    auth_required: bool = True
    auth0_domain: str | None = None
    auth0_audience: str | None = None
    auth0_required_scope: str = "read:transit"
    ticketmaster_api_key: SecretStr | None = Field(default=None, validation_alias="TICKETMASTER_API_KEY")
    ticketmaster_base_url: str = "https://app.ticketmaster.com/discovery/v2"
    ticketmaster_timeout_seconds: float = Field(default=8, gt=0, le=30)
    ticketmaster_max_requests_per_minute: int = Field(default=20, ge=1, le=300)
    ticketmaster_max_requests_per_day: int = Field(default=1_000, ge=1, le=5_000)
    events_cache_ttl_seconds: int = Field(default=900, ge=0, le=86_400)
    events_max_results: int = Field(default=20, ge=1, le=50)
    events_max_searches_per_user_per_minute: int = Field(default=10, ge=1, le=120)
    overpass_base_url: str = "https://overpass.private.coffee/api/interpreter"
    overpass_timeout_seconds: float = Field(default=18, gt=0, le=30)
    overpass_query_timeout_seconds: int = Field(default=12, ge=5, le=25)
    overpass_max_response_bytes: int = Field(default=8_000_000, ge=100_000, le=32_000_000)
    overpass_user_agent: str = "SmartMoveOntario/0.1 (HackTrent educational project)"
    places_cache_ttl_seconds: int = Field(default=3_600, ge=0, le=86_400)
    places_max_results: int = Field(default=60, ge=1, le=100)
    places_max_searches_per_user_per_minute: int = Field(default=10, ge=1, le=120)
    overpass_max_requests_per_minute: int = Field(default=4, ge=1, le=30)
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"],
    )

    @field_validator("tigerdata_schema", "bus_positions_table")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if not value or not value.replace("_", "").isalnum():
            raise ValueError("database identifiers may contain only letters, numbers, and underscores")
        return value

    @field_validator("agency_values")
    @classmethod
    def normalize_agencies(cls, value: dict[str, str]) -> dict[str, str]:
        normalized = {key.strip().lower(): stored.strip() for key, stored in value.items()}
        if not normalized or any(not key or not stored for key, stored in normalized.items()):
            raise ValueError("TIGERDATA_AGENCY_VALUES must contain non-empty agency mappings")
        return normalized

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            import json

            parsed = json.loads(value)
            if not isinstance(parsed, list):
                raise ValueError("CORS_ALLOWED_ORIGINS must be a JSON array")
            return parsed
        return value

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_origins(cls, value: list[str]) -> list[str]:
        origins = [origin.rstrip("/") for origin in value]
        if any(origin == "*" for origin in origins):
            raise ValueError("wildcard CORS origins are not allowed")
        return origins

    @field_validator("ticketmaster_base_url")
    @classmethod
    def validate_ticketmaster_url(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("TICKETMASTER_BASE_URL must use https")
        return value.rstrip("/")

    @field_validator("gtfs_durham_feed_url")
    @classmethod
    def validate_gtfs_url(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("GTFS_DURHAM_FEED_URL must use https")
        return value

    @field_validator("gtfs_cache_dir", mode="before")
    @classmethod
    def resolve_gtfs_cache_dir(cls, value: object) -> object:
        path = Path(value) if isinstance(value, (str, Path)) else value
        if isinstance(path, Path) and not path.is_absolute():
            return (BACKEND_ENV_FILE.parent / path).resolve()
        return path

    @field_validator("gtfs_user_agent")
    @classmethod
    def validate_gtfs_user_agent(cls, value: str) -> str:
        if len(value.strip()) < 12:
            raise ValueError("GTFS_USER_AGENT must identify the application")
        return value.strip()

    @field_validator("overpass_base_url")
    @classmethod
    def validate_overpass_url(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("OVERPASS_BASE_URL must use https")
        return value.rstrip("/")

    @field_validator("overpass_user_agent")
    @classmethod
    def validate_overpass_user_agent(cls, value: str) -> str:
        if len(value.strip()) < 12:
            raise ValueError("OVERPASS_USER_AGENT must identify the application")
        return value.strip()

    @property
    def auth_configured(self) -> bool:
        return bool(self.auth0_domain and self.auth0_audience)


@lru_cache
def get_settings() -> Settings:
    return Settings()
