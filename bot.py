#!/usr/bin/env python3
import asyncio
import base64
import itertools
import logging
from io import BytesIO
from typing import Optional, Dict
import datetime
import copy

import colorlog
import d20
import discord
import emoji
import simplejson
# import aiosqlite
from aio_pika import connect, IncomingMessage
from discord import Member, PartialEmoji
from discord.ext import tasks, commands
from discord.ext.commands import Context
from discord.utils import get

from config import *

intents = discord.Intents(members=True, reactions=True)
discord_bot = commands.Bot(command_prefix='!', help_command=None)
discord_channel: Optional[discord.TextChannel] = None
discord_welcome_channel: Optional[discord.TextChannel] = None
discord_roles: Dict[str, discord.Role] = {}
discord_guild: Optional[discord.Guild] = None
rabbit = None
rabbit_channel = None
rabbit_queue = None
logger: Optional[logging.Logger] = None
menu_messages = {}

roles = {
    ':pick:': {'type': 'channel',
             'description': 'тебя интересуют игры в жанре "песочница" (Minecraft, Creativerse, Vintage Story, ...)',
             'role': "Песочницы"},
    ':meat_on_bone:': {'type': 'channel',
                     'description': 'тебя интересуют игры в жанре "выживание" (Raft, Stranded Deep, Valheim, ...)',
                     'role': "Выживач"},
    ':factory:': {'type': 'channel',
                'description': 'тебя интересуют игры в жанре "фабрика" (Factorio, Satisfactory, ...)',
                'role': "Фабрика"},
    ':keyboard:': {'type': 'channel', 'description': 'тебя интересует кодинг', 'role': "Кодинг"},
    ':mega:': {'type': 'mention', 'description': 'анонсы стримов на Twitch <https://twitch.tv/iarspider>',
             'role': "steram_announce"},
    ':satellite_antenna:': {'type': 'mention',
                          'description': 'оповещения о начале стримов на Twitch <https://twitch.tv/iarspider>',
                          'role': "stream_alert"},
    ':film_frames:': {'type': 'mention',
                    'description': 'оповещения о выходе серий по Minecraft или другим играм на Youtube-канале <https://youtube.com/iarspider>',
                    'role': "Кубы"}
}


def setup_logging(logfile, debug, color):
    global logger
    logger = logging.getLogger('arachnobot')
    logger.propagate = False

    bot_handler = logging.StreamHandler()
    if color:
        bot_handler.setFormatter(
            colorlog.ColoredFormatter(
                '%(asctime)s %(log_color)s[%(name)s:%(levelname)s:%(lineno)s]%(reset)s %(message)s',
                datefmt='%H:%M:%S'))
    else:
        bot_handler.setFormatter(
            logging.Formatter(fmt="%(asctime)s [%(name)s:%(levelname)s:%(lineno)s] %(message)s",
                              datefmt='%H:%M:%S'))

    file_handler = logging.FileHandler(logfile, "w")
    file_handler.setFormatter(
        logging.Formatter(fmt="%(asctime)s [%(name)s:%(levelname)s:%(lineno)s] %(message)s"))

    logger.addHandler(bot_handler)
    logger.addHandler(file_handler)

    if not debug:
        logger.setLevel(logging.INFO)
        logging.getLogger('discord').setLevel(logging.INFO)
    else:
        logger.info("Debug logging is ON")
        logger.setLevel(logging.DEBUG)
        logging.getLogger('discord').setLevel(logging.DEBUG)


def check_channel(name):
    def predicate(ctx):
        if isinstance(name, str):
            names = (name,)
        else:
            names = name
        return ctx.guild is not None and ctx.channel.name in names

    return commands.check(predicate)


@tasks.loop(minutes=5.0)
async def cleanup():
    global menu_messages
    now = datetime.datetime.now()
    for id in copy.copy(menu_messages.keys()):
        if menu_messages[id] < now:
            menu_messages.pop(id)


@discord_bot.event
async def on_ready():
    global discord_roles, discord_channel, discord_welcome_channel, discord_guild  # , con

    discord_guild = discord.utils.find(lambda g: g.name == discord_guild_name, discord_bot.guilds)

    if discord_guild is None:
        raise RuntimeError(f"Failed to join Discord guild {discord_guild_name}!")

    discord_channel = discord.utils.find(lambda c: c.name == discord_channel_name, discord_guild.channels)
    if discord_channel is None:
        raise RuntimeError(f"Failed to join Discord channel {discord_channel_name}!")

    discord_welcome_channel = discord.utils.find(lambda c: c.name == discord_welcome_channel_name,
                                                 discord_guild.channels)
    if discord_channel is None:
        raise RuntimeError(f"Failed to join Discord channel {discord_welcome_channel_name}!")

    for discord_role_name in discord_role_names:
        discord_role: Optional[discord.Role] = discord.utils.find(lambda r: r.name == discord_role_name,
                                                                  discord_guild.roles)
        if discord_role is None:
            raise RuntimeError(f"No role {discord_role_name} in guild {discord_guild_name}!")
        else:
            discord_roles[discord_role_name] = discord_role

    print(f"Ready | {discord_bot.user} @ {discord_guild.name} # {discord_channel.name} ")

    global rabbit, rabbit_channel, rabbit_queue
    rabbit = await connect(rabbit_url)
    rabbit_channel = await rabbit.channel()
    rabbit_queue = await rabbit_channel.declare_queue(name='discord')
    await rabbit_queue.consume(on_rabbit_message, no_ack=True)


