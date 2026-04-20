import asyncio
import base64
import datetime
import os
from io import BytesIO
from typing import Literal, Protocol

import discord
from aio_pika import connect_robust
from aio_pika.abc import AbstractIncomingMessage
from discord.ext import commands
from loguru import logger
from pydantic import BaseModel, Field, field_validator, PrivateAttr, model_validator, ValidationError

from src.config import settings

MESSAGE_LIFETIME = 600
MAX_BYTES = 8 * 1024 * 1024


class MyBotProtocol(Protocol):
    discord_channel: discord.TextChannel | None = None
    discord_welcome_channel: discord.TextChannel | None = None
    discord_debug_channel: discord.TextChannel | None = None
    discord_news_channel: discord.TextChannel | None = None
    discord_roles: dict[str, discord.Role] = {}
    discord_guild: discord.Guild | None = None

    async def wait_until_ready(self):
        ...


class Attachment(BaseModel):
    filename: str
    data_b64: str
    _decoded_bytes: bytes = PrivateAttr()

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("filename cannot be empty")

        # prevent path tricks
        if os.path.basename(v) != v:
            raise ValueError("filename must not contain path components")

        return v

    @model_validator(mode="after")
    def decode_and_cache(self) -> Attachment:
        try:
            data = base64.b64decode(self.data_b64, validate=True)
            if len(data) > MAX_BYTES:
                raise ValueError("Attachment too large")

            self._decoded_bytes = data
        except Exception as e:
            raise ValueError("data_b64 must be valid base64") from e
        return self

    @property
    def att_io(self):
        return discord.File(BytesIO(self._decoded_bytes), filename=self.filename)


class SendDiscordMessage(BaseModel):
    expires_at: datetime.datetime
    action: Literal["send"]
    attachment: Attachment | None = Field(None)
    body: str
    channel: str | None = Field(None)


class RabbitCog(commands.Cog, name="Rabbit"):
    def __init__(self, bot):
        self.bot: MyBotProtocol = bot
        self.rabbit = None
        asyncio.ensure_future(self.setup())

    async def setup(self):
        self.rabbit = await connect_robust(settings.rabbitmq_dsn)
        rabbit_channel = await self.rabbit.channel()
        await rabbit_channel.set_qos(prefetch_count=10)
        rabbit_queue = await rabbit_channel.declare_queue(
            name="discord", durable=True, arguments={"x-message-ttl": 60000}
        )
        await rabbit_queue.consume(self.on_rabbit_message)

    async def on_rabbit_message(self, message: AbstractIncomingMessage) -> None:
        logger.debug("RabbitMQ message received!")
        now = datetime.datetime.now().astimezone()

        async with message.process():
            try:
                decoded_message = SendDiscordMessage.model_validate_json(message.body)
            except ValidationError:
                logger.exception("Message decoding failed")
                return

            remaining = (decoded_message.expires_at - now).total_seconds()
            if remaining <= 0:
                logger.error("Discarding expired message!")
                return

            loop = asyncio.get_running_loop()
            deadline = loop.time() + remaining

            try:
                async with asyncio.timeout_at(deadline):
                    await self.bot.wait_until_ready()
                    await self.send(decoded_message)
            except TimeoutError:
                logger.error("Giving up on message - deadline expired!")
                return

    async def send(self, message: SendDiscordMessage):
        logger.info("Received send command")

        body = message.body
        for role_name, role in self.bot.discord_roles.items():
            body = body.replace(f"@{role_name}", role.mention)

        channel_name = message.channel or settings.discord_channel_name
        if channel_name != settings.discord_channel_name:
            discord_channel = discord.utils.find(
                lambda c: c.name == channel_name,
                self.bot.discord_guild.channels,
            )
            if discord_channel is None:
                logger.error(
                    f"RabbitCog: Discord channel {channel_name} not found!"
                )
        else:
            discord_channel = self.bot.discord_channel
        logger.debug("Ready to send...")
        asyncio.ensure_future(discord_channel.send(content=message.body, file=message.attachment.att_io))
        logger.debug("... done")

    def cog_unload(self):
        loop = asyncio.get_running_loop()
        loop.run_until_complete(self.rabbit.close())


def setup(bot):  # this is called by Pycord to set up the cog
    bot.add_cog(RabbitCog(bot))  # add the cog to the bot
