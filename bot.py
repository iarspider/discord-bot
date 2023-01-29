#!/usr/bin/env python3
import logging
import os
import sys
from typing import Optional, Dict

import discord
import dotenv
from discord import ApplicationCommand
from loguru import logger

from config import *

intents = discord.Intents(members=True, reactions=True, messages=True)
discord_channel: Optional[discord.TextChannel] = None
discord_welcome_channel: Optional[discord.TextChannel] = None
discord_roles: Dict[str, discord.Role] = {}
discord_guild: Optional[discord.Guild] = None
rabbit_url = ""
rabbit = None
rabbit_channel = None
rabbit_queue = None

menu_messages = {}


class MyBot(discord.Bot):
    async def register_command(
        self,
        command: ApplicationCommand,
        force: bool = True,
        guild_ids: list[int] | None = None,
    ) -> None:
        raise NotImplementedError()

    data = {}
    setup_ = False


discord_bot = MyBot(help_command=None)


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(logfile, debug, color):
    loglevel = logging.DEBUG if debug else logging.INFO
    logger.remove()
    logger.add(sys.stderr, level=loglevel, backtrace=True, diagnose=True)
    logger.add(
        logfile,
        level=loglevel,
        rotation="12:00",
        compression="zip",
        retention="1 week",
        backtrace=True,
        diagnose=True,
    )

    logging.basicConfig(handlers=[InterceptHandler()], level=0)
    logging.getLogger("discord").setLevel(loglevel)

    if debug:
        logger.info("Debug logging is ON")


@discord_bot.event
async def on_ready():
    global discord_roles, discord_channel, discord_welcome_channel, discord_guild

    discord_guild = discord.utils.find(
        lambda g: g.name == discord_guild_name, discord_bot.guilds
    )

    if discord_guild is None:
        raise RuntimeError(f"Failed to join Discord guild {discord_guild_name}!")

    discord_bot.data["discord_guild"] = discord_guild

    discord_channel = discord.utils.find(
        lambda c: c.name == discord_channel_name, discord_guild.channels
    )
    if discord_channel is None:
        raise RuntimeError(f"Failed to join Discord channel {discord_channel_name}!")

    discord_welcome_channel = discord.utils.find(
        lambda c: c.name == discord_welcome_channel_name, discord_guild.channels
    )
    if discord_channel is None:
        raise RuntimeError(
            f"Failed to join Discord channel {discord_welcome_channel_name}!"
        )

    for discord_role_name in discord_role_names:
        discord_role: Optional[discord.Role] = discord.utils.find(
            lambda r: r.name == discord_role_name, discord_guild.roles
        )
        if discord_role is None:
            raise RuntimeError(
                f"No role {discord_role_name} in guild {discord_guild_name}!"
            )
        else:
            discord_roles[discord_role_name] = discord_role

    logger.info(
        f"Ready | {discord_bot.user} @ {discord_guild.name} ({discord_guild.id}) #"
        f" {discord_channel.name} "
    )

    discord_bot.data["discord_roles"] = discord_roles

    if not discord_bot.setup_:
        cog = discord_bot.get_cog("Rabbit")
        # noinspection PyUnresolvedReferences
        await cog.setup()
        discord_bot.setup_ = True


@logger.catch
def main():
    global rabbit_url, discord_bot

    discord_bot.data = {}

    dotenv.load_dotenv()
    token = str(os.getenv("TOKEN"))
    discord_bot.data["rabbit_url"] = str(os.getenv("RABBIT"))

    setup_logging("discord.log", True, True)
    # all_cogs = ("dice", "polls", "rabbit", "roles")
    # all_cogs = ("dice", "polls", "rabbit", "roles")
    # all_cogs = ("dice", "polls", "rabbit", "roles")
    all_cogs = (
        "dice",
        "roles",
        "rabbit",
        "poll_tools",
    )
    for cog in all_cogs:
        discord_bot.load_extension(f"cogs.{cog}")
    discord_bot.run(token)


if __name__ == "__main__":
    main()
