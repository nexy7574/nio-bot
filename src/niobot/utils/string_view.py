import logging

# Inspiration from https://github.com/Pycord-Development/pycord/blob/36fea3/discord/ext/commands/view.py#L55

__all__ = ("QUOTES", "ArgumentView")

QUOTES = ['"', "'", "`"]

log = logging.getLogger(__name__)


class ArgumentView:
    """A parser designed to allow for multi-word arguments and quotes

    For example, the arguments `1 "2 3" 4` would result in three items in the internal list:
    `1`, `2 3`, and `4`

    This is most useful when parsing arguments from a command, as it allows for multi-word arguments.

    :param string: The string to parse
    """

    def __init__(self, string: str):
        self.source = string
        self.index = 0

        self.arguments: list[str] = []

    def add_arg(self, argument: str) -> None:
        """Adds an argument to the argument list

        :param argument: The argument to add
        :return: none"""
        if not argument:
            return
        self.arguments.append(argument)

    @property
    def eof(self) -> bool:
        """Returns whether the parser has reached the end of the string

        :return: Whether the parser has reached the end of the string
        (cursor is greater than or equal to the length of the string)
        """
        return self.index >= len(self.source)

    def parse_arguments(self) -> "ArgumentView":
        """Main parsing engine.

        :returns: self"""
        reconstructed = ""
        quote_started = False
        quote_char = None
        while not self.eof:
            char = self.source[self.index]
            if char in QUOTES:
                # if we're already quoted, we need to check if the last character was an escape (\\)
                # If it is escaped, add it to the string.
                # If it isn't, we can end the quote.
                if quote_started:
                    if self.index > 0 and (self.source[self.index - 1] == "\\" or quote_char != char):
                        reconstructed += char
                    else:
                        quote_started = False
                        self.add_arg(reconstructed)
                        reconstructed = ""
                        quote_char = None
                elif self.index == 0:  # cannot be an escaped string
                    quote_started = True
                    quote_char = char
                elif self.index > 0 and self.source[self.index - 1] != "\\":
                    quote_started = True
                    quote_char = char
                else:
                    reconstructed += char
            elif char.isspace():
                if quote_started:
                    reconstructed += char
                else:
                    self.add_arg(reconstructed)
                    reconstructed = ""
                    quote_char = None
            elif char:  # elif ensures the character isn't null
                reconstructed += char
            self.index += 1
        # If we have a reconstructed string, we can add it to the arguments list
        if reconstructed:
            self.add_arg(reconstructed)
        return self
