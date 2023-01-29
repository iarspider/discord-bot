import asyncio
import base64
import json
from io import BytesIO

import discord
from loguru import logger
from discord.ext import commands
from aio_pika import connect
from aio_pika.abc import AbstractIncomingMessage

from config import *


class RabbitCog(commands.Cog, name="Rabbit"):
    def __init__(self, bot):
        self.bot = bot
        self.rabbit = None
        asyncio.ensure_future(self.setup())

    async def setup(self):
        self.rabbit = await connect(self.bot.data["rabbit_url"])
        rabbit_channel = await self.rabbit.channel()
        rabbit_queue = await rabbit_channel.declare_queue(name="discord")
        await rabbit_queue.consume(self.on_rabbit_message)

    async def on_rabbit_message(self, message: AbstractIncomingMessage) -> None:
        logger.debug("RabbitMQ message received!")
        async with message.process():
            body_ = message.body
            body = json.loads(body_)
            logger.debug("Action is: %s", body["action"])
            if body["action"] == "send":
                self.send(body)

    def send(self, body):
        logger.info("Received send command")
        discord_channel = globals().get("discord_channel")

        if "attachment" in body:
            attachment_data = base64.b64decode(body["attachment"])
            att_io = discord.File(BytesIO(attachment_data), filename=body["filename"])
        else:
            att_io = None

        message = body["message"]
        for role_name, role in self.bot.data["discord_roles"].items():
            message = message.replace(f"@{role_name}", role.mention)

        channel_name = body.get("channel", discord_channel_name)
        if channel_name != discord_channel_name:
            discord_channel = discord.utils.find(
                lambda c: c.name == channel_name,
                self.bot.data["discord_guild"].channels,
            )
            if discord_channel is None:
                raise RuntimeError(
                    f"Failed to join Discord channel {discord_channel_name}!"
                )

        logger.debug("Ready to send...")
        asyncio.ensure_future(discord_channel.send(content=message, file=att_io))
        logger.debug("... done")

    def cog_unload(self):
        loop = asyncio.get_running_loop()
        loop.run_until_complete(self.rabbit.close())


def setup(bot):  # this is called by Pycord to setup the cog
    bot.add_cog(RabbitCog(bot))  # add the cog to the bot
