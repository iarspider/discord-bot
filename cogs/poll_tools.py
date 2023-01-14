import math
import collections
import datetime
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import *

import discord
import discord.utils
from dateutil import parser
from discord import ApplicationContext, Interaction
from discord.ext import commands, tasks
from loguru import logger

# A Python port of Ved_s' PollSystem. Thanks!

PollIdValidator = re.compile("^(\d+)_(\d+)$")


@dataclass
class Poll:
    title: str = ""
    description: str = ""
    answers: List[str] = field(default_factory=list)
    votes: Dict[int, int] = field(default_factory=dict)
    close_on: Optional[datetime] = None

    channelId: int = 0
    messageId: int = 0
    userId: int = 0

    def toJson(self):
        return json.dumps(self, default=lambda o: o.__dict__)


PollConfig = dict[str, Poll]
poll_config = PollConfig()


def check_channel(name):
    def predicate(ctx):
        if isinstance(name, str):
            names = (name,)
        else:
            names = name
        return ctx.guild is not None and (
            ctx.channel.name in names or ctx.channel.name == "ботова-отладка"
        )

    return commands.check(predicate)


def create_message(poll: Poll, ended: bool) -> Dict:
    def format_bar(votes: int) -> str:
        value = (votes / total) if total > 0 else 0
        s = "#" * int(value * barWidth) + "-" * int((1.0 - value) * barWidth)
        percent = int(math.floor(value * 100.0))
        if value == votes and value > 0:
            s = f"[{s}]"
        else:
            s = f" {s} "

        s = f"{s} {percent}%"

        return s

    barWidth: int = 20

    total = 0
    maxvotes = None

    c = collections.Counter()
    for i in range(len(poll.answers)):
        c[poll.answers[i]] = 0

    c.update(poll.votes.values())

    maxvotes = c.most_common(1)[0][1]
    total = c.total()

    if total != 0:
        votes = [v for v in c.values()]
    else:
        votes = [0 for _ in poll.answers]

    logger.debug(f"{votes=}")

    fields: List[discord.EmbedField] = [
        discord.EmbedField(name=poll.answers[i], value=format_bar(votes[i]))
        for i in range(len(poll.answers))
    ]

    options: List[discord.SelectOption] = [
        discord.SelectOption(label="Сброс голоса", value="reset")
    ]

    options.extend(
        [
            discord.SelectOption(label=poll.answers[i], value=str(i))
            for i in range(len(poll.answers))
        ]
    )

    return {
        "content": "Голосование завершено" if ended else "Голосование",
        "embed": discord.Embed(
            title=poll.title,
            description=poll.description,
            fields=fields,
            colour=0x00AA22 if ended else 0x0022AA,
        ),
        "view": None
        if ended
        else discord.ui.View(
            PollSelect(
                placeholder="Выбор ответа",
                options=options,
            ),
            timeout=None,
        ),
    }


class PollToolsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.message_command(name="Poll summary", guild_ids=[585487843510714389])
    @discord.default_permissions(
        administrator=True,
    )
    async def get_message_id(self, ctx: ApplicationContext, message: discord.Message):
        resp: Interaction = await ctx.send_response("Calculating...", ephemeral=True)

        guild = discord.utils.find(
            lambda g: g.id == 585487843510714389, self.bot.guilds
        )

        msg = "Результаты голосования:\n"

        for i, r in enumerate(message.reactions):
            print(type(r.emoji), r.emoji)
            if isinstance(r.emoji, str) and emoji.demojize(r.emoji) == ":locked:":
                continue

            summ = 0
            msg += f"* {r.emoji}: "
            async for m in r.users():
                # m = guild.get_member(u.id)
                if not isinstance(m, Member):
                    print(f"Warning: user {m.display_name} ({m.id}) is not in guild!")
                    weight = 1
                else:
                    if "Сабы" in [o.name for o in m.roles]:
                        weight = 2
                    else:
                        weight = 1

                summ += weight

            msg += f"{summ}\n"

        await resp.edit_original_response(content=msg)


def setup(bot):  # this is called by Pycord to setup the cog
    bot.add_cog(PollToolsCog(bot))  # add the cog to the bot
