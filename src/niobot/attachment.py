# This file is deprecated, and instead you should use the types in `niobot.attachments`.

from __future__ import annotations

import io
import json
import logging
import pathlib
import shutil
import subprocess
import tempfile
import time
from typing import IO, Any, Dict, Optional, Type, TypeVar, Union

import PIL.Image

from .attachments import *

# noinspection PyProtectedMember
from .attachments._util import _to_path

try:
    import magic
except ImportError:
    logging.getLogger(__name__).critical(
        "Failed to load magic. Automatic file type detection will be unavailable. Please install python3-magic.",
    )
    magic = None

from .exceptions import MediaUploadException, MetadataDetectionException
from .utils import deprecated

log = logging.getLogger(__name__)
_CT = TypeVar("_CT", bound=Union[str, bytes, pathlib.Path, IO[bytes]])


__all__ = (
    "AttachmentType",
    "AudioAttachment",
    "BaseAttachment",
    "FileAttachment",
    "ImageAttachment",
    "VideoAttachment",
    "detect_mime_type",
    "first_frame",
    "get_metadata",
    "get_metadata_ffmpeg",
    "get_metadata_imagemagick",
    "which",
)


@deprecated("<T>Attachment.get_metadata")
def get_metadata_ffmpeg(file: Union[str, pathlib.Path]) -> Dict[str, Any]:
    # Deprecated, will be removed in v1.4.0
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


@deprecated("<T>Attachment.get_metadata")
def get_metadata_imagemagick(file: pathlib.Path) -> Dict[str, Any]:
    # Deprecated, will be removed in v1.4.0
    file = file.resolve(True)
    command = ["identify", "-format", "%m,%w,%h", str(file)]
    start = time.perf_counter()
    try:
        result = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace", check=True)
    except subprocess.SubprocessError as e:
        raise MetadataDetectionException("Failed to get metadata for file.", exception=e)
    log.debug("identify output (%d): %s", result.returncode, result.stdout)
    log.debug("identify took %f seconds", time.perf_counter() - start)
    stdout = result.stdout
    stdout = stdout[len(str(file)) + 1 :]
    img_format, img_width, img_height = stdout.split(",")
    data = {
        "streams": [
            {
                "index": 0,
                "codec_name": img_format,
                "codec_long_name": img_format,
                "codec_type": "video",
                "height": int(img_height),
                "width": int(img_width),
            },
        ],
        "format": {
            "filename": str(file),
            "format_long_name": img_format,
            "size": str(file.stat().st_size),
        },
    }
    log.debug("Parsed identify output:\n%s", json.dumps(data, indent=4))
    return data


@deprecated("<T>Attachment.get_metadata")
def get_metadata(file: Union[str, pathlib.Path], mime_type: Optional[str] = None) -> Dict[str, Any]:
    # Deprecated, will be removed in v1.4.0
    file = _to_path(file)
    mime = mime_type or detect_mime_type(file)
    mime = mime.split("/")[0]
    if mime == "image":
        # First, try using PIL to get the metadata
        try:
            log.debug("Using PIL to detect metadata for %r", file)
            with PIL.Image.open(file) as img:
                data = {
                    "streams": [
                        {
                            "index": 0,
                            "codec_name": img.format,
                            "codec_long_name": img.format,
                            "codec_type": "video",
                            "height": img.height,
                            "width": img.width,
                        },
                    ],
                    "format": {
                        "filename": str(file),
                        "format_long_name": img.format,
                        "size": file.stat().st_size,
                    },
                }
                log.debug("PIL metadata for %r: %r", file, data)
                return data
        except (PIL.UnidentifiedImageError, OSError):
            log.warning("Failed to detect metadata for %r with PIL. Falling back to imagemagick.", file, exc_info=True)
            if not shutil.which("identify"):
                log.warning(
                    "Imagemagick identify not found, falling back to ffmpeg for image metadata detection. "
                    "Check your $PATH.",
                )
            else:
                start = time.perf_counter()

                try:
                    r = get_metadata_imagemagick(file)
                    log.debug("get_metadata_imagemagick took %f seconds", time.perf_counter() - start)
                    log.debug("identify detected data for %r: %r", file, r)
                    return r
                except (IndexError, ValueError, subprocess.SubprocessError, OSError):
                    log.warning(
                        "Failed to detect metadata for %r with imagemagick. Falling back to ffmpeg.",
                        file,
                        exc_info=True,
                    )

    if mime not in ["audio", "video", "image"]:
        raise MetadataDetectionException("Unsupported mime type. Must be an audio clip, video, or image.")
    start = time.perf_counter()
    log.debug("Getting metadata for %r with ffprobe", file)
    r = get_metadata_ffmpeg(file)
    log.debug("get_metadata_ffmpeg took %f seconds", time.perf_counter() - start)
    log.debug("ffprobe detected data for %r: %r", file, r)
    return r


@deprecated("VideoAttachment.first_frame")
def first_frame(file: Union[str, pathlib.Path], file_format: str = "webp") -> bytes:
    # Deprecated, will be removed in v1.4.0
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


def which(
    file: Union[io.BytesIO, pathlib.Path, str],
    mime_type: Optional[str] = None,
) -> Union[
    Type[FileAttachment],
    Type[ImageAttachment],
    Type[AudioAttachment],
    Type[VideoAttachment],
]:
    """Gets the correct attachment type for a file.

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
