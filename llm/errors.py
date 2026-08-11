"""Language-model integration errors."""


class StructuredOutputError(RuntimeError):
    """Raised when a provider cannot return a valid structured model."""
