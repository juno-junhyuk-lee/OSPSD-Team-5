"""Keep path safety independent of the retired HTTP implementation."""

import pytest
from cloud_storage_api import InvalidRequestError

from app.storage_paths import storage_path


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/",
        "../escape",
        "/a//b",
        "//a/b",
        "/a/../b",
        "/a/",
        "a/./b",
        "bad\x00name",
        "bad\nname",
        "a\\b",
    ],
)
def test_root_traversal_and_ambiguous_paths_are_rejected(path: str) -> None:
    with pytest.raises(InvalidRequestError):
        storage_path(path)


@pytest.mark.parametrize(
    "path", ["team5/summary.md", "/team5/summary.md", "/팀5/일정.md"]
)
def test_explicit_destination_paths_are_preserved(path: str) -> None:
    assert storage_path(path) == (path if path.startswith("/") else "/" + path)
