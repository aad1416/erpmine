"""Tool-boundary-adjacent test for FilesService.create_from_bytes (ticket 10):
export_excel needs a bytes-accepting create path alongside the existing
UploadFile-based create(); no changes to the File model or download route."""

import tempfile

import pytest

from app.services.files import FilesService


class _StubFilesRepository:
    def __init__(self):
        self.created = []

    def create(self, file_model):
        self.created.append(file_model)
        return file_model


@pytest.fixture
def files_service():
    repo = _StubFilesRepository()
    service = FilesService(repo)
    with tempfile.TemporaryDirectory() as tmp_dir:
        service.uploads_path = tmp_dir
        yield service, repo


def test_create_from_bytes_writes_content_and_returns_file_record(files_service):
    service, repo = files_service
    content = b"fake xlsx bytes"

    file = service.create_from_bytes(
        content=content,
        file_name="report.xlsx",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        user_id="u-1",
    )

    assert file.file_name == "report.xlsx"
    assert file.extension == "xlsx"
    assert file.size == len(content)
    assert file.user_id == "u-1"
    assert repo.created == [file]

    with open(file.path, "rb") as f:
        assert f.read() == content


def test_create_from_bytes_size_matches_written_byte_count(files_service):
    service, _ = files_service
    content = bytes(range(256)) * 10

    file = service.create_from_bytes(content=content, file_name="data.xlsx", user_id="u-2")

    assert file.size == len(content)
