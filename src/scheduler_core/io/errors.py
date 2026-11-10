"""Errors raised by run storage."""


class ArtifactError(Exception):
    """An artifact or its provenance is invalid."""


class UnsafePathError(ArtifactError):
    """A path is unsafe or contains a link."""


class RunClosedError(ArtifactError):
    """A terminal run cannot be changed."""
