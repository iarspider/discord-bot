import d20
import discord

from discord import ApplicationContext
from discord.ext import commands


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


class DiceCog(commands.Cog):
    @discord.slash_command(
        name="roll",
        guild_ids=[585487843510714389],
        description="Кидает кубики. Поддерживает расширенный синтаксис (/roll help)",
    )
    @check_channel("кубовая")
    async def slash_roll(self, ctx: ApplicationContext, arg):
        args = arg.split()

        if len(args) == 1 and args[0] == "help":
            await ctx.respond(
                "Расширенный синтаксис: "
                "<https://d20.readthedocs.io/en/latest/start.html#dice-syntax>",
                ephemeral=True,
            )
            return

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

        await ctx.respond("\n".join(rolls))


def setup(bot):  # this is called by Pycord to setup the cog
    bot.add_cog(DiceCog(bot))  # add the cog to the bot
