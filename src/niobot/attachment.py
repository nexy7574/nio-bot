"""
Matrix file attachments. Full e2ee support is implemented.
"""

import abc
import enum
import io
import json
import logging
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import time
import typing
import urllib.parse
import warnings
from typing import Union as U
from typing import overload

import aiofiles
import aiohttp
import blurhash
import magic
import nio
import PIL.Image

from .exceptions import (
    MediaCodecWarning,
    MediaDownloadException,
    MediaUploadException,
    MetadataDetectionException,
)
from .utils import run_blocking

if typing.TYPE_CHECKING:
    from .client import NioBot


log = logging.getLogger(__name__)
_CT = typing.TypeVar("_CT", bound=U[str, bytes, pathlib.Path, typing.IO[bytes]])


__all__ = (
    "detect_mime_type",
    "get_metadata_ffmpeg",
    "get_metadata_imagemagick",
    "get_metadata",
    "generate_blur_hash",
    "first_frame",
    "which",
    "BaseAttachment",
    "FileAttachment",
    "ImageAttachment",
    "VideoAttachment",
    "AudioAttachment",
    "AttachmentType",
    "SUPPORTED_CODECS",
    "SUPPORTED_VIDEO_CODECS",
    "SUPPORTED_AUDIO_CODECS",
    "SUPPORTED_IMAGE_CODECS",
)

SUPPORTED_VIDEO_CODECS = [
    "h264",
    "vp8",
    "vp9",
    "av1",
    "theora",
]
# Come on browsers, five codecs is lackluster support. I'm looking at you, Safari.
SUPPORTED_AUDIO_CODECS = [
    "speex",
    "opus",
    "aac",
    "mp3",
    "vorbis",
    "flac",
    "mp2",
]
# All of the above codecs were played in Element Desktop. A bunch were cut out, as the list was far too long.
# Realistically, I don't see the warning being useful to too many people, it's literally only in to help people figure
# out why their media isn't playing.
SUPPORTED_IMAGE_CODECS = ["mjpeg", "gif", "png", "av1", "webp"]
# Probably not all of them but close enough
SUPPORTED_CODECS = SUPPORTED_VIDEO_CODECS + SUPPORTED_AUDIO_CODECS + SUPPORTED_IMAGE_CODECS


def detect_mime_type(file: U[str, io.BytesIO, pathlib.Path]) -> str:
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
        start = time.perf_counter()
        mt = magic.from_buffer(file.read(), mime=True)
        log.debug("Took %f seconds to detect mime type", time.perf_counter() - start)
        file.seek(current_position)  # Reset the file position
        return mt
    elif isinstance(file, pathlib.Path):
        start = time.perf_counter()
        mt = magic.from_file(str(file), mime=True)
        log.debug("Took %f seconds to detect mime type", time.perf_counter() - start)
        return mt
    else:
        raise TypeError("File must be a string, BytesIO, or Path object.")


def get_metadata_ffmpeg(file: U[str, pathlib.Path]) -> dict[str, typing.Any]:
    """
    Gets metadata for a file via ffprobe.

    [example output (JSON)](https://github.com/nexy7574/niobot/raw/master/docs/assets/guides/text/example_ffprobe.json)

    :param file: The file to get metadata for. **Must be a path-like object**
    :return: A dictionary containing the metadata.
    """
    if not shutil.which("ffprobe"):
        raise FileNotFoundError("ffprobe is not installed. If it is, check your $PATH.")
    command = ["ffprobe", "-of", "json", "-loglevel", "9", "-show_format", "-show_streams", "-i", str(file)]
    start = time.perf_counter()
    try:
        result = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace", check=True)
    except subprocess.SubprocessError as e:
        raise MetadataDetectionException("Failed to get metadata for file.", exception=e)
    log.debug("Took %f seconds to run ffprobe", time.perf_counter() - start)
    log.debug("ffprobe output (%d): %s", result.returncode, result.stdout)
    data = json.loads(result.stdout or "{}")
    log.debug("parsed ffprobe output:\n%s", json.dumps(data, indent=4))
    return data


def get_metadata_imagemagick(file: pathlib.Path) -> dict[str, typing.Any]:
    """The same as `get_metadata_ffmpeg` but for ImageMagick.

    Only returns a limited subset of the data, such as one stream, which contains the format, and size,
    and the format, which contains the filename, format, and size.

    [example output (JSON)](https://github.com/nexy7574/niobot/raw/master/docs/assets/guides/text/example_identify.json)

    :param file: The file to get metadata for. **Must be a path object**
    :return: A slimmed-down dictionary containing the metadata.
    """
    file = file.resolve(True)
    command = ["identify", str(file)]
    start = time.perf_counter()
    try:
        result = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace", check=True)
    except subprocess.SubprocessError as e:
        raise MetadataDetectionException("Failed to get metadata for file.", exception=e)
    log.debug("identify output (%d): %s", result.returncode, result.stdout)
    log.debug("identify took %f seconds", time.perf_counter() - start)
    stdout = result.stdout
    stdout = stdout[len(str(file)) + 1 :]
    img_format, img_size, *_ = stdout.split()
    data = {
        "streams": [
            {
                "index": 0,
                "codec_name": img_format,
                "codec_long_name": img_format,
                "codec_type": "video",
                "height": int(img_size.split("x")[1]),
                "width": int(img_size.split("x")[0]),
            }
        ],
        "format": {
            "filename": str(file),
            "format_long_name": img_format,
            "size": str(file.stat().st_size),
        },
    }
    log.debug("Parsed identify output:\n%s", json.dumps(data, indent=4))
    return data


