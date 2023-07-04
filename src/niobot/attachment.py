import tempfile
import warnings

import nio
import subprocess
import json
import io
import os
import pathlib
import shutil
import magic
import typing
import aiofiles
import blurhash

from .utils import run_blocking
from .exceptions import MediaUploadException

if typing.TYPE_CHECKING:
    from .client import NioBot

if not shutil.which("ffmpeg"):
    raise RuntimeError(
        "ffmpeg is not installed. You must install it to use this library. If its installed, is it in PATH?"
    )
if not shutil.which("ffprobe"):
    raise RuntimeError(
        "ffprobe is not installed. You must install it to use this library. If its installed, is it in PATH?"
    )


__all__ = (
    "detect_mime_type",
    "get_metadata",
    "generate_blur_hash",
    "first_frame",
    "Thumbnail",
    "MediaAttachment",
    "FileAttachment",
)


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


def first_frame(file: str | pathlib.Path, file_format: str = "webp") -> bytes:
    """
    Gets the first frame of a video file.

    !!! Danger "This function creates a file on disk"
        In order to extract the frame, this function creates a temporary file on disk (or memdisk depending on where
        your tempdir is). While this file is deleted after the function is done, it is still something to be aware of.
        For example, if you're (worryingly) low on space, this function may fail to extract the frame due to a lack of
        space. Or, someone could temporarily access and read the file before it is deleted.

        This also means that this function may be slow.

    :param file: The file to get the first frame of. **Must be a path-like object**
    :param file_format: The format to save the frame as. Defaults to webp.
    :return: The first frame of the video in bytes.
    """
    with tempfile.NamedTemporaryFile(suffix=f".{file_format}") as f:
        command = [
            "ffmpeg",
            "-i",
            str(file),
            "-vframes",
            "1",
            f.name
        ]
        subprocess.run(command, capture_output=True, text=False, check=True)
        f.seek(0)
        return f.read()


def generate_blur_hash(file: str | pathlib.Path) -> str:
    """
    Creates a blurhash

    !!! warning "This function may be resource intensive"
        This function may be resource intensive, especially for large images. You should run this in a thread or
        process pool.

        You should also scale any images down in order to increase performance.
    """
    if isinstance(file, str):
        file = pathlib.Path(file)
    with file.open("rb") as fd:
        return blurhash.encode(fd, 4, 3)


class Thumbnail:
    """
    Represents a thumbnail for a media attachment.

    :param url: The URL of the thumbnail.
    :param mime: The mime type of the thumbnail.
    :param height: The height of the thumbnail.
    :param width: The width of the thumbnail.
    :param size: The size of the thumbnail.
    """
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

    @classmethod
    def from_attachment(cls, attachment: "MediaAttachment"):
        """
        Creates a thumbnail from a MediaAttachment.

        You should make sure you've `upload()`ed the attachment first.

        :param attachment: The attachment to create the thumbnail from.
        :return: A Thumbnail object.
        """
        if not attachment.url:
            raise ValueError("You must upload the attachment first.")

        if attachment.media_type.split(".")[1] not in ("video", "image"):
            raise ValueError("You can only create a thumbnail from a video or image.")

        return cls(
            url=attachment.url,
            mime=attachment.mime,
            height=attachment.height,
            width=attachment.width,
            size=attachment.size
        )

    def to_dict(self):
        return {
            "w": self._width,
            "h": self._height,
            "mimetype": self._mime,
            "size": self.size,
        }


