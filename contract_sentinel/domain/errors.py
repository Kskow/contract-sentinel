class UnsupportedFrameworkError(Exception):
    pass


class UnsupportedStorageError(Exception):
    pass


class MissingDependencyError(Exception):
    def __init__(self, package: str) -> None:
        super().__init__(
            f"Required package '{package}' is not installed. Install it with: pip install {package}"
        )
