"""Explicit Durham GTFS cache refresh command: python -m app.gtfs_ingest."""
from __future__ import annotations

import json

from .config import get_settings
from .errors import ApiError
from .gtfs import GtfsImporter, GtfsValidationError


def main() -> int:
    try:
        result = GtfsImporter(get_settings()).sync()
    except GtfsValidationError as error:
        print(json.dumps({"status": "invalid", "error": str(error)}))
        return 1
    except ApiError as error:
        print(json.dumps({"status": "unavailable", "code": error.code, "error": error.message}))
        return 1
    print(json.dumps({
        "status": result.status,
        "agencyId": result.agency_id,
        "databasePath": str(result.database_path),
        "version": result.version,
        "validFrom": result.valid_from.isoformat() if result.valid_from else None,
        "validUntil": result.valid_until.isoformat() if result.valid_until else None,
        "counts": result.counts,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
