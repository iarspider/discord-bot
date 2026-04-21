import json
import re
from datetime import datetime
from typing import Optional

import emoji
import pytz
import telegram
from babel.dates import format_datetime
from discord import TextChannel, Message
from discord.ext import commands
from loguru import logger
from telegram import Bot

__all__ = ["TgCog", "setup"]

from telegram.error import TelegramError

from src.config import settings

SECONDS_IN_MINUTE = 60
SECONDS_IN_HOUR = 60 * SECONDS_IN_MINUTE
SECONDS_IN_DAY = 24 * SECONDS_IN_HOUR
SECONDS_IN_WEEK = 7 * SECONDS_IN_DAY


class TgCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_map = {}
        self.load_message_map()

    def load_message_map(self):
        try:
            with open("message_map.json", "r") as f:
                self.message_map = json.load(f)
        except FileNotFoundError:
            pass
        except json.JSONDecodeError:
            logger.exception("Failed to load message_map.json")

    def save_message_map(self):
        with open("message_map.json", "w") as f:
            json.dump(self.message_map, f)

    @staticmethod
    def format_timestamp(ts: int, dt: datetime, style: str) -> str:
        formats = {
            "t": "dd.MM.yyyy H:mm",
            "T": "H:mm:ss",
            "d": "dd.MM.yyyy",
            "D": "dd MMMM yyyy",
            "f": "dd MMMM yyyy H:mm",
            "R": "dd MMMM yyyy H:mm",  # use "long" format for relative, since TG doesn't support relative
            "F": "EEEE, dd MMMM yyyy H:mm",
        }

        formats_tg = {
            "t": "dt",
            "T": "T",
            "d": "d",
            "D": "D",
            "f": "Dt",
            "R": "r",  # use "long" format for relative, since TG doesn't support relative
            "F": "wDt",
        }

        dt_str = format_datetime(dt, formats.get(style, formats["F"]), locale="ru")
        return f'<tg-time unix="{ts}" format="{formats_tg.get(style, formats_tg["F"])}">{dt_str}</tg-time>'

    def process_message(self, content: str):
        content = content.replace("@everyone", "")
        user_mentions = re.findall(r"<@!?(\d+)>", content)
        for user_id in user_mentions:
            user = self.bot.discord_guild.get_member(int(user_id))
            if user:
                content = content.replace(f"<@{user_id}>", f"{user.display_name}")
                content = content.replace(f"<@!{user_id}>", f"{user.display_name}")

        channel_mentions = re.findall(r"<#(\d+)>", content)
        for channel_id in channel_mentions:
            channel = self.bot.discord_guild.get_channel(int(channel_id))
            if isinstance(channel, TextChannel):
                content = content.replace(f"<#{channel_id}>", f"#{channel.name}")

        role_mentions = re.findall(r"<@&(\d+)>", content)
        for role_id in role_mentions:
            content = content.replace(f"<@&{role_id}>", "")

        content = emoji.emojize(content)

        custom_emoji_pattern = r"<a?:(\w+):\d+>"
        content = re.sub(custom_emoji_pattern, r"\1", content)

        timestamp_mentions = re.findall(r"<t:(\d+):?([a-zA-Z])?>", content)
        msk_tz = pytz.timezone("Europe/Moscow")
        for timestamp, style in timestamp_mentions:
            dt = datetime.fromtimestamp(int(timestamp), tz=msk_tz)
            formatted_time = self.format_timestamp(
                int(timestamp), dt, style if style else "F"
            )

            content = re.sub(
                f'<t:{timestamp}:{style if style else ""}>',
                f"<pre>{formatted_time}</pre>",
                content,
            )

        return content

    @staticmethod
    def md_discord_to_tg(text: str) -> str:
        bold_re = re.compile(r"(?<!\*)\*\*(.+?)\*\*(?!\*)")
        italic_re = re.compile(r"(?<!\*)\*(.+?)\*(?!\*)")
        italic_re_alt = re.compile(r"(?<!_)_(.+?)_(?!_)")
        # bold_italic_re = re.compile(r"\*\*\*(.+?)\*\*\*")
        strikethrough_re = re.compile(r"(?<!~)~(.+?)~(?!~)")
        spoiler_re = re.compile(r"\|\|(.+?)\|\|")

        text = bold_re.sub(r"<b>\1<b>", text)
        text = italic_re.sub(r"<i>\1<i>", text)
        text = italic_re_alt.sub(r"<i>\1<i>", text)
        # text = bold_italic_re.sub(r"<bi>\1</bi>", text)
        text = strikethrough_re.sub(r"<s>\1<s>", text)
        text = spoiler_re.sub("<tg-spoiler>\1</tg-spoiler>", text)

        return text

    async def send_or_edit_message(
        self, message: Message, message_id: Optional[int] = None
    ):
        if message.author.bot or message.channel.id not in (
            self.bot.discord_news_channel.id,
            self.bot.discord_debug_channel.id,
        ):
            return

        if message_id and message_id not in self.message_map:
            return

        telegram_token = settings.telegram_token
        telegram_channel = settings.telegram_channel

        tg_bot = Bot(telegram_token)

        clean_text = self.md_discord_to_tg(message.content)
        clean_text = self.process_message(clean_text)

        logger.info(
            f"send_or_edit_message: message_id is {message_id}, clean_text is {clean_text}"
        )

        try:
            if not message_id:
                sent_message = await tg_bot.send_message(
                    telegram_channel,
                    clean_text,
                    parse_mode=telegram.constants.ParseMode.HTML,
                )
                self.message_map[message.id] = sent_message.message_id
                self.save_message_map()
            else:
                await tg_bot.edit_message_text(
                    clean_text,
                    telegram_channel,
                    message_id,
                    parse_mode=telegram.constants.ParseMode.HTML,
                )
        except TelegramError as e:
            logger.exception(f"Error sending message to Telegram: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        await self.send_or_edit_message(message, None)

    # noinspection PyUnusedLocal
    @commands.Cog.listener()
    async def on_message_edit(self, before: Message, after: Message):
        await self.send_or_edit_message(after, after.id)


def setup(bot):  # this is called by Pycord to set up the cog
    bot.add_cog(TgCog(bot))  # add the cog to the bot
