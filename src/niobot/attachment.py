"""
Matrix file attachments. Full e2ee support is implemented.

Implemented media types:

[X] Generic file
[X] Image
[X] Audio
[X] Video
"""
import abc
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
import enum
import aiofiles
import logging
import blurhash

from .utils import run_blocking
from .exceptions import MediaUploadException, MetadataDetectionException

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


log = logging.getLogger(__name__)


__all__ = (
    "detect_mime_type",
    "get_metadata",
    "generate_blur_hash",
    "first_frame",
    "BaseAttachment",
    "FileAttachment",
    "ImageAttachment",
    "VideoAttachment",
    "AudioAttachment",
)


def detect_mime_type(file: typing.Union[str, io.BytesIO, pathlib.Path]) -> str:
    """
    Detect the mime type of a file.

    :param file: The file to detect the mime type of. Can be a BytesIO.
    :return: The mime type of the file (e.g. `text/plain`, `image/png`, `application/pdf`, `video/webp` etc.)
    """
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


def get_metadata(file: typing.Union[str, pathlib.Path]) -> typing.Dict[str, typing.Any]:
    """
    Gets metadata for a file via ffprobe.

    ??? note "Example result"
        ```json
        {
            "streams": [
                {
                    "index": 0,
                    "codec_name": "h264",
                    "codec_long_name": "H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10",
                    "profile": "High",
                    "codec_type": "video",
                    ...
                }
            ],
            "format": {
                "filename": "./assets/peek.mp4",
                "format_long_name": "QuickTime / MOV",
                "start_time": "0.000000",
                "duration": "16.283333",
                "size": "4380760",
                "bit_rate": "2152266",
                ...
            }
        }
        ```

    :param file: The file to get metadata for. **Must be a path-like object**
    :return: A dictionary containing the metadata.
    """
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
    try:
        result = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace", check=True)
    except subprocess.SubprocessError as e:
        raise MetadataDetectionException("Failed to get metadata for file.", exception=e)
    log.debug("ffprobe output (%d): %s", result.returncode, result.stdout)
    return json.loads(result.stdout or '{}')


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
            "-loglevel",
            "9",
            "-i",
            str(file),
            "-frames:v",
            "1",
            '-y',
            f.name
        ]
        log.debug("Extracting first frame of %r: %s", file, ' '.join(command))
        try:
            log.debug(
                "Extraction return code: %d",
                subprocess.run(command, capture_output=True, check=True).returncode
            )
        except subprocess.SubprocessError as e:
            raise MediaUploadException("Failed to extract first frame of video.", exception=e)
        f.seek(0)
        return f.read()


def generate_blur_hash(file: str | pathlib.Path | io.BytesIO) -> str:
    """
    Creates a blurhash

    !!! warning "This function may be resource intensive"
        This function may be resource intensive, especially for large images. You should run this in a thread or
        process pool.

        You should also scale any images down in order to increase performance.

        See: [woltapp/blurhash](https://github.com/woltapp/blurhash)
    """
    file = _to_path(file)
    if not isinstance(file, io.BytesIO):
        with file.open("rb") as fd:
            log.info("Generating blurhash for %s", file)
            return blurhash.encode(fd, 4, 3)
    else:
        log.info("Generating blurhash for BytesIO object")
        return blurhash.encode(file, 4, 3)


def _file_okay(file: pathlib.Path | io.BytesIO) -> typing.Literal[True]:
    """Checks if a file exists, is a file, and can be read."""
    if isinstance(file, io.BytesIO):
        if file.closed:
            raise ValueError("BytesIO object is closed.")
        if len(file.getbuffer()) == 0:
            w = ResourceWarning("BytesIO object is empty, this may cause issues. Did you mean to seek(0) first?")
            warnings.warn(w)
        return True

    if not file.exists():
        raise FileNotFoundError(f"File {file} does not exist.")
    if not file.is_file():
        raise ValueError(f"{file} is not a file.")
    if not os.access(file, os.R_OK):
        raise PermissionError(f"Cannot read {file}.")
    # Check it can have a stat() value
    file.stat()
    return True


def _to_path(file: str | pathlib.Path | io.BytesIO) -> typing.Union[pathlib.Path, io.BytesIO]:
    """Converts a string to a Path object."""
    if not isinstance(file, (str, pathlib.PurePath, io.BytesIO)):
        raise TypeError("File must be a string, BytesIO, or Path object.")

    if isinstance(file, io.BytesIO):
        return file

    if isinstance(file, str):
        file = pathlib.Path(file)
    file = file.resolve()
    return file


