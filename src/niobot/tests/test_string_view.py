import pytest
from src.niobot.utils.string_view import ArgumentView


@pytest.fixture(
    scope="session",
    params=[
        ("foo", ["foo"]),
        ("bar", ["bar"]),
        ("foo bar", ["foo", "bar"]),
        (" foo bar", ["foo", "bar"]),
        ("foo bar ", ["foo", "bar"]),
        ("'foo' bar", ["foo", "bar"]),
        ("foo 'bar'", ["foo", "bar"]),
        ("foo 'bar' baz", ["foo", "bar", "baz"]),
        ("foo 'bar baz'", ["foo", "bar baz"]),
        ("foo 'bar baz' qux", ["foo", "bar baz", "qux"]),
        ("foo 'bar baz' qux 'quux corge'", ["foo", "bar baz", "qux", "quux corge"]),
    ]
)
def test_string_view(value: str, expected: list[str]):
    view = ArgumentView(value)
    view.parse_arguments()
    assert view.arguments == expected, f"Expected {expected}, got {view.arguments}"
    return view

