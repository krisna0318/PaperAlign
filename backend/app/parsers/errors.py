class DocxAnalysisError(Exception):
    """A safe, user-facing failure raised while reading an input package."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