def get_metadata(file: U[str, pathlib.Path], mime_type: typing.Optional[str] = None) -> dict[str, typing.Any]:
    """
    Gets metadata for a file.

    This will use imagemagick (`identify`) for images where available, falling back to ffmpeg (`ffprobe`)
    for everything else.

    :param file: The file to get metadata for.
    :param mime_type: The mime type of the file. If not provided, it will be detected.
    :return: The metadata for the file. See [niobot.get_metadata_ffmpeg][] and [niobot.get_metadata_imagemagick][]
     for more information.
    """
    file = _to_path(file)
    mime = mime_type or detect_mime_type(file)
    mime = mime.split("/")[0]
    if mime == "image":
        if not shutil.which("identify"):
            log.warning(
                "Imagemagick identify not found, falling back to ffmpeg for image metadata detection. "
                "Check your $PATH."
            )
        else:
            start = time.perf_counter()

            try:
                r = get_metadata_imagemagick(file)
                log.debug("get_metadata_imagemagick took %f seconds", time.perf_counter() - start)
                return r
            except (IndexError, ValueError, subprocess.SubprocessError, IOError, OSError):
                log.warning(
                    "Failed to detect metadata for %r with imagemagick. Falling back to ffmpeg.", file, exc_info=True
                )

    if mime not in ["audio", "video", "image"]:
        raise MetadataDetectionException("Unsupported mime type. Must be an audio clip, video, or image.")
    start = time.perf_counter()
    r = get_metadata_ffmpeg(file)
    log.debug("get_metadata_ffmpeg took %f seconds", time.perf_counter() - start)
    return r


def first_frame(file: U[str, pathlib.Path], file_format: str = "webp") -> bytes:
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
    if not shutil.which("ffmpeg"):
        raise FileNotFoundError("ffmpeg is not installed. If it is, check your $PATH.")
    with tempfile.NamedTemporaryFile(suffix=f".{file_format}") as f:
        command = ["ffmpeg", "-loglevel", "9", "-i", str(file), "-frames:v", "1", "-y", "-strict", "-2", f.name]
        log.debug("Extracting first frame of %r: %s", file, " ".join(command))
        try:
            start = time.perf_counter()
            log.debug("Extraction return code: %d", subprocess.run(command, capture_output=True, check=True).returncode)
            log.debug("Extraction took %f seconds", time.perf_counter() - start)
        except subprocess.SubprocessError as e:
            raise MediaUploadException("Failed to extract first frame of video.", exception=e)
        f.seek(0)
        return f.read()


def generate_blur_hash(file: U[str, pathlib.Path, io.BytesIO, PIL.Image.Image], *parts: int) -> str:
    """
    Creates a blurhash

    !!! warning "This function may be resource intensive"
        This function may be resource intensive, especially for large images. You should run this in a thread or
        process pool.

        You should also scale any images down in order to increase performance.

        See: [woltapp/blurhash](https://github.com/woltapp/blurhash)
    """
    if not parts:
        parts = 4, 3
    if not isinstance(file, (io.BytesIO, PIL.Image.Image)):
        file = _to_path(file)
        size = PIL.Image.open(file).size
        with file.open("rb") as fd:
            log.info("Generating blurhash for %s (%s)", file, size)
            start = time.perf_counter()
            x = blurhash.encode(fd, *parts)
            log.debug("Generating blurhash took %f seconds", time.perf_counter() - start)
            return x
    else:
        if isinstance(file, io.BytesIO):
            size = PIL.Image.open(file).size
        else:
            size = file.size
        log.info("Generating blurhash for BytesIO/PIL object %r (%s)", file, size)
        start = time.perf_counter()
        x = blurhash.encode(file, *parts)
        log.debug("Generating blurhash took %f seconds", time.perf_counter() - start)
        return x


def _file_okay(file: U[pathlib.Path, io.BytesIO]) -> typing.Literal[True]:
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


@overload
def _to_path(file: U[str, pathlib.Path]) -> pathlib.Path: ...


@overload
def _to_path(file: io.BytesIO) -> io.BytesIO: ...


def _to_path(file: U[str, pathlib.Path, io.BytesIO]) -> U[pathlib.Path, io.BytesIO]:
    """Converts a string to a Path object."""
    if not isinstance(file, (str, pathlib.Path, io.BytesIO)):
        raise TypeError("File must be a string, BytesIO, or Path object.")

    if isinstance(file, io.BytesIO):
        return file

    if isinstance(file, str):
        file = pathlib.Path(file)
    file = file.resolve()
    return file