def _size(file: pathlib.Path | io.BytesIO) -> int:
    """Gets the size of a file."""
    if isinstance(file, io.BytesIO):
        return len(file.getbuffer())
    return file.stat().st_size


class AttachmentType(enum.Enum):
    """
    Enumeration containing the different types of media.
    """
    FILE = "m.file"
    AUDIO = "m.audio"
    VIDEO = "m.video"
    IMAGE = "m.image"


class BaseAttachment(abc.ABC):
    """Base class for attachments"""
    def __init__(
            self,
            file: typing.Union[str, io.BytesIO, pathlib.Path],
            file_name: str = None,
            mime_type: str = ...,
            size_bytes: int = ...,
            *,
            attachment_type: AttachmentType = AttachmentType.FILE
    ):
        self.file = _to_path(file)
        self.file_name = file.name if isinstance(file, pathlib.Path) else file_name
        if not file_name:
            raise ValueError("file_name must be specified when uploading a BytesIO object.")
        self.mime_type = mime_type or detect_mime_type(file)
        self.size = size_bytes or os.path.getsize(file)

        self.type = attachment_type
        self.url = None
        self.keys = None

    def __repr__(self):
        return "<{0.__class__.__name__} file={0.file!r} file_name={0.file_name!r} " \
               "mime_type={0.mime_type!r} size={0.size!r} type={0.type!r}>".format(self)

    def as_body(self, body: str = None) -> dict:
        """
        Generates the body for the attachment for sending. The attachment must've been uploaded first.

        :param body: The body to use (should be a textual description). Defaults to the file name.
        :return:
        """
        body = {
            "body": body or self.file_name,
            "info": {
                "mimetype": self.mime_type,
                "size": self.size,
            },
            "msgtype": self.type.value,
            "filename": self.file_name,
            "url": self.url,
        }
        if self.keys:
            body["file"] = self.keys
        return body

    @classmethod
    async def from_file(
            cls,
            file: typing.Union[str, io.BytesIO, pathlib.Path],
            file_name: str = None,
    ) -> "BaseAttachment":
        """
        Creates an attachment from a file.

        You should use this method instead of the constructor, as it will automatically detect all other values

        :param file: The file or BytesIO to attach
        :param file_name: The name of the BytesIO file, if applicable
        :return: Loaded attachment.
        """
        file = _to_path(file)
        if isinstance(file, io.BytesIO):
            if not file_name:
                raise ValueError("file_name must be specified when uploading a BytesIO object.")
        else:
            if not file_name:
                file_name = file.name

        mime_type = detect_mime_type(file)
        size = _size(file)
        return cls(file, file_name, mime_type, size)

    @classmethod
    def convert_from(cls, other: "BaseAttachment") -> "BaseAttachment":
        """
        Converts another attachment into this type.

        !!! warning "This discards upload progress"
            If you've uploaded the other attachment, you'll lose keys and mxc url by doing this!

        :param other: The other attachment
        :return: This attachment
        """
        return cls(other.file, other.file_name, other.mime_type, other.size)

    @property
    def size_bytes(self) -> int:
        """Returns the size of this attachment in bytes."""
        return self.size

    async def upload(self, client: "NioBot", encrypted: bool = False) -> "BaseAttachment":
        """
        Uploads the file to matrix.

        :param client: The client to upload
        :param encrypted: Whether to encrypt the thumbnail or not
        :return: The attachment
        """
        size = self.size or _size(self.file)
        if not isinstance(self.file, io.BytesIO):
            async with aiofiles.open(self.file, "rb") as f:
                result, keys = await client.upload(
                    f,
                    content_type=self.mime_type,
                    filename=self.file_name,
                    encrypt=encrypted,
                    filesize=size,
                )
        else:
            result, keys = await client.upload(
                self.file,
                content_type=self.mime_type,
                filename=self.file_name,
                encrypt=encrypted,
                filesize=size,
            )
        if not isinstance(result, nio.UploadResponse):
            raise MediaUploadException("Upload failed: %r" % result, result)

        if keys:
            self.keys = keys

        self.url = result.content_uri
        return self


