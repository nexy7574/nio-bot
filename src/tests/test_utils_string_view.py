import pytest

from niobot.utils.string_view import ArgumentView

STRINGS = [
    [
        "hello world",
        ["hello", "world"]
    ],
    [
        "hello 'world'",
        ["hello", "world"]
    ],
    [
        "'hello world'",
        ["hello world"]
    ],
    [
        "hello 'world' 'two'",
        ["hello", "world", "two"]
    ],
    [
        "hello 'world two'",
        ["hello", "world two"]
    ],
    [
        "hello 'world two' three",
        ["hello", "world two", "three"]
    ],
    [
        "\"hello 'world'\"",
        ["hello 'world'"]
    ],
    [
        """Hello "'`world`'"!""",
        ["Hello", "'`world`'", "!"]
    ],
    [
        '''"""hello world"""''',
        ["hello world"]
    ],
    [
        """'''hello world''""",
        ["hello world"]
    ]
]

@pytest.mark.parametrize("string, expected", STRINGS)
def test_string_view(string, expected):
    sv = ArgumentView(string)
    sv.parse_arguments()
    assert sv.arguments == expected