def _size(file: U[pathlib.Path, io.BytesIO]) -> int:
    """Gets the size of a file."""
    if isinstance(file, io.BytesIO):
        return len(file.getbuffer())
    return file.stat().st_size


def which(file: U[io.BytesIO, pathlib.Path, str], mime_type: typing.Optional[str] = None) -> U[
    typing.Type["FileAttachment"],
    typing.Type["ImageAttachment"],
    typing.Type["AudioAttachment"],
    typing.Type["VideoAttachment"],
]:
    """
    Gets the correct attachment type for a file.

    This function will provide either Image/Video/Audio attachment where possible, or FileAttachment otherwise.

    For example, `image/png` (from `my_image.png`) will see `image/` and will return
    [`ImageAttachment`][niobot.ImageAttachment], and `video/mp4` (from `my_video.mp4`) will see `video/` and will
    return [`VideoAttachment`][niobot.VideoAttachment].

    If the mime type cannot be mapped to an attachment type, this function will return
    [`FileAttachment`][niobot.FileAttachment].

    ??? example "Usage"
        ```python
        import niobot
        import pathlib

        my_file = pathlib.Path("/tmp/foo.bar")
        attachment = await niobot.which(my_file).from_file(my_file)
        # or
        attachment_type = niobot.which(my_file)  # one of the BaseAttachment subclasses
        attachment = await attachment_type.from_file(my_file)
        ```

    :param file: The file or BytesIO to investigate
    :param mime_type: The optional pre-detected mime type. If this is not provided, it will be detected.
    :return: The correct type for this attachment (not instantiated)
    """
    values = {
        "image": ImageAttachment,
        "audio": AudioAttachment,
        "video": VideoAttachment,
    }
    if not mime_type:
        mime_type = detect_mime_type(file)
    mime_start = mime_type.split("/")[0].lower()
    return values.get(mime_start, FileAttachment)


class AttachmentType(enum.Enum):
    """
    Enumeration containing the different types of media.

    :var FILE: A generic file.
    :var AUDIO: An audio file.
    :var VIDEO: A video file.
    :var IMAGE: An image file.
    """

    if typing.TYPE_CHECKING:
        FILE: "AttachmentType"
        AUDIO: "AttachmentType"
        VIDEO: "AttachmentType"
        IMAGE: "AttachmentType"
    FILE = "m.file"
    AUDIO = "m.audio"
    VIDEO = "m.video"
    IMAGE = "m.image"


