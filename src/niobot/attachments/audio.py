import asyncio
import io
import json
import logging
import shlex
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional, Type, Union

from ..exceptions import MetadataDetectionException
from ..utils import run_blocking
from ._util import _size, _to_path, detect_mime_type
from .base import AttachmentType, BaseAttachment

__all__ = ("AudioAttachment",)
log = logging.getLogger(__name__)


class AudioAttachment(BaseAttachment):
    """Represents an audio attachment."""

    def __init__(
        self,
        file: Union[str, io.BytesIO, Path],
        file_name: Optional[str] = None,
        mime_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
        duration: Optional[int] = None,
    ):
        super().__init__(file, file_name, mime_type, size_bytes, attachment_type=AttachmentType.AUDIO)
        self.info = {
            "duration": duration,
            "mimetype": mime_type,
            "size": size_bytes,
        }

    def as_body(self, body: Optional[str] = None) -> dict:
        output_body = super().as_body(body)
        info = self.info.copy()
        if info.get("duration") is None:
            info.pop("duration", None)
        output_body["info"] = {**output_body["info"], **self.info}
        return output_body

    @property
    def duration(self) -> Optional[int]:
        """The duration of this audio in milliseconds"""
        return self.info["duration"]

    @duration.setter
    def duration(self, value: Optional[int]):
        self.info["duration"] = value

    @classmethod
    async def from_file(
        cls,
        file: Union[str, io.BytesIO, Path],
        file_name: Optional[str] = None,
        duration: Optional[int] = None,
    ) -> "AudioAttachment":
        """Generates an audio attachment

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
                metadata = await AudioAttachment.get_metadata(file)
                duration = round(float(metadata["format"]["duration"]) * 1000)

        mime_type = await run_blocking(detect_mime_type, file)
        size = _size(file)
        self = cls(file, file_name, mime_type, size, duration)
        return self

    @classmethod
    async def get_metadata(cls: Type[BaseAttachment], file: Union[str, Path]) -> Dict[str, Any]:
        """Get metadata about an audio file.

        :param file: The audio file to get metadata for
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
