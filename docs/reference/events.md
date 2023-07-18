# Event Reference

## A little note about event names

Event names are never prefixed with `on_`, so make sure you're listening to events like `message`, not `on_message`!

While trying to listen for an `on_` prefixed event will still work, it will throw warnings in the console, and may
be deprecated in the future.

---

## NioBot-specific events

There are two types of events in niobot: those that are dispatched by niobot itself, and those that're dispatched by
`matrix-nio`.
In order to keep backwards compatability, as well as high flexibility and extensibility, niobot's
[NioBot][niobot.NioBot] class actually subclasses [nio.AsyncClient][]. This means that anything you can do with
`matrix-nio`, you can do with niobot.

However, for simplicity, niobot dispatches its own events independently of `matrix-nio`. These events are listed below.

You can listen to these events with [niobot.NioBot.on_event][].

??? example
    ```python
    import niobot

    bot = niobot.NioBot(...)


    @bot.on_event("ready")
    async def on_ready(result):
        print("Bot is ready!")
        print("Logged in as:", bot.user_id)


    bot.run(...)
    ```

::: niobot._event_stubs

---

## `matrix-nio` events
See the [`matrix-nio`](https://matrix-nio.readthedocs.io/en/latest/nio.html#module-nio.events) documentation for the
base-library set of events.

Remember, you'll need to use [nio.Client.add_event_callback][] in order to listen to these!
