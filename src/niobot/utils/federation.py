import json
from urllib.parse import urlparse

import aiohttp

__all__ = ["resolve_homeserver"]


async def resolve_homeserver(domain: str) -> str:
    """
    Resolves a given homeserver part to the actual homeserver

    :param domain: The domain to crawl
    :return: The resolved homeserver
    """
    from niobot import __user_agent__

    if not domain.startswith("https://"):
        domain = f"https://{domain}"
    domain = urlparse(domain).netloc
    async with aiohttp.ClientSession(headers={"User-Agent": __user_agent__}) as session:
        async with session.get(f"https://{domain}/.well-known/matrix/client") as resp:
            if resp.status == 200:
                if resp.content_type != "application/json":
                    try:
                        data = await resp.text("utf-8")
                    except UnicodeDecodeError:
                        raise ValueError("Invalid homeserver response for well-known")
                    else:
                        try:
                            data = json.loads(data)
                        except json.JSONDecodeError:
                            raise ValueError("Invalid homeserver response for well-known")
                else:
                    data = await resp.json()
                if data["m.homeserver"]["base_url"]:
                    parsed = data["m.homeserver"]["base_url"]
                    if parsed.endswith("/"):
                        return parsed[:-1]
                    return parsed

    return f"https://{domain}"
