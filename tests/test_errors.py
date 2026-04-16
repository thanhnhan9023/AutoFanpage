import pytest
from autofanpage.errors import (
    AutofanpageError, ProfileError, SchemaError,
    SkillInvocationError, AlreadyRanError, SourceFailedError,
)


def test_all_errors_inherit_from_base():
    assert issubclass(ProfileError, AutofanpageError)
    assert issubclass(SchemaError, AutofanpageError)
    assert issubclass(SkillInvocationError, AutofanpageError)
    assert issubclass(AlreadyRanError, AutofanpageError)
    assert issubclass(SourceFailedError, AutofanpageError)


def test_schema_error_carries_context():
    err = SchemaError("posts.json", ["missing key: time"])
    assert err.artifact == "posts.json"
    assert err.violations == ["missing key: time"]
    assert "posts.json" in str(err)
