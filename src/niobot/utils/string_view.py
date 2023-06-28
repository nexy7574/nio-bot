import logging
# Inspiration from https://github.com/Pycord-Development/pycord/blob/36fea3/discord/ext/commands/view.py#L55

__all__ = (
    "QUOTES",
    "ArgumentView"
)

QUOTES = ['"', "'", '`']

log = logging.getLogger(__name__)


class ArgumentView:
    def __init__(self, string: str):
        # if not string:
        #     raise ValueError("Cannot create an empty view")
        self.source = string
        self.index = 0

        self.arguments = []

    def add_arg(self, argument: str):
        if not argument:
            log.warning("Blank argument added to ArgumentView (FIXME)")
            return
        self.arguments.append(argument)

    @property
    def eof(self) -> bool:
        return self.index >= len(self.source)

    def parse_arguments(self):
        """Parses arguments"""
        reconstructed = ""
        quote_started = False
        while not self.eof:
            char = self.source[self.index]
            if char in QUOTES:
                # if we're already quoted, we need to check if the last character was an escape (\\)
                # If it is escaped, add it to the string.
                # If it isn't, we can end the quote.
                if quote_started:
                    if self.index > 0 and self.source[self.index - 1] == "\\":
                        reconstructed += char
                    else:
                        quote_started = False
                        self.add_arg(reconstructed)
                        reconstructed = ""
                else:
                    if self.index == 0:  # cannot be an escaped string
                        quote_started = True
                    elif self.index > 0 and self.source[self.index - 1] != "\\":
                        quote_started = True
                    # If it is an escaped quote, we can add it to the string.
                    else:
                        reconstructed += char
            # If the character is a space, we can add the reconstructed string to the arguments list
            elif char.isspace():
                if quote_started:
                    reconstructed += char
                else:
                    self.add_arg(reconstructed)
                    reconstructed = ""
            # Any other character can be added to the current string
            elif char:  # elif ensures the character isn't null
                reconstructed += char
            self.index += 1
        # If we have a reconstructed string, we can add it to the arguments list
        if reconstructed:
            self.add_arg(reconstructed)
        return self
