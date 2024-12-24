import abc
import enum
import io
import logging
import os
import re
import urllib.parse
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Literal, Optional, Type, Union, overload

import aiofiles
import aiohttp
import nio
from typing_extensions import Self

from ..exceptions import MediaDownloadException, MediaUploadException
from ..utils import run_blocking
from ._util import _size, _to_path, detect_mime_type

__all__ = (
    "AttachmentType",
    "BaseAttachment",
)

log = logging.getLogger(__name__)


class AttachmentType(enum.Enum):
    """Enumeration containing the different types of media.

    :var FILE: A generic file.
    :var AUDIO: An audio file.
    :var VIDEO: A video file.
    :var IMAGE: An image file.
    """

    if TYPE_CHECKING:
        FILE: "AttachmentType"
        AUDIO: "AttachmentType"
        VIDEO: "AttachmentType"
        IMAGE: "AttachmentType"
    FILE = "m.file"
    AUDIO = "m.audio"
    VIDEO = "m.video"
    IMAGE = "m.image"


class BaseAttachment(abc.ABC):
    """Base class for attachments

    !!! note
        If you pass a custom `file_name`, this is only actually used if you pass a [io.BytesIO][] to `file`.
        If you pass a [Path][] or a [string][str], the file name will be resolved from the path, overriding
        the `file_name` parameter.

    :param file: The file path or BytesIO object to upload.
    :param file_name: The name of the file. **Must be specified if uploading a BytesIO object.**
    :param mime_type: The mime type of the file. If not specified, it will be detected.
    :param size_bytes: The size of the file in bytes. If not specified, it will be detected.
    :param attachment_type: The type of attachment. Defaults to `AttachmentType.FILE`.

    :ivar file: The file path or BytesIO object to upload. Resolved to a [Path][] object if a string is
    passed to `__init__`.
    :ivar file_name: The name of the file. If `file` was a string or `Path`, this will be the name of the file.
    :ivar mime_type: The mime type of the file.
    :ivar size: The size of the file in bytes.
    :ivar type: The type of attachment.
    :ivar url: The URL of the uploaded file. This is set after the file is uploaded.
    :ivar keys: The encryption keys for the file. This is set after the file is uploaded.
    """

    if TYPE_CHECKING:
        file: Union[Path, io.BytesIO]
        file_name: str
        mime_type: str
        size: int
        type: AttachmentType

        url: Optional[str]
        keys: Optional[dict[str, str]]

    @overload
    def __init__(
        self,
        file: io.BytesIO,
        file_name: str,
        mime_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
        *,
        attachment_type: AttachmentType = AttachmentType.FILE,
    ): ...

    @overload
    def __init__(
        self,
        file: Union[str, os.PathLike, Path],
        file_name: Optional[str] = None,
        mime_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
        *,
        attachment_type: AttachmentType = AttachmentType.FILE,
    ): ...

    def __init__(
        self,
        file: Union[str, io.BytesIO, os.PathLike, Path],
        file_name: Optional[str] = None,
        mime_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
        *,
        attachment_type: AttachmentType = AttachmentType.FILE,
    ):
        self.file = _to_path(file)
        # Ignore type error as the type is checked right afterwards
        self.file_name = file_name  # type: ignore
        if file_name is None and hasattr(self.file, "name"):
            self.file_name = file.name

        if not self.file_name:
            raise ValueError("file_name must be specified when uploading a BytesIO object.")

        self.mime_type = mime_type or detect_mime_type(self.file)

        if size_bytes:
            self.size = size_bytes
        elif isinstance(self.file, io.BytesIO):
            self.size = len(self.file.getbuffer())
        else:
            self.size = os.path.getsize(self.file)

        self.type = attachment_type

        self.url = None
        self.keys = None

    def __repr__(self):
        return (
            f"<{self.__class__.__name__} file={self.file!r} file_name={self.file_name!r} "
            f"mime_type={self.mime_type!r} size={self.size!r} type={self.type!r}>"
        )

    def as_body(self, body: Optional[str] = None) -> dict:
        """Generates the body for the attachment for sending. The attachment must've been uploaded first.

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
        file: Union[str, io.BytesIO, Path],
        file_name: Optional[str] = None,
    ) -> "BaseAttachment":
        """Creates an attachment from a file.

        You should use this method instead of the constructor, as it will automatically detect all other values

        :param file: The file or BytesIO to attach
        :param file_name: The name of the BytesIO file, if applicable
        :return: Loaded attachment.
        """
        file = _to_path(file)
        if not file_name:
            if isinstance(file, io.BytesIO):
                raise ValueError("file_name must be specified when uploading a BytesIO object.")
            file_name = file.name

        mime_type = await run_blocking(detect_mime_type, file)
        size = _size(file)
        return cls(file, file_name, mime_type, size)

    @classmethod
    async def from_mxc(cls, client, url: str) -> "BaseAttachment":
        """Creates an attachment from an MXC URL.

        :param client: The current client instance (used to download the attachment)
        :param url: The MXC:// url to download
        :return: The downloaded and probed attachment.
        """
        response = await client.download(url)
        if isinstance(response, nio.DownloadResponse):
            # noinspection PyTypeChecker
            return await cls.from_file(io.BytesIO(response.body), response.filename)
        raise MediaDownloadException("Failed to download attachment.", response)

    @classmethod
    async def from_http(
        cls,
        url: str,
        client_session: Optional[aiohttp.ClientSession] = None,
    ) -> "BaseAttachment":
        """Creates an attachment from an HTTP URL.

        This is not necessarily just for images, video, or other media - it can be used for any HTTP resource.

        :param url: The http/s URL to download
        :param client_session: The aiohttp client session to use. If not specified, a new one will be created.
        :return: The downloaded and probed attachment.
        :raises niobot.MediaDownloadException: if the download failed.
        :raises aiohttp.ClientError: if the download failed.
        :raises niobot.MediaDetectionException: if the MIME type could not be detected.
        """
        if not client_session:
            from .. import __user_agent__

            async with aiohttp.ClientSession(headers={"User-Agent": __user_agent__}) as session:
                return await cls.from_http(url, session)

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

            # noinspection PyTypeChecker
            return await cls.from_file(io.BytesIO(await response.read()), file_name)

    @property
    def size_bytes(self) -> int:
        """Returns the size of this attachment in bytes."""
        return self.size

    def size_as(
        self,
        unit: Literal[
            "b",
            "kb",
            "kib",
            "mb",
            "mib",
            "gb",
            "gib",
        ],
    ) -> Union[int, float]:
        """Helper function to convert the size of this attachment into a different unit.

        Remember:

        - 1 kilobyte (KB) is 1000 bytes
        - 1 kibibyte (KiB) is 1024 bytes

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

    async def upload(self, client, encrypted: bool = False) -> Self:
        """Uploads the file to matrix.

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

    @classmethod
    @abc.abstractmethod
    async def get_metadata(cls: Type["BaseAttachment"], file: Union[str, io.BytesIO, Path]) -> Dict[str, Any]:
        """Gets metadata for a file."""
        raise NotImplementedError("This method must be implemented in a subclass.")
