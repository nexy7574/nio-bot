import io
import logging
import pathlib
import tempfile
import time
from typing import Any, Dict, Optional, Tuple, Type, Union

import PIL.Image
import blurhash
from typing_extensions import Self

from ..utils import deprecated, run_blocking
from ._util import _size, _to_path, detect_mime_type
from .base import AttachmentType, BaseAttachment

__all__ = ["ImageAttachment"]

log = logging.getLogger(__name__)


class ImageAttachment(BaseAttachment):
    """Represents an image attachment.

    :param file: The file to upload
    :param file_name: The name of the file
    :param mime_type: The mime type of the file
    :param size_bytes: The size of the file in bytes
    :param height: The height of the image in pixels (e.g. 1080)
    :param width: The width of the image in pixels (e.g. 1920)
    :param thumbnail: A thumbnail of the image. NOT a blurhash.
    :param xyz_amorgan_blurhash: The blurhash of the image
    :ivar thumbnail: A thumbnail of the image. NOT a blurhash.
    """

    def __init__(
        self,
        file: Union[str, io.BytesIO, pathlib.Path],
        file_name: Optional[str] = None,
        mime_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
        height: Optional[int] = None,
        width: Optional[int] = None,
        thumbnail: Optional["ImageAttachment"] = None,
        xyz_amorgan_blurhash: Optional[str] = None,
    ):
        super().__init__(
            file,
            file_name,
            mime_type,
            size_bytes,
            attachment_type=AttachmentType.IMAGE,
        )
        self.xyz_amorgan_blurhash = xyz_amorgan_blurhash
        self.height = height
        self.width = width
        self.mime_type = mime_type
        self.size = size_bytes
        self.thumbnail = thumbnail

    def as_body(self, body: Optional[str] = None) -> Dict:
        output_body = super().as_body(body)
        output_body["info"] = {"mimetype": self.mime_type, "size": self.size}
        if self.height is not None:
            output_body["info"]["h"] = self.height
        if self.width is not None:
            output_body["info"]["w"] = self.width

        if self.thumbnail:
            if self.thumbnail.keys:
                output_body["info"]["thumbnail_file"] = self.thumbnail.keys
            output_body["info"]["thumbnail_info"] = self.thumbnail.as_body()["info"]
            output_body["info"]["thumbnail_url"] = self.thumbnail.url
        if self.xyz_amorgan_blurhash:
            output_body["info"]["xyz.amorgan.blurhash"] = self.xyz_amorgan_blurhash
        return output_body

    @classmethod
    async def from_file(
        cls: Type["ImageAttachment"],
        file: Union[str, io.BytesIO, pathlib.Path],
        file_name: Optional[str] = None,
        height: Optional[int] = None,
        width: Optional[int] = None,
        thumbnail: Optional["ImageAttachment"] = None,
        generate_blurhash: bool = True,
        *,
        xyz_amorgan_blurhash: Optional[str] = None,
    ) -> "ImageAttachment":
        """Generates an image attachment

        :param file: The file to upload
        :param file_name: The name of the file (only used if file is a `BytesIO`)
        :param height: The height, in pixels, of this image
        :param width: The width, in pixels, of this image
        :param thumbnail: A thumbnail for this image
        :param generate_blurhash: Whether to generate a blurhash for this image
        :param xyz_amorgan_blurhash: The blurhash of the image, if known beforehand.
        :return: An image attachment
        """
        file = _to_path(file)
        if isinstance(file, io.BytesIO):
            if not file_name:
                raise ValueError("file_name must be specified when uploading a BytesIO object.")
            log.debug("Writing bytesio to tempfile in order to fetch metadata")
            with tempfile.NamedTemporaryFile(mode="wb", suffix=file_name) as fd:
                fd.write(file.getvalue())
                fd.seek(0)
                # It's best to work on a real file for imagemagick and ffmpeg.
                self = await cls.from_file(
                    file=fd.name,
                    file_name=file_name,
                    height=height,
                    width=width,
                    thumbnail=thumbnail,
                    generate_blurhash=generate_blurhash,
                    xyz_amorgan_blurhash=xyz_amorgan_blurhash,
                )
                fd.seek(0)
                with open(fd.name, "rb") as rfd:  # this is stupid
                    new_bytes_io = io.BytesIO()
                    new_bytes_io.write(rfd.read())
                    new_bytes_io.seek(0)
                    self.file = new_bytes_io
                    # ^ This is necessary to ensure the tempfile isn't lost before uploading
        else:
            if not file_name:
                file_name = file.name

            if height is None or width is None:
                try:
                    metadata = await cls.get_metadata(file)
                except (OSError, PIL.UnidentifiedImageError) as err:
                    log.warning("Failed to get metadata for %r: %r", file, err, exc_info=True)
                else:
                    for stream in metadata["streams"]:
                        if stream["codec_type"] == "video":
                            log.debug("Selecting stream %r for %r", stream, file)
                            height = stream["height"]
                            width = stream["width"]
                            break
                    log.debug("Detected resolution HxW for %s: %dx%d", file, height, width)

        mime_type = await run_blocking(detect_mime_type, file)
        size = _size(file)
        if height is None or width is None:
            log.warning("Width or Height (%r, %r) is None, this may break the display on some clients.", height, width)
        self = cls(
            file=file,
            file_name=file_name,
            mime_type=mime_type,
            size_bytes=size,
            height=height,
            width=width,
            thumbnail=thumbnail,
            xyz_amorgan_blurhash=xyz_amorgan_blurhash,
        )
        if generate_blurhash:
            try:
                await self.get_blurhash()
            except Exception as err:
                log.warning("Failed to generate blurhash for %r: %r", file, err, exc_info=True)
        return self

    @staticmethod
    def generate_blur_hash(
        file: Union[str, pathlib.Path, io.BytesIO, PIL.Image.Image],
        parts: Tuple[int, int] = (4, 3),
    ) -> str:
        """Creates a blurhash

        !!! warning "This function may be resource intensive"
            This function may be resource intensive, especially for large images. You should run this in a thread or
            process pool.

            You should also scale any images down in order to increase performance.

            See: [woltapp/blurhash](https://github.com/woltapp/blurhash)
        """
        # NOTE: In future, profile the pure-python blurhash implementation and see if it's worth using over the C one.
        if any(x not in range(1, 10) for x in parts):
            raise ValueError("Blurhash parts must be between 1 and 9")

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

    async def get_blurhash(
        self,
        quality: Tuple[int, int] = (4, 3),
        file: Optional[Union[str, pathlib.Path, io.BytesIO, PIL.Image.Image]] = None,
        disable_auto_crop: bool = False,
    ) -> str:
        """Gets the blurhash of the attachment. See: [woltapp/blurhash](https://github.com/woltapp/blurhash)

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
            log.debug("Opening %r as a PIL image", file)
            file = PIL.Image.open(file)

        if disable_auto_crop is False and (file.width > 800 or file.height > 600):
            log.debug(f"Cropping image down from {file.width}x{file.height} to 800x600 for faster blurhashing")
            file.thumbnail((800, 600), PIL.Image.Resampling.BICUBIC)
        x = await run_blocking(self.generate_blur_hash, file or self.file, quality)
        self.xyz_amorgan_blurhash = x
        return x

    @staticmethod
    def generate_thumbnail(
        image: Union[PIL.Image.Image, io.BytesIO, str, pathlib.Path],
        size: Tuple[int, int] = (320, 240),
        resampling: Union["PIL.Image.Resampling"] = PIL.Image.Resampling.BICUBIC,
    ) -> PIL.Image.Image:
        """Generates a small thumbnail of a large image.

        :param image: The image to generate a thumbnail of. Can be a PIL Image, BytesIO, or a path.
        :param size: The size of the thumbnail to generate in width x height. Defaults to (320, 240).
        :param resampling: The resampling algorithm to use. Defaults to `PIL.Image.Resampling.BICUBIC`.
        :return: The generated PIL image object
        """
        if not isinstance(image, PIL.Image.Image):
            image = _to_path(image)
            image = PIL.Image.open(image)
        image.thumbnail(size, resampling)
        return image

    @classmethod
    async def get_metadata(cls, file: Union[str, io.BytesIO, pathlib.Path]) -> Dict[str, Any]:
        """Gets metadata for an image.

        !!! danger "New in v1.3.0"
            This function is new in v1.3.0. Additionally, unlike the previous way of fetching metadata, this function
            does NOT fall back to using imagemagick/ffmpeg. If you use a format too new, it may error.
        """
        file = _to_path(file)
        if isinstance(file, io.BytesIO):
            with tempfile.NamedTemporaryFile() as f:
                f.write(file.getvalue())
                f.seek(0)
                return await cls.get_metadata(f.name)

        def runner(fd: pathlib.Path) -> Dict[str, Any]:
            with PIL.Image.open(fd) as img:
                return {
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

        assert isinstance(file, pathlib.Path), "file must be a pathlib.Path object, got %r" % type(file)
        # ^ This shouldn't happen as per _to_path, but we'll check just to be safe.
        return await run_blocking(runner, file)

    def set_thumbnail(self, thumbnail: "ImageAttachment") -> Self:
        """Sets the thumbnail for this image attachment.

        :param thumbnail: The thumbnail to set
        """
        self.thumbnail = thumbnail
        return self

    @staticmethod
    @deprecated("ImageAttachment.generate_thumbnail")
    def thumbnailify_image(*args):
        # Deprecated, will be removed in v1.4.0
        return ImageAttachment.generate_thumbnail(*args)
