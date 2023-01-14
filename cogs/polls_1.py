import math
import collections
import datetime
import json
import re
from dataclasses import dataclass, field
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
class PollConfig:
    polls: List["Poll"] = field(default_factory=list)

    def toJson(self):
        return json.dumps(self, default=lambda o: o.__dict__)


poll_config = PollConfig()


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
        value = math.floor(votes / total)
        s = "#" * int(value * barWidth) + "-" * int((1.0 - value) * barWidth)
        percent = int(math.floor(votes / total * 100.0))
        if value == votes:
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

    maxvotes = c.most_common(1)[1]
    total = c.total()

    if total != 0:
        votes = [int(math.floor(v / total * barWidth)) for v in c.values()]
    else:
        votes = [0 for _ in poll.answers]

    fields: List[discord.EmbedField] = [
        discord.EmbedField(name=poll.answers[i], value=format_bar(poll.votes[i]))
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
        "embeds": discord.Embed(
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
            )
        ),
    }


class PollSelect(discord.ui.Select):
    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

    def callback(self, interaction: Interaction):
        for poll in poll_config.polls:
            if not (
                poll.channelId == interaction.channel.id
                and poll.messageId == interaction.message.id
            ):
                continue

            if self.values[0] == "reset":
                poll.votes.pop(interaction.user.id, None)
            else:
                poll.votes[interaction.user.id] = int(self.values[0])
                msg = await interaction.original_response()
                await msg.edit(**create_message(poll, False))
        else:
            interaction.response.send_message("Голосование не найдено", ephemeral=True)
            msg = await interaction.original_response()
            # TODO
            # embeds = msg.embeds
            # for embed in embeds:
            #     embed.colour = 0xFF0000
            #
            # msg.edit(embeds=embeds)


class PollModal(discord.ui.Modal):
    def __init__(self, channel: discord.TextChannel | None, *args, **kwargs) -> None:
        self.channel = channel
        super().__init__(
            discord.ui.InputText(
                label="Заголовок",
                required=True,
                style=discord.InputTextStyle.short,
            ),
            discord.ui.InputText(
                label="Описание",
                required=False,
                style=discord.InputTextStyle.short,
            ),
            discord.ui.InputText(
                label="Варианты ответов",
                placeholder=f"1.\n2.\n3.",
                required=True,
                style=discord.InputTextStyle.long,
            ),
            discord.ui.InputText(
                label="Дата закрытия",
                placeholder="dd-mm-yyyy",
                required=False,
                style=discord.InputTextStyle.short,
            ),
            *args,
            **kwargs,
        )

    async def callback(self, interaction: discord.Interaction):
        global poll_config

        channel_ = interaction.channel
        if self.channel:
            channel_ = self.channel

        close_on = self.children[3].value
        if close_on is not None:
            try:
                close_on = parser.parse(close_on)
            except:
                await interaction.response.send_message(
                    f"Некорректная дата {close_on}, "
                    "вам придётся закрыть голосование вручную",
                    ephemeral=True,
                )
                close_on = None

        p = Poll(
            title=self.children[0].value,
            description=self.children[1].value,
            answers=self.children[2].value.splitlines(),
            close_on=close_on,
        )

        await interaction.response.send_message(
            f"Голосование создано. Используйте /endpoll для завершения",
            ephemeral=True,
        )

        msg = await channel_.send(**create_message(p, False))
        p.messageId = msg.id
        poll_config.polls.append(p)


async def poll_autocomplete(ctx: discord.AutocompleteContext):
    perms = ctx.interaction.user.guild_permissions
    mod = perms.manage_messages
    res = []

    for poll in poll_config.polls:
        if poll.userId == ctx.interaction.user.id or mod:
            res.append(
                discord.OptionChoice(
                    name=poll.title, value=f"{poll.channelId}_{poll.messageId}"
                )
            )

    return res


@tasks.loop(minutes=5.0)
async def cleanup():
    # TODO: clean up polls
    pass


class PollsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(description="Открыть форму создания голосования")
    @check_channel("ботова-отладка")
    async def poll(self, ctx: ApplicationContext, channel: discord.TextChannel):
        modal = PollModal(channel=channel)
        id = "pollmodal_{}".format(channel.id if channel else "")
        await ctx.send_modal(modal, custom_id=id)

    @discord.slash_command(description="Завершает голосование")
    @check_channel("ботова-отладка")
    async def endpoll(
        self,
        ctx: ApplicationContext,
        id: discord.Option(
            discord.SlashCommandOptionType.string,
            description="Идентификатор голосования, автодополнение",
            autocomplete=poll_autocomplete,
        ),
        delete: discord.Option(
            discord.SlashCommandOptionType.boolean,
            description="Удалить сообщение с голосованием",
        ),
        resend: discord.Option(
            discord.SlashCommandOptionType.boolean,
            description="Отправить сообщение с завершённым голосованием",
        ),
    ):
        res = PollIdValidator.match(id)
        if not res:
            await ctx.interaction.response.send_message(
                "Неверный ID голования", ephemeral=True
            )
            return

        channel = int(res[1])
        message = int(res[2])

        for poll in poll_config.polls:
            if poll.channelId == channel and poll.messageId == message:
                break
        else:
            poll = None

        if not poll:
            await ctx.interaction.response.send_message(
                "Голосование не найдено", ephemeral=True
            )
            return

        poll_config.polls.remove(poll)

        discord_guild = self.bot.data["discord_guild"]
        discord_channel: discord.TextChannel = discord.utils.find(
            lambda c: c.id == channel, discord_guild.channels
        )

        discord_message: discord.Message = await discord_channel.fetch_message(message)

        if delete:
            await ctx.interaction.response.send_message(
                "Голосование удалено", ephemeral=True
            )
            await discord_message.delete()
        else:
            ctx.interaction.response.send_message(
                "Голосование завершено", ephemeral=True
            )

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        for i, poll in enumerate(poll_config.polls):
            if poll.messageId == message.id and poll.channelId == message.channel.id:
                logger.info(f"Removed poll {poll.title}")
                break
        else:
            return

        poll_config.polls.pop(i)

    @commands.Cog.listener()
    async def on_ready(self):
        discord_guild = self.bot.data["discord_guild"]
        with open("polls.json", "r") as f:
            data: Dict = json.load(f)

        for v in data["polls"]:
            channel: discord.TextChannel = discord.utils.find(
                lambda c: c.id == v["channelId"], discord_guild.channels
            )
            if not channel:
                continue

            try:
                message = channel.fetch_message(v["messageId"])
            except:
                continue

            poll_config.polls.append(Poll(**v))

    def cog_unload(self):
        with open("polls.json", "w") as f:
            json.dump(poll_config.toJson(), f)


def setup(bot):  # this is called by Pycord to setup the cog
    bot.add_cog(PollsCog(bot))  # add the cog to the bot
