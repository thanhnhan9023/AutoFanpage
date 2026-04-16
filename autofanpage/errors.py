"""Typed exceptions for autofanpage."""
from __future__ import annotations


class AutofanpageError(Exception):
    """Base class."""


class ProfileError(AutofanpageError):
    """Raised when a page profile is missing keys or has invalid values."""


class SchemaError(AutofanpageError):
    """Raised when a JSON artifact fails schema validation."""

    def __init__(self, artifact: str, violations: list[str]) -> None:
        self.artifact = artifact
        self.violations = violations
        super().__init__(f"{artifact}: {'; '.join(violations)}")


class SkillInvocationError(AutofanpageError):
    """Raised when a sub-skill invocation fails."""


class AlreadyRanError(AutofanpageError):
    """Raised when today's run has already succeeded for this page."""


class SourceFailedError(AutofanpageError):
    """Raised by an individual Phase-1 source after retries exhausted."""
