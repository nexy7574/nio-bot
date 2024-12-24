import io
from pathlib import Path
from typing import Any, Dict, Optional, Type, Union

from .base import AttachmentType, BaseAttachment

__all__ = ("FileAttachment",)


class FileAttachment(BaseAttachment):
    """Represents a generic file attachment.

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
        file: Union[str, io.BytesIO, Path],
        file_name: Optional[str] = None,
        mime_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
    ):
        super().__init__(file, file_name, mime_type, size_bytes, attachment_type=AttachmentType.FILE)

    @classmethod
    async def get_metadata(cls: Type["BaseAttachment"], file: Union[str, io.BytesIO, Path]) -> Dict[str, Any]:
        """Dud method, there's no metadata to fetch for a generic file."""
        # yet...
        # Would be neat if you could have some custom file info, like a hash or something
        # but alas, no spec/client support, or need really
        return {}
