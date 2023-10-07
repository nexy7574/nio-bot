import niobot
import pytest
import pathlib

ASSETS = pathlib.Path(__file__).parent / "assets"


@pytest.mark.parametrize(
    "file_path, expected",
    [
        (ASSETS / "sample-5s-compressed.mp4", niobot.VideoAttachment),
        (ASSETS / "sample-15s.ogg", niobot.AudioAttachment),
        (ASSETS / "sample-clouds.avif", niobot.ImageAttachment),
        (ASSETS / "sample-lipsum-10.txt", niobot.FileAttachment),
    ],
)
def test_which(file_path: pathlib.Path, expected):
    assert niobot.which(file_path) == expected


@pytest.mark.parametrize(
    "file_path, expected",
    [
        (ASSETS / "sample-5s-compressed.mp4", "video/mp4"),
        (ASSETS / "sample-15s.ogg", "audio/ogg"),
        (ASSETS / "sample-clouds.avif", "image/avif"),
        (ASSETS / "sample-lipsum-10.txt", "text/csv"),  # while it is a text file, this does technically yield csv.
    ],
)
def test_mimetype_detection(file_path: pathlib.Path, expected: str):
    assert niobot.detect_mime_type(file_path) == expected, str(file_path)