@discord_bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    user: Member = payload.member
    if user == discord_bot.user:
        return

    msg_id = payload.message_id
    if msg_id not in menu_messages:
        return

    reaction: PartialEmoji = payload.emoji
    reaction_code = emoji.demojize(reaction.name, use_aliases=True)
    if reaction_code in roles:
        logger.debug(f"Will give role {roles[reaction_code]['role']} to {user.display_name}")
        await give_role(user, roles[reaction_code]['role'])
        logger.info(f"Gave role {roles[reaction_code]['role']} to {user.display_name}")
    else:
        logger.warning(f"Unknown reaction {reaction} ({reaction_code})")


@discord_bot.command()
@check_channel('ботова-болталка')
async def help(ctx):
    msg = """Справка по командам бота:
    `!help`: выводит эту справку
    `!menu`: выводит меню для выбора ролей. Доступно только в канале <#817443293507747891>.
    `!roll <XdY> ...`: бросает виртуальные кубики и показывает результат. Доступно только в канале <#709426323025821756>. Поддерживает расширенный синтаксис."""

    await ctx.send(msg)


async def give_role(member: Member, role_name):
    role = get(discord_guild.roles, name=role_name)
    await member.add_roles(role)


async def remove_role(member: Member, role_name):
    role = get(member.server.roles, name=role_name)
    await member.remove_roles(role)


async def post_menu(ch: discord.TextChannel, author: Member):
    global menu_messages
    msg_txt_1 = f"""Приветствую тебя, {author.display_name}, в Паучьем Логове! 
    Поставь реакцию, если ..."""

    msg_txt_2 = "Чтобы не пропустить что-то интересное, можно также подписаться на ..."

    msg_txt_3 = "Это сообщение самоуничтожится через 60 секунд, если я не сломаюсь."

    msg_txt_1l = [msg_txt_1]
    msg_txt_2l = [msg_txt_2]
    for role_emoji, role in roles.items():
        if role['type'] == 'channel':
            msg_txt_1l.append(f'{role_emoji} - ' + role['description'])
        elif role['type'] == 'mention':
            msg_txt_2l.append(f'{role_emoji} - ' + role['description'])

    msg_txt_1l.append("")
    msg_txt_2l.append("")

    msg_txt = "\n".join(itertools.chain(msg_txt_1l, msg_txt_2l, (msg_txt_3,)))

    msg = await ch.send(msg_txt, delete_after=60)
    now = datetime.datetime.now()
    then = now + datetime.timedelta(seconds=60)
    menu_messages[msg.id] = then

    await asyncio.gather(*(msg.add_reaction(emoji.emojize(x, use_aliases=True)) for x in roles.keys()))


@discord_bot.event
async def on_member_join(author: Member):
    asyncio.ensure_future(post_menu(discord_welcome_channel, author))


@discord_bot.command()
@check_channel(('ботова-болталка', 'ботова-отладка'))
async def menu(ctx: Context):
    asyncio.ensure_future(ctx.message.delete())
    asyncio.ensure_future(post_menu(ctx.channel, ctx.author))


@discord_bot.command()
@check_channel('кубовая')
async def roll(ctx: Context, *args):
    rolls = []
    for arg in args:
        try:
            res = d20.roll(arg)
        except d20.errors.RollError:
            pass
        else:
            rolls.append(str(res))

    if not rolls:
        return

    await ctx.send("\n".join(rolls))


def send(body):
    logger.info("Received send command")
    discord_channel = globals().get('discord_channel')

    if 'attachment' in body:
        attachment_data = base64.b64decode(body['attachment'])
        att_io = discord.File(BytesIO(attachment_data), filename=body['filename'])
    else:
        att_io = None

    message = body['message']
    for role_name, role in discord_roles.items():
        message = message.replace(f'@{role_name}', role.mention)

    channel_name = body.get('channel', discord_channel_name)
    if channel_name != discord_channel_name:
        discord_channel = discord.utils.find(lambda c: c.name == channel_name, discord_guild.channels)
        if discord_channel is None:
            raise RuntimeError(f"Failed to join Discord channel {discord_channel_name}!")

    logger.debug("Ready to send...")
    asyncio.ensure_future(discord_channel.send(content=message, file=att_io))
    logger.debug("... done")


async def on_rabbit_message(message: IncomingMessage):
    logger.debug("RabbitMQ message received!")
    body_ = message.body
    body = simplejson.loads(body_)
    logger.debug("Action is:", body['action'])
    if body['action'] == 'send':
        send(body)


if __name__ == "__main__":
    setup_logging("discord.log", True, True)
    discord_bot.run(discord_bot_token)
