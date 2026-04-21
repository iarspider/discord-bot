#!/usr/bin/env python3
import logging
import sys
from typing import Optional, Dict

import discord
from discord import ApplicationCommand
from loguru import logger

from src.config import settings

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

    async def on_ready(self):
        logger.debug("Guilds:\n" + "\n".join(f"* {x.name}#{x.id}" for x in self.guilds))

        self.discord_guild = discord.utils.find(
            lambda g: g.name == settings.discord_guild_name, self.guilds
        )

        if self.discord_guild is None:
            raise RuntimeError(
                f"Failed to join Discord guild {settings.discord_guild_name}!"
            )

        self.discord_channel = self.find_channel(settings.discord_channel_name)
        self.discord_welcome_channel = self.find_channel(
            settings.discord_welcome_channel_name
        )
        self.discord_news_channel = self.find_channel(
            settings.discord_news_channel_name
        )
        self.discord_debug_channel = self.find_channel(
            settings.discord_debug_channel_name
        )

        for discord_role_name in settings.discord_role_names:
            discord_role: Optional[discord.Role] = discord.utils.find(
                lambda r: r.name == discord_role_name, self.discord_guild.roles
            )
            if discord_role is None:
                raise RuntimeError(
                    f"No role {discord_role_name} in guild {settings.discord_guild_name}!"
                )
            else:
                self.discord_roles[discord_role_name] = discord_role

        logger.info(
            f"Ready | {self.user} @ {self.discord_guild.name} ({self.discord_guild.id}) #"
            f" {self.discord_channel.name} "
        )

    async def on_message(self, message):
        # TODO: Temporary disabled

        # if message.author.bot or message.channel.id not in (
        #         self.discord_channel.id,
        #         self.discord_debug_channel.id,
        # ):
        #     return

        #    try:
        #        sent_message = telegram_bot.send_message(chat_id=telegram_chat_id, text=message.content)
        #        message_map[message.id] = sent_message.message_id
        #        save_message_map()  # Save to file after each new message
        #    except TelegramError as e:
        #        print(f"Error sending message to Telegram: {e}")
        # logger.info(message.content)
        pass

    def find_channel(self, name):
        res = discord.utils.find(lambda c: c.name == name, self.discord_guild.channels)

        if res is None:
            raise RuntimeError(f"Failed to join Discord channel {name}!")

        return res


intents = discord.Intents.default()
# noinspection PyDunderSlots,PyUnresolvedReferences
intents.members = True
# noinspection PyDunderSlots,PyUnresolvedReferences
intents.message_content = True


discord_bot: MyBot | None = None


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


def setup_logging(debug):
    loglevel = logging.DEBUG if debug else logging.INFO
    logger.remove()
    logger.add(sys.stderr, level=loglevel, backtrace=True, diagnose=True)

    logging.basicConfig(handlers=[InterceptHandler()], level=0)
    logging.getLogger("discord").setLevel(loglevel)

    if debug:
        logger.info("Debug logging is ON")


@logger.catch
async def main():
    global discord_bot

    discord_bot = MyBot(help_command=None, intents=intents)
    discord_bot.data = {}

    setup_logging(settings.debug)
    all_cogs = (
        "dice",
        "roles",
        "rabbit",
        "tg",
    )
    for cog in all_cogs:
        discord_bot.load_extension(f"src.cogs.{cog}")
    await discord_bot.start(settings.discord_token.get_secret_value())
