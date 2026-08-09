"""Worker-local typed error; mirrors alpha_core.DataError semantics without the import."""


class DataError(RuntimeError):
    """Fail-loud data/validation error inside the isolated literature worker."""