class SupportXYZAmorganBlurHash(BaseAttachment):
    """Represents an attachment that supports blurhashes."""
    def __init__(self, *args, xyz_amorgan_blurhash: str = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.xyz_amorgan_blurhash = xyz_amorgan_blurhash

    @classmethod
    async def from_file(
            cls,
            file: typing.Union[str, io.BytesIO, pathlib.Path],
            file_name: str = None,
            xyz_amorgan_blurhash: str | bool = None,
    ):
        file = _to_path(file)
        if isinstance(file, io.BytesIO):
            if not file_name:
                raise ValueError("file_name must be specified when uploading a BytesIO object.")
        else:
            if not file_name:
                file_name = file.name

        mime_type = detect_mime_type(file)
        size = _size(file)
        self = cls(file, file_name, mime_type, size, xyz_amorgan_blurhash=xyz_amorgan_blurhash)
        if xyz_amorgan_blurhash is not False:
            await self.get_blurhash()
        return self

    async def get_blurhash(self):
        """
        Gets the blurhash of the attachment.

        :return: The blurhash
        """
        if isinstance(self.xyz_amorgan_blurhash, str):
            return self.xyz_amorgan_blurhash
        x = await run_blocking(generate_blur_hash, self.file)
        self.xyz_amorgan_blurhash = x
        return x

    def as_body(self, body: str = None) -> dict:
        body = super().as_body(body)
        if isinstance(self.xyz_amorgan_blurhash, str):
            body["info"]["xyz.amorgan.blurhash"] = self.xyz_amorgan_blurhash
        return body


class FileAttachment(BaseAttachment):
    """
    Represents a generic file attachment.

    You should use [VideoAttachment][niobot.attachment.VideoAttachment] for videos,
    [AudioAttachment][niobot.attachment.AudioAttachment] for audio,
    and [ImageAttachment][niobot.attachment.ImageAttachment] for images.
    This is for everything else.
    """
    def __init__(
            self,
            file: typing.Union[str, io.BytesIO, pathlib.Path],
            file_name: str = ...,
            mime_type: str = ...,
            size_bytes: int = ...,
    ):
        super().__init__(file, file_name, mime_type, size_bytes, attachment_type=AttachmentType.FILE)


class ImageAttachment(SupportXYZAmorganBlurHash):
    """
    Represents an image attachment.
    """
    def __init__(
            self,
            file: typing.Union[str, io.BytesIO, pathlib.Path],
            file_name: str = ...,
            mime_type: str = ...,
            size_bytes: int = ...,
            height: int = None,
            width: int = None,
            thumbnail: "ImageAttachment" = None,
            xyz_amorgan_blurhash: str = None,
    ):
        super().__init__(
            file,
            file_name,
            mime_type,
            size_bytes,
            xyz_amorgan_blurhash=xyz_amorgan_blurhash,
            attachment_type=AttachmentType.IMAGE
        )
        self.info = {
            "h": height,
            "w": width,
            "mimetype": mime_type,
            "size": size_bytes,
        }
        self.thumbnail = thumbnail

    @classmethod
    async def from_file(
            cls,
            file: typing.Union[str, io.BytesIO, pathlib.Path],
            file_name: str = ...,
            height: int = None,
            width: int = None,
            thumbnail: "ImageAttachment" = None,
            generate_blurhash: bool = True,
    ) -> "ImageAttachment":
        """
        Generates an image attachment

        :param file: The file to upload
        :param file_name: The name of the file (only used if file is a `BytesIO`)
        :param height: The height, in pixels, of this image
        :param width: The width, in pixels, of this image
        :param thumbnail: A thumbnail for this image
        :param generate_blurhash: Whether to generate a blurhash for this image
        :return: An image attachment
        """
        file = _to_path(file)
        if isinstance(file, io.BytesIO):
            if not file_name:
                raise ValueError("file_name must be specified when uploading a BytesIO object.")
        else:
            if not file_name:
                file_name = file.name

            if height is None or width is None:
                metadata = await run_blocking(get_metadata, file)
                stream = metadata["streams"][0]
                height = stream["height"]
                width = stream["width"]

        mime_type = detect_mime_type(file)
        size = _size(file)
        self = cls(file, file_name, mime_type, size, height, width, thumbnail)
        if generate_blurhash:
            await self.get_blurhash()
        return self

    def as_body(self, body: str = None) -> dict:
        body = super().as_body(body)
        body["info"] = {**body["info"], **self.info}
        if self.thumbnail:
            if self.thumbnail.keys:
                body["info"]["thumbnail_file"] = self.thumbnail.keys
            body["info"]["thumbnail_info"] = self.thumbnail.info
            body["info"]["thumbnail_url"] = self.thumbnail.url
        return body


class VideoAttachment(SupportXYZAmorganBlurHash):
    """
    Represents a video attachment.
    """
    def __init__(
            self,
            file: typing.Union[str, io.BytesIO, pathlib.Path],
            file_name: str = ...,
            mime_type: str = ...,
            size_bytes: int = ...,
            duration: int = None,
            height: int = None,
            width: int = None,
            thumbnail: "ImageAttachment" = None,
            xyz_amorgan_blurhash: str = None,
    ):
        super().__init__(
            file,
            file_name,
            mime_type,
            size_bytes,
            xyz_amorgan_blurhash=xyz_amorgan_blurhash,
            attachment_type=AttachmentType.VIDEO
        )
        self.info = {
            "duration": round(duration * 1000) if duration else None,
            "h": height,
            "w": width,
            "mimetype": mime_type,
            "size": size_bytes,
        }
        self.thumbnail = thumbnail

    @classmethod
    async def from_file(
            cls,
            file: typing.Union[str, io.BytesIO, pathlib.Path],
            file_name: str = ...,
            duration: int = None,
            height: int = None,
            width: int = None,
            thumbnail: "ImageAttachment" = None,
            generate_blurhash: bool = True,
    ) -> "VideoAttachment":
        """
        Generates a video attachment

        :param file: The file to upload
        :param file_name: The name of the file (only used if file is a `BytesIO`)
        :param duration: The duration of the video, in seconds
        :param height: The height, in pixels, of this video
        :param width: The width, in pixels, of this video
        :param thumbnail: A thumbnail for this image
        :param generate_blurhash: Whether to generate a blurhash for this image
        :return: An image attachment
        """
        file = _to_path(file)
        if isinstance(file, io.BytesIO):
            if not file_name:
                raise ValueError("file_name must be specified when uploading a BytesIO object.")
        else:
            if not file_name:
                file_name = file.name

            if height is None or width is None or duration is None:
                metadata = await run_blocking(get_metadata, file)
                stream = metadata["streams"][0]
                height = stream["height"]
                width = stream["width"]
                duration = round(float(metadata["format"]["duration"]) * 1000)

        mime_type = detect_mime_type(file)
        size = _size(file)
        self = cls(file, file_name, mime_type, size, duration, height, width, thumbnail)
        if generate_blurhash:
            await self.get_blurhash()
        return self

    def as_body(self, body: str = None) -> dict:
        body = super().as_body(body)
        body["info"] = {**body["info"], **self.info}
        if self.thumbnail:
            if self.thumbnail.keys:
                body["info"]["thumbnail_file"] = self.thumbnail.keys
            body["info"]["thumbnail_info"] = self.thumbnail.info
            body["info"]["thumbnail_url"] = self.thumbnail.url
        return body


class AudioAttachment(BaseAttachment):
    """
    Represents an audio attachment.
    """
    def __init__(
            self,
            file: typing.Union[str, io.BytesIO, pathlib.Path],
            file_name: str = ...,
            mime_type: str = ...,
            size_bytes: int = ...,
            duration: int = None,
    ):
        super().__init__(
            file,
            file_name,
            mime_type,
            size_bytes,
            attachment_type=AttachmentType.AUDIO
        )
        self.info = {
            "duration": round(duration * 1000) if duration else None,
            "mimetype": mime_type,
            "size": size_bytes,
        }

    @classmethod
    async def from_file(
            cls,
            file: typing.Union[str, io.BytesIO, pathlib.Path],
            file_name: str = ...,
            duration: int = None,
    ) -> "AudioAttachment":
        """
        Generates an audio attachment

        :param file: The file to upload
        :param file_name: The name of the file (only used if file is a `BytesIO`)
        :param duration: The duration of the audio, in seconds
        :return: An audio attachment
        """
        file = _to_path(file)
        if isinstance(file, io.BytesIO):
            if not file_name:
                raise ValueError("file_name must be specified when uploading a BytesIO object.")
        else:
            if not file_name:
                file_name = file.name
            if duration is None:
                metadata = await run_blocking(get_metadata, file)
                duration = round(float(metadata["format"]["duration"]) * 1000)

        mime_type = detect_mime_type(file)
        size = _size(file)
        self = cls(file, file_name, mime_type, size, duration)
        return self

    def as_body(self, body: str = None) -> dict:
        body = super().as_body(body)
        body["info"] = {**body["info"], **self.info}
        return body
