from dataclasses import dataclass


@dataclass(slots=True)
class ApiError(Exception):
    status_code: int
    code: str
    message: str


class DatabaseNotConfiguredError(Exception):
    pass


class DatabaseUnavailableError(Exception):
    pass


class SchemaVerificationError(Exception):
    pass
