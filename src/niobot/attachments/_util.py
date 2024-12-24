import io
import logging
import mimetypes
import os
import sys
import time
import warnings
from pathlib import Path
from typing import Literal, Union, overload

try:
    import magic
except ImportError:
    magic = None


__all__ = (
    "_file_okay",
    "_size",
    "_to_path",
    "detect_mime_type",
)


log = logging.getLogger(__name__)


def detect_mime_type(file: Union[str, io.BytesIO, Path]) -> str:
    """Detect the mime type of a file.

    :param file: The file to detect the mime type of. Can be a BytesIO.
    :return: The mime type of the file (e.g. `text/plain`, `image/png`, `application/pdf`, `video/webp` etc.)
    :raises RuntimeError: If the `magic` library is not installed.
    :raises TypeError: If the file is not a string, BytesIO, or Path object.
    """
    file = _to_path(file)
    if not magic:
        log.warning("magic is not installed. Falling back to extension-based detection")

    if isinstance(file, io.BytesIO):
        current_position = file.tell()
        file.seek(0)
        start = time.perf_counter()
        mt = magic.from_buffer(file.read(), mime=True)
        log.debug("Took %f seconds to detect mime type", time.perf_counter() - start)
        file.seek(current_position)  # Reset the file position
        return mt
    if isinstance(file, Path):
        start = time.perf_counter()
        if magic:
            mt = magic.from_file(str(file), mime=True)
        else:
            if sys.version_info >= (3, 11):
                mt = mimetypes.guess_file_type(str(file))[0]
            else:
                mt = mimetypes.guess_type(str(file))[0]
            mt = mt or "application/octet-stream"
        log.debug("Took %f seconds to detect mime type", time.perf_counter() - start)
        return mt
    raise TypeError("File must be a string, BytesIO, or Path object.")


def _file_okay(file: Union[Path, io.BytesIO]) -> Literal[True]:
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
def _to_path(file: Union[str, os.PathLike, Path]) -> Path: ...


@overload
def _to_path(file: io.BytesIO) -> io.BytesIO: ...


def _to_path(file: Union[str, Path, io.BytesIO]) -> Union[Path, io.BytesIO]:
    """Converts a string to a Path object."""
    if not isinstance(file, (str, Path, os.PathLike, io.BytesIO)):
        raise TypeError("File must be a string, BytesIO, or Path object.")

    if isinstance(file, str):
        file = Path(file)
    elif isinstance(file, os.PathLike) and not isinstance(file, Path):
        file = Path(file.__fspath__())
    elif isinstance(file, io.BytesIO):
        return file

    return file.resolve()


def _size(file: Union[Path, io.BytesIO]) -> int:
    """Gets the size of a file."""
    if isinstance(file, io.BytesIO):
        return len(file.getbuffer())
    return file.stat().st_size