class BaseAttachment(abc.ABC):
    """
    Base class for attachments

    !!! note
        If you pass a custom `file_name`, this is only actually used if you pass a [io.BytesIO][] to `file`.
        If you pass a [pathlib.Path][] or a [string][str], the file name will be resolved from the path, overriding
        the `file_name` parameter.

    :param file: The file path or BytesIO object to upload.
    :param file_name: The name of the file. **Must be specified if uploading a BytesIO object.**
    :param mime_type: The mime type of the file. If not specified, it will be detected.
    :param size_bytes: The size of the file in bytes. If not specified, it will be detected.
    :param attachment_type: The type of attachment. Defaults to `AttachmentType.FILE`.

    :ivar file: The file path or BytesIO object to upload. Resolved to a [pathlib.Path][] object if a string is
    passed to `__init__`.
    :ivar file_name: The name of the file. If `file` was a string or `Path`, this will be the name of the file.
    :ivar mime_type: The mime type of the file.
    :ivar size: The size of the file in bytes.
    :ivar type: The type of attachment.
    :ivar url: The URL of the uploaded file. This is set after the file is uploaded.
    :ivar keys: The encryption keys for the file. This is set after the file is uploaded.
    """

    if typing.TYPE_CHECKING:
        file: U[pathlib.Path, io.BytesIO]
        file_name: str
        mime_type: str
        size: int
        type: AttachmentType

        url: typing.Optional[str]
        keys: typing.Optional[dict[str, str]]

    def __init__(
        self,
        file: U[str, io.BytesIO, pathlib.Path],
        file_name: typing.Optional[str] = None,
        mime_type: typing.Optional[str] = None,
        size_bytes: typing.Optional[int] = None,
        *,
        attachment_type: AttachmentType = AttachmentType.FILE,
    ):
        self.file = _to_path(file)
        # Ignore type error as the type is checked right afterwards
        self.file_name = self.file.name if isinstance(self.file, pathlib.Path) else file_name  # type: ignore
        if not self.file_name:
            raise ValueError("file_name must be specified when uploading a BytesIO object.")
        self.mime_type = mime_type or detect_mime_type(self.file)
        if size_bytes:
            self.size = size_bytes
        elif isinstance(self.file, io.BytesIO):
            self.size = len(self.file.getbuffer())
        else:
            os.path.getsize(self.file)

        self.type = attachment_type
        self.url = None
        self.keys = None

    def __repr__(self):
        return (
            "<{0.__class__.__name__} file={0.file!r} file_name={0.file_name!r} "
            "mime_type={0.mime_type!r} size={0.size!r} type={0.type!r}>".format(self)
        )

    def as_body(self, body: typing.Optional[str] = None) -> dict:
        """
        Generates the body for the attachment for sending. The attachment must've been uploaded first.

        :param body: The body to use (should be a textual description). Defaults to the file name.
        :return:
        """
        output_body = {
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
            output_body["file"] = self.keys
        return output_body

    @classmethod
    async def from_file(
        cls,
        file: U[str, io.BytesIO, pathlib.Path],
        file_name: typing.Optional[str] = None,
    ) -> "BaseAttachment":
        """
        Creates an attachment from a file.

        You should use this method instead of the constructor, as it will automatically detect all other values

        :param file: The file or BytesIO to attach
        :param file_name: The name of the BytesIO file, if applicable
        :return: Loaded attachment.
        """
        file = _to_path(file)
        if not file_name:
            if isinstance(file, io.BytesIO):
                raise ValueError("file_name must be specified when uploading a BytesIO object.")
            else:
                file_name = file.name

        mime_type = await run_blocking(detect_mime_type, file)
        size = _size(file)
        return cls(file, file_name, mime_type, size)

    @classmethod
    async def from_mxc(
        cls, client: "NioBot", url: str, *, force_write: U[bool, pathlib.Path] = False
    ) -> "BaseAttachment":
        """
        Creates an attachment from an MXC URL.

        :param client: The current client instance (used to download the attachment)
        :param url: The MXC:// url to download
        :param force_write: Whether to force writing downloaded attachments to a temporary file.
        :return: The downloaded and probed attachment.
        """
        # !!! warning "This function loads the entire attachment into memory."
        #     If you are downloading large attachments, you should set `force_write` to `True`, otherwise the downloaded
        #     attachment is pushed into an [`io.BytesIO`][] object (for speed benefits), which can cause memory issues
        #     on low-memory systems.
        #
        #     Bear in mind that most attachments are <= 100 megabytes. Also, forcing temp file writes may not be useful
        #     unless your temporary file directory is backed by a physical disk, because otherwise you're just loading
        #     into RAM with extra steps (for example, by default, `/tmp` is in-memory on linux, but `/var/tmp` is not).
        if force_write is not None:
            raise NotImplementedError("force_write is not implemented yet.")
        response = await client.download(url)
        if isinstance(response, nio.DownloadResponse):
            return await cls.from_file(io.BytesIO(response.body), response.filename)
        raise MediaDownloadException("Failed to download attachment.", response)

    @classmethod
    async def from_http(
        cls,
        url: str,
        client_session: typing.Optional[aiohttp.ClientSession] = None,
        *,
        force_write: U[bool, pathlib.Path] = False,
    ) -> "BaseAttachment":
        """
        Creates an attachment from an HTTP URL.

        This is not necessarily just for images, video, or other media - it can be used for any HTTP resource.

        :param url: The http/s URL to download
        :param client_session: The aiohttp client session to use. If not specified, a new one will be created.
        :param force_write: Whether to force stream the download to the file system, instead of into memory.
            See: [niobot.BaseAttachment.from_mxc][]
        :return: The downloaded and probed attachment.
        :raises niobot.MediaDownloadException: if the download failed.
        :raises aiohttp.ClientError: if the download failed.
        :raises niobot.MediaDetectionException: if the MIME type could not be detected.
        """
        if not client_session:
            from . import __user_agent__

            async with aiohttp.ClientSession(headers={"User-Agent": __user_agent__}) as session:
                return await cls.from_http(url, session, force_write=force_write)

        async with client_session.get(url) as response:
            try:
                response.raise_for_status()
            except aiohttp.ClientResponseError as err:
                raise MediaDownloadException("Failed to download attachment.", exception=err)

            file_name = response.headers.get("Content-Disposition")
            if file_name:
                file_name = re.search(r"filename=\"(.+)\"", file_name)
                if file_name:
                    file_name = file_name.group(1)

            if not file_name:
                u = urllib.parse.urlparse(url)
                file_name = os.path.basename(u.path)
            save_path = None
            if force_write is not False:
                if force_write is True:
                    tempdir = tempfile.gettempdir()
                elif isinstance(force_write, (os.PathLike, str)):
                    tempdir = pathlib.Path(str(force_write))

                if os.path.isdir(tempdir):
                    save_path = os.path.join(tempdir, file_name)
                else:
                    save_path = tempdir

            if save_path is None:
                return await cls.from_file(io.BytesIO(await response.read()), file_name)

            async with aiofiles.open(save_path, "wb") as fh:
                async for chunk in response.content.iter_chunked(1024):
                    await fh.write(chunk)
            return await cls.from_file(save_path, file_name)

    @property
    def size_bytes(self) -> int:
        """Returns the size of this attachment in bytes."""
        return self.size

    def size_as(
        self,
        unit: typing.Literal[
            "b",
            "kb",
            "kib",
            "mb",
            "mib",
            "gb",
            "gib",
        ],
    ) -> U[int, float]:
        """
        Helper function to convert the size of this attachment into a different unit.

        ??? example "Example"
            ```python
            >>> import niobot
            >>> attachment = niobot.FileAttachment("background.png", "image/png")
            >>> attachment.size_bytes
            329945
            >>> attachment.size_as("kb")
            329.945
            >>> attachment.size_as("kib")
            322.2119140625
            >>> attachment.size_as("mb")
            0.329945
            >>> attachment.size_as("mib")
            0.31466007232666016
            ```
            *Note that due to the nature of floats, precision may be lost, especially the larger in units you go.*

        :param unit: The unit to convert into
        :return: The converted size
        """
        multi = {
            "b": 1,
            "kb": 1000,
            "kib": 1024,
            "mb": 1000**2,
            "mib": 1024**2,
            "gb": 1000**3,
            "gib": 1024**3,
        }
        return self.size_bytes / multi[unit]

    async def upload(self, client: "NioBot", encrypted: bool = False) -> "BaseAttachment":
        """
        Uploads the file to matrix.

        :param client: The client to upload
        :param encrypted: Whether to encrypt the attachment or not
        :return: The attachment
        """
        if self.keys or self.url:
            raise RuntimeError("This attachment has already been uploaded.")
        if self.file_name is None:
            if hasattr(self.file, "name"):
                self.file_name = self.file.name
            else:
                raise ValueError("file_name must be specified when uploading a BytesIO object.")
        size = self.size or _size(self.file)

        if not isinstance(self.file, io.BytesIO):
            # We can open the file async here, as this will avoid blocking the loop
            async with aiofiles.open(self.file, "rb") as f:
                log.debug("Using aiofiles to open %r" % self.file)
                result, keys = await client.upload(
                    f,
                    content_type=self.mime_type,
                    filename=self.file_name,
                    encrypt=encrypted,
                    filesize=size,
                )
        else:
            # Usually, BytesIO objects are small enough to be uploaded synchronously. Plus, they're literally just
            # in-memory.
            # For scale, here is a 1GiB BytesIO with urandom() content, seek(0)ed and read() in its entirety, with
            # timeit:
            # 47.2 ns ± 0.367 ns per loop (mean ± std. dev. of 7 runs, 10,000,000 loops each)
            # So in reality, it's not going to be a massive problem.
            pos = self.file.tell()
            self.file.seek(0)
            log.debug("Uploading BytesIO object, seeked from position %d to 0, will restore after upload." % pos)
            result, keys = await client.upload(
                self.file,
                content_type=self.mime_type,
                filename=self.file_name,
                encrypt=encrypted,
                filesize=size,
            )
            self.file.seek(pos)
            log.debug("Uploaded BytesIO, seeked back to position %d." % pos)
        if not isinstance(result, nio.UploadResponse):
            raise MediaUploadException("Upload failed: %r" % result, result)

        if keys:
            self.keys = keys

        self.url = result.content_uri
        return self


class SupportXYZAmorganBlurHash(BaseAttachment):
    """
    Represents an attachment that supports blurhashes.

    :param xyz_amorgan_blurhash: The blurhash of the attachment
    :ivar xyz_amorgan_blurhash: The blurhash of the attachment
    """

    if typing.TYPE_CHECKING:
        xyz_amorgan_blurhash: str

    def __init__(self, *args, xyz_amorgan_blurhash: typing.Optional[str] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.xyz_amorgan_blurhash = xyz_amorgan_blurhash

    @classmethod
    async def from_file(
        cls,
        file: U[str, io.BytesIO, pathlib.Path],
        file_name: typing.Optional[str] = None,
        xyz_amorgan_blurhash: typing.Optional[U[str, bool]] = None,
    ) -> "SupportXYZAmorganBlurHash":
        file = _to_path(file)
        if isinstance(file, io.BytesIO):
            if not file_name:
                raise ValueError("file_name must be specified when uploading a BytesIO object.")
        else:
            if not file_name:
                file_name = file.name

        mime_type = await run_blocking(detect_mime_type, file)
        size = _size(file)
        self = cls(file, file_name, mime_type, size, xyz_amorgan_blurhash=xyz_amorgan_blurhash)
        if xyz_amorgan_blurhash is not False:
            await self.get_blurhash()
        return self

    @staticmethod
    def thumbnailify_image(
        image: U[PIL.Image.Image, io.BytesIO, str, pathlib.Path],
        size: typing.Tuple[int, int] = (320, 240),
        resampling: PIL.Image.Resampling = PIL.Image.Resampling.BICUBIC,
    ) -> PIL.Image.Image:
        """
        Helper function to thumbnail an image.

        This function is blocking - you should use [niobot.utils.run_blocking][] to run it.

        :param image: The image to thumbnail
        :param size: The size to thumbnail to. Defaults to 320x240, a standard thumbnail size.
        :param resampling: The resampling filter to use. Defaults to `PIL.Image.BICUBIC`, a high-quality but
        fast resampling method. For the highest quality, use `PIL.Image.LANCZOS`.
        :return: The thumbnail
        """
        if not isinstance(image, PIL.Image.Image):
            image = _to_path(image)
            image = PIL.Image.open(image)
        image.thumbnail(size, resampling)
        return image

    async def get_blurhash(
        self,
        quality: typing.Tuple[int, int] = (4, 3),
        file: typing.Optional[U[str, pathlib.Path, io.BytesIO, PIL.Image.Image]] = None,
        disable_auto_crop: bool = False,
    ) -> str:
        """
        Gets the blurhash of the attachment. See: [woltapp/blurhash](https://github.com/woltapp/blurhash)

        !!! tip "You should crop-down your blurhash images."
            Generating blurhashes can take a long time, *especially* on large images.
            You should crop-down your images to a reasonable size before generating the blurhash.

            Remember, most image quality is lost - there's very little point in generating a blurhash for a 4K image.
            Anything over 800x600 is definitely overkill.

            You can easily resize images with
            [SupportXYZAmorganBlurHash.thumbnailify_image][niobot.attachment.SupportXYZAmorganBlurHash.thumbnailify_image]:

            ```python
            attachment = await niobot.ImageAttachment.from_file(my_image, generate_blurhash=False)
            await attachment.get_blurhash(file=attachment.thumbnailify_image(attachment.file))
            ```

            This will generate a roughly 320x240 thumbnail image, and generate the blurhash from that.

            !!! tip "New!"
                Unless you pass `disable_auto_crop=True`, this function will automatically crop the image down to
                a reasonable size, before generating a blurhash.


        :param quality: A tuple of the quality to generate the blurhash at. Defaults to (4, 3).
        :param file: The file to generate the blurhash from. Defaults to the file passed in the constructor.
        :param disable_auto_crop: Whether to disable automatic cropping of the image. Defaults to False.
        :return: The blurhash
        """
        if isinstance(self.xyz_amorgan_blurhash, str):
            return self.xyz_amorgan_blurhash

        file = file or self.file
        if not isinstance(file, PIL.Image.Image):
            file = _to_path(file)
            file = PIL.Image.open(file)

        if disable_auto_crop is False and (file.width > 800 or file.height > 600):
            log.debug("Cropping image down from {0.width}x{0.height} to 800x600 for faster blurhashing".format(file))
            file.thumbnail((800, 600), PIL.Image.BICUBIC)
        x = await run_blocking(generate_blur_hash, file or self.file, *quality)
        self.xyz_amorgan_blurhash = x
        return x

    def as_body(self, body: typing.Optional[str] = None) -> dict:
        output_body = super().as_body(body)
        if isinstance(self.xyz_amorgan_blurhash, str):
            output_body["info"]["xyz.amorgan.blurhash"] = self.xyz_amorgan_blurhash
        return output_body


class FileAttachment(BaseAttachment):
    """
    Represents a generic file attachment.

    You should use [VideoAttachment][niobot.attachment.VideoAttachment] for videos,
    [AudioAttachment][niobot.attachment.AudioAttachment] for audio,
    and [ImageAttachment][niobot.attachment.ImageAttachment] for images.
    This is for everything else.

    :param file: The file to upload
    :param file_name: The name of the file
    :param mime_type: The mime type of the file
    :param size_bytes: The size of the file in bytes
    """

    def __init__(
        self,
        file: U[str, io.BytesIO, pathlib.Path],
        file_name: typing.Optional[str] = None,
        mime_type: typing.Optional[str] = None,
        size_bytes: typing.Optional[int] = None,
    ):
        super().__init__(file, file_name, mime_type, size_bytes, attachment_type=AttachmentType.FILE)


class ImageAttachment(SupportXYZAmorganBlurHash):
    """
    Represents an image attachment.

    :param file: The file to upload
    :param file_name: The name of the file
    :param mime_type: The mime type of the file
    :param size_bytes: The size of the file in bytes
    :param height: The height of the image in pixels (e.g. 1080)
    :param width: The width of the image in pixels (e.g. 1920)
    :param thumbnail: A thumbnail of the image. NOT a blurhash.
    :param xyz_amorgan_blurhash: The blurhash of the image

    :ivar info: A dict of info about the image. Contains `h`, `w`, `mimetype`, and `size` keys.
    :ivar thumbnail: A thumbnail of the image. NOT a blurhash.
    """

    def __init__(
        self,
        file: U[str, io.BytesIO, pathlib.Path],
        file_name: typing.Optional[str] = None,
        mime_type: typing.Optional[str] = None,
        size_bytes: typing.Optional[int] = None,
        height: typing.Optional[int] = None,
        width: typing.Optional[int] = None,
        thumbnail: typing.Optional["ImageAttachment"] = None,
        xyz_amorgan_blurhash: typing.Optional[str] = None,
    ):
        super().__init__(
            file,
            file_name,
            mime_type,
            size_bytes,
            xyz_amorgan_blurhash=xyz_amorgan_blurhash,
            attachment_type=AttachmentType.IMAGE,
        )
        self.info = {
            "h": height,
            "w": width,
            "mimetype": mime_type,
            "size": size_bytes,
        }
        self.thumbnail = thumbnail

    @property
    def height(self) -> typing.Optional[int]:
        """The height of this image in pixels"""
        return self.info["h"]

    @height.setter
    def height(self, value: typing.Optional[int]):
        self.info["h"] = value

    @property
    def width(self) -> typing.Optional[int]:
        """The width of this image in pixels"""
        return self.info["w"]

    @width.setter
    def width(self, value: typing.Optional[int]):
        self.info["w"] = value

    @classmethod
    async def from_file(
        cls,
        file: U[str, io.BytesIO, pathlib.Path],
        file_name: typing.Optional[str] = None,
        height: typing.Optional[int] = None,
        width: typing.Optional[int] = None,
        thumbnail: typing.Optional["ImageAttachment"] = None,
        generate_blurhash: bool = True,
        *,
        unsafe: bool = False,
    ) -> "ImageAttachment":
        """
        Generates an image attachment

        :param file: The file to upload
        :param file_name: The name of the file (only used if file is a `BytesIO`)
        :param height: The height, in pixels, of this image
        :param width: The width, in pixels, of this image
        :param thumbnail: A thumbnail for this image
        :param generate_blurhash: Whether to generate a blurhash for this image
        :param unsafe: Whether to allow uploading of images with unsupported codecs. May break metadata detection.
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
                for stream in metadata["streams"]:
                    log.debug("Found stream in image:\n%s", stream)
                    if stream["codec_type"] == "video":
                        if stream["codec_name"].lower() not in SUPPORTED_IMAGE_CODECS and unsafe is False:
                            warning = MediaCodecWarning(stream["codec_name"], *SUPPORTED_IMAGE_CODECS)
                            warnings.warn(warning)
                        log.debug("Selecting stream %r for image", stream)
                        break
                else:
                    raise ValueError("Unable to find an image stream in the given file. Are you sure its an image?")
                # ffmpeg doesn't have an image type
                height = stream["height"]
                width = stream["width"]

        mime_type = await run_blocking(detect_mime_type, file)
        size = _size(file)
        self = cls(file, file_name, mime_type, size, height, width, thumbnail)
        if generate_blurhash:
            await self.get_blurhash()
        return self

    def as_body(self, body: typing.Optional[str] = None) -> dict:
        output_body = super().as_body(body)
        output_body["info"] = {**output_body["info"], **self.info}
        if self.thumbnail:
            if self.thumbnail.keys:
                output_body["info"]["thumbnail_file"] = self.thumbnail.keys
            output_body["info"]["thumbnail_info"] = self.thumbnail.info
            output_body["info"]["thumbnail_url"] = self.thumbnail.url
        return output_body


class VideoAttachment(BaseAttachment):
    """
    Represents a video attachment.

    :param file: The file to upload
    :param file_name: The name of the file
    :param mime_type: The mime type of the file
    :param size_bytes: The size of the file in bytes
    :param height: The height of the video in pixels (e.g. 1080)
    :param width: The width of the video in pixels (e.g. 1920)
    :param duration: The duration of the video in seconds
    :param thumbnail: A thumbnail of the video. NOT a blurhash.
    """

    def __init__(
        self,
        file: U[str, io.BytesIO, pathlib.Path],
        file_name: typing.Optional[str] = None,
        mime_type: typing.Optional[str] = None,
        size_bytes: typing.Optional[int] = None,
        duration: typing.Optional[int] = None,
        height: typing.Optional[int] = None,
        width: typing.Optional[int] = None,
        thumbnail: typing.Optional["ImageAttachment"] = None,
    ):
        super().__init__(file, file_name, mime_type, size_bytes, attachment_type=AttachmentType.VIDEO)
        self.info = {
            "duration": duration,
            "h": height,
            "w": width,
            "mimetype": mime_type,
            "size": size_bytes,
        }
        self.thumbnail = thumbnail

    @property
    def duration(self) -> typing.Optional[int]:
        """The duration of this video in milliseconds"""
        return self.info["duration"]

    @duration.setter
    def duration(self, value: typing.Optional[int]):
        self.info["duration"] = value

    @property
    def height(self) -> typing.Optional[int]:
        """The height of this image in pixels"""
        return self.info["h"]

    @height.setter
    def height(self, value: typing.Optional[int]):
        self.info["h"] = value

    @property
    def width(self) -> typing.Optional[int]:
        """The width of this image in pixels"""
        return self.info["w"]

    @width.setter
    def width(self, value: typing.Optional[int]):
        self.info["w"] = value

    @classmethod
    async def from_file(
        cls,
        file: U[str, io.BytesIO, pathlib.Path],
        file_name: typing.Optional[str] = None,
        duration: typing.Optional[int] = None,
        height: typing.Optional[int] = None,
        width: typing.Optional[int] = None,
        thumbnail: typing.Optional[U[ImageAttachment, typing.Literal[False]]] = None,
        generate_blurhash: bool = True,
    ) -> "VideoAttachment":
        """
        Generates a video attachment

        !!! warning "This function auto-generates a thumbnail!"
            As thumbnails greatly improve user experience, even with blurhashes enabled, this function will by default
            create a thumbnail of the first frame of the given video if you do not provide one yourself.
            **This may increase your initialisation time by a couple seconds, give or take!**

            If this is undesirable, pass `thumbnail=False` to disable generating a thumbnail.
            This is independent of `generate_blurhash`.

            Generated thumbnails are always WebP images, so they will always be miniature, so you shouldn't
            notice a significant increase in upload time, especially considering your video will likely be several
            megabytes.

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
                for stream in metadata["streams"]:
                    if stream["codec_type"] == "video":
                        if stream["codec_name"].lower() not in SUPPORTED_VIDEO_CODECS or not stream[
                            "codec_name"
                        ].startswith(
                            "pcm_"
                        ):  # usually, pcm is supported.
                            warning = MediaCodecWarning(stream["codec_name"], *SUPPORTED_VIDEO_CODECS)
                            warnings.warn(warning)
                        height = stream["height"]
                        width = stream["width"]
                        duration = round(float(metadata["format"]["duration"]) * 1000)
                        break
                else:
                    raise ValueError("Could not find a video stream in this file.")

        mime_type = await run_blocking(detect_mime_type, file)
        size = _size(file)
        original_thumbnail = thumbnail
        if thumbnail is False:
            thumbnail = None
        self = cls(file, file_name, mime_type, size, duration, height, width, thumbnail)
        if generate_blurhash:
            if isinstance(self.thumbnail, ImageAttachment):
                await self.thumbnail.get_blurhash()
            elif isinstance(file, pathlib.Path) and original_thumbnail is not False:
                thumbnail_bytes = await run_blocking(first_frame, file)
                self.thumbnail = await ImageAttachment.from_file(
                    io.BytesIO(thumbnail_bytes), file_name="thumbnail.webp"
                )
        return self

    @staticmethod
    async def generate_thumbnail(video: U[str, pathlib.Path, "VideoAttachment"]) -> ImageAttachment:
        """
        Generates a thumbnail for a video.

        :param video: The video to generate a thumbnail for
        :return: The path to the generated thumbnail
        """
        if isinstance(video, VideoAttachment):
            if not isinstance(video.file, pathlib.Path):
                raise ValueError(
                    "VideoAttachment.file must be a pathlib.Path, BytesIOs are not supported for thumbnail generation"
                )
            video = video.file
        video = _to_path(video)
        x = await run_blocking(first_frame, video, "webp")
        return await ImageAttachment.from_file(io.BytesIO(x), file_name="thumbnail.webp")

    def as_body(self, body: typing.Optional[str] = None) -> dict:
        output_body = super().as_body(body)
        output_body["info"] = {**output_body["info"], **self.info}
        if self.thumbnail:
            if self.thumbnail.keys:
                output_body["info"]["thumbnail_file"] = self.thumbnail.keys
            output_body["info"]["thumbnail_info"] = self.thumbnail.info
            output_body["info"]["thumbnail_url"] = self.thumbnail.url
        return output_body


class AudioAttachment(BaseAttachment):
    """
    Represents an audio attachment.
    """

    def __init__(
        self,
        file: U[str, io.BytesIO, pathlib.Path],
        file_name: typing.Optional[str] = None,
        mime_type: typing.Optional[str] = None,
        size_bytes: typing.Optional[int] = None,
        duration: typing.Optional[int] = None,
    ):
        super().__init__(file, file_name, mime_type, size_bytes, attachment_type=AttachmentType.AUDIO)
        self.info = {
            "duration": duration,
            "mimetype": mime_type,
            "size": size_bytes,
        }

    @property
    def duration(self) -> typing.Optional[int]:
        """The duration of this audio in milliseconds"""
        return self.info["duration"]

    @duration.setter
    def duration(self, value: typing.Optional[int]):
        self.info["duration"] = value

    @classmethod
    async def from_file(
        cls,
        file: U[str, io.BytesIO, pathlib.Path],
        file_name: typing.Optional[str] = None,
        duration: typing.Optional[int] = None,
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

        mime_type = await run_blocking(detect_mime_type, file)
        size = _size(file)
        self = cls(file, file_name, mime_type, size, duration)
        return self

    def as_body(self, body: typing.Optional[str] = None) -> dict:
        output_body = super().as_body(body)
        output_body["info"] = {**output_body["info"], **self.info}
        return output_body
