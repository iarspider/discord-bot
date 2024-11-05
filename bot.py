#!/usr/bin/env python3
import logging
import os
import sys
from typing import Optional, Dict

import discord
import dotenv
from discord import ApplicationCommand
from loguru import logger

from config import (
    discord_channel_name,
    discord_debug_channel_name,
    discord_guild_name,
    discord_news_channel_name,
    discord_role_names,
    discord_welcome_channel_name,
)

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
    setup_done = False
    discord_channel: Optional[discord.TextChannel] = None
    discord_welcome_channel: Optional[discord.TextChannel] = None
    discord_debug_channel: Optional[discord.TextChannel] = None
    discord_news_channel: Optional[discord.TextChannel] = None
    discord_roles: Dict[str, discord.Role] = {}
    discord_guild: Optional[discord.Guild] = None
    rabbit_url = ""
    rabbit = None
    rabbit_channel = None
    rabbit_queue = None


intents = discord.Intents.default()
# noinspection PyDunderSlots
intents.members = True
# noinspection PyDunderSlots
intents.message_content = True


discord_bot = MyBot(help_command=None, intents=intents)


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
        rotation="1 day",
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
async def on_message(message):
    if message.author.bot or message.channel.id not in (
        discord_bot.discord_channel.id,
        discord_bot.discord_debug_channel.id,
    ):
        return

    #    try:
    #        sent_message = telegram_bot.send_message(chat_id=telegram_chat_id, text=message.content)
    #        message_map[message.id] = sent_message.message_id
    #        save_message_map()  # Save to file after each new message
    #    except TelegramError as e:
    #        print(f"Error sending message to Telegram: {e}")
    logger.info(message.content)
    pass


def find_channel(name):
    res = discord.utils.find(
        lambda c: c.name == name, discord_bot.discord_guild.channels
    )

    if res is None:
        raise RuntimeError(f"Failed to join Discord channel {name}!")

    return res


@discord_bot.event
async def on_ready():
    # global discord_roles, discord_channel, discord_welcome_channel, discord_news_channel, discord_debug_channel, discord_guild

    logger.debug(
        "Guilds:\n" + "\n".join(f"* {x.name}#{x.id}" for x in discord_bot.guilds)
    )

    discord_bot.discord_guild = discord.utils.find(
        lambda g: g.name == discord_guild_name, discord_bot.guilds
    )

    if discord_bot.discord_guild is None:
        raise RuntimeError(f"Failed to join Discord guild {discord_guild_name}!")

    discord_bot.discord_channel = find_channel(discord_channel_name)
    discord_bot.discord_welcome_channel = find_channel(discord_welcome_channel_name)
    discord_bot.discord_news_channel = find_channel(discord_news_channel_name)
    discord_bot.discord_debug_channel = find_channel(discord_debug_channel_name)

    for discord_role_name in discord_role_names:
        discord_role: Optional[discord.Role] = discord.utils.find(
            lambda r: r.name == discord_role_name, discord_bot.discord_guild.roles
        )
        if discord_role is None:
            raise RuntimeError(
                f"No role {discord_role_name} in guild {discord_guild_name}!"
            )
        else:
            discord_bot.discord_roles[discord_role_name] = discord_role

    logger.info(
        f"Ready | {discord_bot.user} @ {discord_bot.discord_guild.name} ({discord_bot.discord_guild.id}) #"
        f" {discord_bot.discord_channel.name} "
    )

    if not discord_bot.setup_done:
        cog = discord_bot.get_cog("Rabbit")
        # noinspection PyUnresolvedReferences
        if cog:
            await cog.setup()
        discord_bot.setup_done = True


@logger.catch
def main():
    global discord_bot

    discord_bot.data = {}

    dotenv.load_dotenv()
    token = str(os.getenv("TOKEN"))
    discord_bot.rabbit_url = str(os.getenv("RABBIT"))

    setup_logging("discord.log", False, True)
    all_cogs = (
        "dice",
        "roles",
        # "rabbit",
        "tg",
    )
    for cog in all_cogs:
        discord_bot.load_extension(f"cogs.{cog}")
    discord_bot.run(token)


if __name__ == "__main__":
    main()
