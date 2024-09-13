from ipaddress import IPv4Address, IPv4Network

from niobot import CommandArgumentsError, StatelessParser


class IPConverter(StatelessParser):
    """
    Converts an input into either an IP(v4) address or IP network.
    """
    def __call__(self, value: str) -> IPv4Address | IPv4Network:
        try:
            return IPv4Address(value)
        except ValueError:
            try:
                return IPv4Network(value)
            except ValueError as e:
                raise CommandArgumentsError("Invalid IP address or network.", exception=e)
