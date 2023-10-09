# Context
For each command invoked, the first argument is always a [`Context`](#command-context) instance, which holds a lot of
metadata, and a few utility functions to help you write commands.

A lot of the time, these are the three main attributes you'll be using:

* [`Context.room`](#niobot.context.Context.room) (`nio.MatrixRoom`) - the room the command was invoked in.
* [`Context.event`](#niobot.context.Context.event) (`nio.RoomMessageText`) - the message that invoked this command.
* [`Context.respond`](#niobot.context.Context.respond) - a utility class to help you respond to the command.

## Command Context
::: niobot.context.Context

## Contextual Response
::: niobot.context.ContextualResponse
