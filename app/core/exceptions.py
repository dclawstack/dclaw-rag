class DclawRagError(Exception):
    """Base application error."""


class IngestionError(DclawRagError):
    """Raised when ingestion fails."""


class RetrievalError(DclawRagError):
    """Raised when retrieval fails."""


class GenerationError(DclawRagError):
    """Raised when generation fails."""


class ConfigurationError(DclawRagError):
    """Raised on invalid configuration."""
