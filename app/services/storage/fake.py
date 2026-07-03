"""In-memory StorageProvider for tests - never touches live credentials or a real network.

Seeded with a set of files; `list_new_files` returns those not yet moved, `download_file`
returns their canned bytes, and `move_file` records the destination. Used across Slice 2's tests
(and later slices) so provider-dependent code can be exercised without Google Drive/S3.
"""

from app.services.storage.base import FileDestination, RemoteFile, StorageProvider


class FakeStorageProvider(StorageProvider):
    def __init__(self, files: dict[RemoteFile, bytes] | None = None) -> None:
        self._files: dict[RemoteFile, bytes] = dict(files or {})
        # file id -> destination it was moved to; also removes it from list_new_files.
        self.moved: dict[str, FileDestination] = {}

    async def list_new_files(self) -> list[RemoteFile]:
        return [f for f in self._files if f.id not in self.moved]

    async def download_file(self, file: RemoteFile) -> bytes:
        return self._files[file]

    async def move_file(self, file: RemoteFile, destination: FileDestination) -> None:
        self.moved[file.id] = destination
