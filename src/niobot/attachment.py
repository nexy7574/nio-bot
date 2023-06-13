import nio
import asyncio
import subprocess
import json
import logging
import io
import os
import pathlib
import typing
import magic
import typing
import tempfile

from .utils import run_blocking

if typing.TYPE_CHECKING:
    from .client import NioBot


def detect_mime_type(file: typing.Union[str, io.BytesIO, pathlib.Path]) -> str:
    """Detect the mime type of a file."""
    if isinstance(file, str):
        file = pathlib.Path(file)

    if isinstance(file, io.BytesIO):
        current_position = file.tell()
        file.seek(0)
        mt = magic.from_buffer(file.read(), mime=True)
        file.seek(current_position)  # Reset the file position
        return mt
    elif isinstance(file, pathlib.Path):
        return magic.from_file(str(file), mime=True)
    else:
        raise TypeError("File must be a string, BytesIO, or Path object.")


def get_metadata(file: typing.Union[str, io.BytesIO, pathlib.Path]):
    """Gets metadata for a file via ffprobe."""
    command = [
        "ffprobe",
        "-of",
        "json",
        "-loglevel",
        "9",
        "-show_format",
        "-show_streams",
        "-i",
        str(file)
    ]
    result = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace", check=True)
    return json.loads(result.stdout)


class Thumbnail:
    """Represents a thumbnail for a media attachment."""
    def __init__(
            self,
            url: str,
            *,
            mime: str,
            height: int,
            width: int,
            size: int
    ):
        self.url = url
        self._mime = mime
        self._height = height
        self._width = width
        self.size = size

    def to_dict(self):
        return {
            "w": self._width,
            "h": self._height,
            "mimetype": self._mime,
            "size": self.size,
        }


class MediaAttachment:
    """Represents an image or video to be sent to a room."""
    def __init__(
            self,
            file: typing.Union[str, io.BytesIO, pathlib.Path],
            *,
            mime: str = None,
            height: int,
            width: int,
            thumbnail: Thumbnail = None
    ):
        self._file = file
        self._url = None
        self.mime = mime
        self.height = height
        self.width = width
        self.thumbnail = thumbnail

        if self.mime is None:
            self.mime = detect_mime_type(self._file)

    @classmethod
    async def from_file(cls, file: pathlib.Path | str, thumbnail: Thumbnail = None) -> "MediaAttachment":
        """Creates a MediaAttachment from a file."""
        # TODO: Add thumbnail (discovery? generation?)
        metadata = await run_blocking(get_metadata, file)
        if "streams" not in metadata:
            raise ValueError("Invalid file.")

        stream = metadata["streams"][0]
        mime_type = await run_blocking(detect_mime_type, file)
        return cls(
            file,
            mime=mime_type,
            height=stream["height"],
            width=stream["width"],
            thumbnail=thumbnail
        )

    @property
    def media_type(self) -> str:
        """The media type of the attachment, be it m.video or m.image."""
        return "m.video" if self.mime.startswith("video/") else "m.image"

    @property
    def size(self) -> int:
        """Returns the size of the thumbnail in bytes."""
        if isinstance(self._file, io.BytesIO):
            self._file.seek(0, io.SEEK_END)
            size = self._file.tell()
            self._file.seek(0)
            return size
        else:
            return os.path.getsize(self.file)

    @property
    def url(self) -> str | None:
        """The current mxc URL of the attachment, if it has been uploaded."""
        return self._url

    @property
    def file(self) -> pathlib.Path | io.BytesIO:
        if isinstance(self._file, str):
            return pathlib.Path(self._file)
        else:
            return self._file

    async def upload(self, client: "NioBot", file_name: str = None):
        """Uploads the file to matrix."""
        if isinstance(self.file, io.BytesIO):
            if not file_name:
                raise ValueError("file_name must be specified when uploading a BytesIO object.")
            self._file.seek(0)

        result = await client.upload(
            self.file,
            content_type=self.mime,
            filename=file_name or self.file.name,
            filesize=self.size
        )
        if isinstance(result, nio.UploadResponse):
            self._url = result.content_uri
        return result

    def to_dict(self) -> dict:
        """Convert the attachment to a dictionary."""
        return {
            "mimetype": self.mime,
            "h": self.height,
            "w": self.width,
            "size": self.size,
            "thumbnail_info": self.thumbnail.to_dict() if self.thumbnail else None
        }