class MediaAttachment:
    """Represents an image, audio or video to be sent to a room.

    ??? tip "You probably want to skip to [from_file](niobot.attachment.MediaAttachment.from_file)"
        The `MediaAttachment.from_file` method is the best way to create a MediaAttachment from just a file.
        You should (and realistically, only can) create an instance of this manually if you have the file,
        mime type, height, width, and optionally thumbnail already.

        The `MediaAttachment.from_file` method will automatically do this for you.

    ??? warning "You can only use video/image/audio content with this class"
        Do not use this attachment type for anything other than video, image, or audio content. Use
        `FileAttachment` for other types of files.

    ???+ danger "BytesIO support is experimental"
        It is advised to write BytesIO objects to a temporary file if you experience any issues with them. This is
        because some methods, such as `MediaAttachment.upload`, re-open the file descriptor in an
        asynchronous context, which may cause issues with BytesIO.

        Initially, the library did this automatically, however to prevent compatibility issues, this is now just the
        responsibility of the developer.

        Using a BytesIO() will yield a warning in the logs, however may still work.

    :param file: The file to send (either a path, BytesIO, or `pathlib.Path` object)
    :param mime: The mime type of the file
    :param height: The height of the file, if applicable
    :param width: The width of the file, if applicable
    :param thumbnail: The thumbnail of the file, if applicable
    :param blur_hash: The blurhash of the file, if applicable
    """
    def __init__(
            self,
            file: typing.Union[str, io.BytesIO, pathlib.Path],
            *,
            mime: str = None,
            height: typing.Union[int, None],
            width: typing.Union[int, None],
            thumbnail: Thumbnail = None,
            blur_hash: str = None
    ):
        if isinstance(file, io.BytesIO):
            warnings.warn(RuntimeWarning("Using BytesIO with MediaAttachment is experimental."))
        self._file = file
        self._url = None
        self.mime = mime
        self.height = height
        self.width = width
        self.thumbnail = thumbnail
        self.blur_hash = blur_hash

        if self.mime is None:
            self.mime = detect_mime_type(self._file)

    @classmethod
    async def from_file(
            cls,
            file: pathlib.Path | str,
            thumbnail: Thumbnail = None,
            gen_blur_hash: bool = True
    ) -> "MediaAttachment":
        """Creates a MediaAttachment from a file.

        :param file: The file to create the attachment from
        (Must be a path or pathlib.Path object, cannot be BytesIO)
        :param thumbnail: The thumbnail of the file, if applicable
        :param gen_blur_hash: Whether to generate a blurhash for the file
        :return: A MediaAttachment object
        """
        # TODO: Add thumbnail (discovery? generation?)
        metadata = await run_blocking(get_metadata, file)
        if "streams" not in metadata:
            raise ValueError("Invalid file.")

        stream = metadata["streams"][0]
        mime_type = await run_blocking(detect_mime_type, file)
        if mime_type.startswith(("image", "video")) and gen_blur_hash:
            if mime_type.startswith("video"):
                frame = await run_blocking(first_frame, file, "jpeg")
                with tempfile.NamedTemporaryFile(suffix=".jpeg") as fd:
                    fd.write(frame)
                    fd.flush()
                    blur_hash = await run_blocking(generate_blur_hash, fd.name)
            else:
                blur_hash = await run_blocking(generate_blur_hash, file)
        else:
            blur_hash = None
        return cls(
            file,
            mime=mime_type,
            height=stream.get("height"),
            width=stream.get("width"),
            thumbnail=thumbnail,
            blur_hash=blur_hash
        )

    @property
    def media_type(self) -> str:
        """
        The media type of the attachment, be it m.video, m.image, or m.audio.

        :returns: `m.audio`, `m.image`, or `m.video`
        """
        return "m." + self.mime.split("/")[0]

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

        if not isinstance(self.file, io.BytesIO):
            async with aiofiles.open(self.file, "r+b") as file:
                result, _ = await client.upload(
                    file,
                    content_type=self.mime,
                    filename=file_name or self.file.name,
                    filesize=self.size
                )
        else:
            result, _ = await client.upload(
                self.file,
                content_type=self.mime,
                filename=file_name or self.file.name,
                filesize=self.size
            )
        if isinstance(result, nio.UploadError):
            raise MediaUploadException(response=result)
        self._url = result.content_uri
        return result

    def to_dict(self) -> dict:
        """Convert the attachment to a dictionary."""
        if self.media_type == "m.audio":
            payload = {"mimetype": self.mime, "size": self.size}
        else:
            if self.height is None:
                raise ValueError("height must be specified for non-audio media attachments.")
            if self.width is None:
                raise ValueError("width must be specified for non-audio media attachments.")

            payload = {
                "mimetype": self.mime,
                "h": self.height,
                "w": self.width,
                "size": self.size,
                "thumbnail_info": self.thumbnail.to_dict() if self.thumbnail else None
            }
            if self.blur_hash:
                payload["xyz.amorgan.blurhash"] = self.blur_hash
        return payload


class FileAttachment(MediaAttachment):
    """Represents a generic file type, such as PDF or TXT.

    !!! warning "Do not use this class for images, audio or video."
        Do not use this class for images, audio or video. Use `MediaAttachment` instead.
        Furthermore, you should initialise this class manually - the `from_file` method does so much
        unnecessary work that it's not worth using for this attachment type.

    :param file: The file to upload.
    :param mime_type: The mime type of the file. If not specified, it will be detected automatically.
    """
    def __init__(
            self,
            file: typing.Union[str, io.BytesIO, pathlib.Path],
            mime_type: str = None,
    ):
        super().__init__(file, mime=mime_type or detect_mime_type(file), height=None, width=None, thumbnail=None)

    def to_dict(self) -> dict:
        """Convert the attachment to a dictionary."""
        return {
            "mimetype": self.mime,
            "size": self.size
        }


# class VideoAttachment:
