import asyncio
import io
import json
import logging
import shlex
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Type, Union

from ..exceptions import MetadataDetectionException
from ..utils import deprecated, run_blocking
from ._util import _size, _to_path, detect_mime_type
from .base import AttachmentType, BaseAttachment
from .image import ImageAttachment

log = logging.getLogger(__name__)


__all__ = ("VideoAttachment",)


class VideoAttachment(BaseAttachment):
    """Represents a video attachment.

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
        file: Union[str, io.BytesIO, Path],
        file_name: Optional[str] = None,
        mime_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
        duration: Optional[int] = None,
        height: Optional[int] = None,
        width: Optional[int] = None,
        thumbnail: Optional["ImageAttachment"] = None,
    ):
        super().__init__(file, file_name, mime_type, size_bytes, attachment_type=AttachmentType.VIDEO)
        self.width = width
        self.height = height
        self.duration = duration
        self.thumbnail = thumbnail

    def as_body(self, body: Optional[str] = None) -> dict:
        output_body = super().as_body(body)
        info = {"mimetype": self.mime_type, "size": self.size_bytes}
        if self.height:
            info["h"] = self.height
        if self.width:
            info["w"] = self.width
        if self.duration:
            info["duration"] = self.duration
        output_body["info"] = {**output_body["info"], **info}
        if self.thumbnail:
            if self.thumbnail.keys:
                output_body["info"]["thumbnail_file"] = self.thumbnail.keys
            output_body["info"]["thumbnail_info"] = self.thumbnail.as_body()["info"]
            output_body["info"]["thumbnail_url"] = self.thumbnail.url
        return output_body

    @staticmethod
    async def generate_thumbnail(video: Union[str, Path, "VideoAttachment"]) -> ImageAttachment:
        """Generates a thumbnail for a video.

        :param video: The video to generate a thumbnail for
        :return: The path to the generated thumbnail
        """
        if isinstance(video, VideoAttachment):
            if not isinstance(video.file, Path):
                raise ValueError(
                    "VideoAttachment.file must be a Path, BytesIOs are not supported for thumbnail generation",
                )
            video = video.file
        video = _to_path(video)
        x = await run_blocking(VideoAttachment.extract_first_frame, video, "webp")
        return await ImageAttachment.from_file(io.BytesIO(x), file_name="thumbnail.webp", thumbnail=False)

    @classmethod
    async def get_metadata(cls: Type[BaseAttachment], file: Union[str, Path]) -> Dict[str, Any]:
        """Get metadata about a video file.

        :param file: The video file to get metadata for
        :return: The metadata
        """
        if isinstance(file, io.BytesIO):
            raise TypeError("Cannot get metadata for a BytesIO object.")
            # Perhaps it's possible to pass via stdin? unsure. Maybe for a future version.

        file = _to_path(file)
        if not shutil.which("ffprobe"):
            raise FileNotFoundError("ffprobe is not installed. If it is, check your $PATH.")
        command = ["ffprobe", "-of", "json", "-loglevel", "9", "-show_format", "-show_streams", "-i", str(file)]
        start = time.perf_counter()
        log.debug("Running ffprobe: %s", shlex.join(command))
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        stdout = stdout.decode("utf-8")
        stderr = stderr.decode("utf-8")
        if proc.returncode != 0:
            raise MetadataDetectionException(f"ffprobe failed with return code {proc.returncode}:\n{stderr}")

        log.debug("Took %f seconds to run ffprobe", time.perf_counter() - start)
        log.debug("ffprobe output (%d): %s", proc.returncode, stdout)
        data = json.loads(stdout or "{}")
        log.debug("parsed ffprobe output:\n%s", json.dumps(data, indent=4))
        return data

    @staticmethod
    @deprecated("VideoAttachment.extract_first_frame")
    async def first_frame(file: Union[str, Path], file_format: str = "webp") -> bytes:
        # Will be removed in v1.4.0
        return await VideoAttachment.extract_first_frame(file, file_format)

    @staticmethod
    async def extract_first_frame(file: Union[str, Path], file_format: str = "webp") -> bytes:
        """Gets the first frame of a video.

        :param file: The video file to get the first frame of
        :param file_format: The format to save the first frame in. Defaults to WebP, which is a good choice.
        :return: The first frame
        """
        if not shutil.which("ffmpeg"):
            raise FileNotFoundError("ffmpeg is not installed. If it is, check your $PATH.")
        file = _to_path(file)

        def runner():
            with tempfile.NamedTemporaryFile(suffix=f".{file_format}") as f:
                command = ["ffmpeg", "-loglevel", "9", "-i", str(file), "-frames:v", "1", "-y", "-strict", "-2", f.name]
                log.debug("Extracting first frame of %r: %s", file, " ".join(command))
                start = time.perf_counter()
                log.debug(
                    "Extraction return code: %d",
                    subprocess.run(command, capture_output=True, check=True).returncode,
                )
                # Exceptions are intentionally propagated ^
                # TODO: use asyncio.create_subprocess_exec instead of dispatching to a thread.
                log.debug("Frame extraction took %f seconds", time.perf_counter() - start)
                f.seek(0)
                return f.read()

        return await run_blocking(runner)

    @classmethod
    async def from_file(
        cls,
        file: Union[str, io.BytesIO, Path],
        file_name: Optional[str] = None,
        duration: Optional[int] = None,
        height: Optional[int] = None,
        width: Optional[int] = None,
        thumbnail: Optional[Union[ImageAttachment, Literal[False]]] = None,
        generate_blurhash: bool = True,
    ) -> "VideoAttachment":
        """Generates a video attachment

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
                log.debug("Width/height/duration is None, fetching data with ffprobe.")
                metadata = await VideoAttachment.get_metadata(file)
                for stream in metadata["streams"]:
                    if stream["codec_type"] == "video":
                        height = stream["height"]
                        width = stream["width"]
                        duration = round(float(metadata["format"]["duration"]) * 1000)
                        break
                else:
                    raise ValueError("Could not find a video stream in this file.")
                log.debug("Resolved width/height/duration to %dx%d for %r.", width, height, file)

        mime_type = await run_blocking(detect_mime_type, file)
        size = _size(file)
        original_thumbnail = thumbnail
        if thumbnail is False:
            thumbnail = None
        # noinspection PyTypeChecker
        self = cls(file, file_name, mime_type, size, duration, height, width, thumbnail)
        if generate_blurhash:
            if isinstance(self.thumbnail, ImageAttachment):
                await self.thumbnail.get_blurhash()
            elif isinstance(file, Path) and original_thumbnail is not False:
                thumbnail_bytes = await VideoAttachment.extract_first_frame(file)
                self.thumbnail = await ImageAttachment.from_file(
                    io.BytesIO(thumbnail_bytes), file_name="thumbnail.webp", thumbnail=False
                )
                assert self.thumbnail.as_body()["info"].get("w", ...) is not None, "null width abort"
                assert self.thumbnail.as_body()["info"].get("h", ...) is not None, "null height abort"
            else:
                raise TypeError("Unsure how to blurhash type %r" % type(self.thumbnail))
        return self
