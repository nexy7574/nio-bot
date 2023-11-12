import pathlib
import typing

import niobot
import pytest

ASSETS = pathlib.Path(__file__).parent / "assets"


@pytest.mark.parametrize(
    "file_path, expected",
    [
        (ASSETS / "sample-5s-compressed.mp4", niobot.VideoAttachment),
        (ASSETS / "sample-15s.ogg", niobot.AudioAttachment),
        (ASSETS / "sample-clouds.webp", niobot.ImageAttachment),
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
        (ASSETS / "sample-clouds.webp", "image/webp"),
        (ASSETS / "sample-lipsum-10.txt", "text/csv"),  # while it is a text file, this does technically yield csv.
    ],
)
def test_mimetype_detection(file_path: pathlib.Path, expected: str):
    assert niobot.detect_mime_type(file_path) == expected, str(file_path)


@pytest.mark.parametrize(
    "file_path, expected_type, expected_values",
    [
        (ASSETS / "sample-15s.ogg", niobot.AudioAttachment, {"duration": 19.18 * 1000}),
        (
            ASSETS / "sample-5s-compressed.mp4",
            niobot.VideoAttachment,
            {
                "duration": 5758,
                "height": 1080,
                "width": 1920,
            },
        ),
        (
            ASSETS / "sample-clouds.webp",
            niobot.ImageAttachment,
            {
                "height": 300,
                "width": 400,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_rich_data_detection(file_path: pathlib.Path, expected_type, expected_values: dict[str, typing.Any]):
    _type = niobot.which(file_path)
    assert _type == expected_type, "%s was %r, not %r." % (str(file_path), _type, expected_type)
    instance = await _type.from_file(file_path)

    for key, value in expected_values.items():
        attr = getattr(instance, key)
        assert attr == value, f"{key} does not match (expected {value!r}, got {attr!r})"
