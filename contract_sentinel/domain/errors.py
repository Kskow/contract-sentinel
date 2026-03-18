class UnsupportedFrameworkError(Exception):
    pass


class UnsupportedStorageError(Exception):
    pass


class MissingDependencyError(Exception):
    """Raised when an optional extra is required but not installed."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
