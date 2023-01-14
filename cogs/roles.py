import emoji
import copy
import itertools
from typing import List, Dict

import discord
from discord.ext import commands
from loguru import logger

from config import roles


class RoleButton(discord.ui.Button):
    def __init__(self, role: discord.Role, emote: str):
        """A button for one role. `custom_id` is needed for persistent views."""
        super().__init__(
            # label=role.name,
            style=discord.ButtonStyle.primary,
            emoji=emoji.emojize(emote, language="alias"),
            custom_id=str(role.id),
        )

    async def callback(self, interaction: discord.Interaction):
        """
        This function will be called any time a user clicks on this button.
        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction object that was created when a user clicks on a button.
        """
        # Get the user who clicked the button.
        user = interaction.user
        # Get the role this button is for (stored in the custom ID).
        role = interaction.guild.get_role(int(self.custom_id))

        if role is None:
            # If the specified role does not exist, return nothing.
            # Error handling could be done here.
            return

        # Add the role and send a response to the user ephemerally (hidden to other
        # users).
        if role not in user.roles:
            # Give the user the role if they don't already have it.
            await user.add_roles(role)
            await interaction.response.send_message(
                f"🎉 Роль {role.mention} выдана!",
                ephemeral=True,
            )
        else:
            # Otherwise, take the role away from the user.
            await user.remove_roles(role)
            await interaction.response.send_message(
                f"❌ Роль {role.mention} убрана!",
                ephemeral=True,
            )


class RolesCog(commands.Cog):
    roles = {}

    def __init__(self, bot):
        self.bot = bot
        self.roles: List[Dict[str, str]] = roles
        self.guild = None

    def build_view(self) -> (discord.ui.View, str):
        msg_txt_1 = (
            f"""Приветствую тебя в Паучьем Логове!"""
            """Нажми на кнопку с соответствующим смайликом, если ..."""
        )

        msg_txt_2 = (
            "Чтобы не пропустить что-то интересное, можно также подписаться на: "
        )

        msg_txt_1l = [msg_txt_1]
        msg_txt_2l = [msg_txt_2]
        for role in self.roles:
            emote = emoji.emojize(role["emote"], language="alias")
            if role["type"] == "channel":
                msg_txt_1l.append(emote + " - " + role["description"])
            elif role["type"] == "mention":
                msg_txt_2l.append(emote + " - " + role["description"])

        msg_txt_1l.append("")
        msg_txt_2l.append("")

        msg_txt = "\n".join(itertools.chain(msg_txt_1l, msg_txt_2l))
        # timeout is None because we want this view to be persistent.
        view = discord.ui.View(timeout=None)

        # Loop through the list of roles and add a new button to the view for each role.
        for r in self.roles:
            # Get the role from the guild by ID.
            role = self.guild.get_role(int(r["id"]))
            view.add_item(RoleButton(role, r["emote"]))

        return view, msg_txt

    # Pass a list of guild IDs to restrict usage to the supplied guild IDs.
    @commands.slash_command(
        guild_ids=[585487843510714389], description="Показывает меню выбора ролей"
    )
    async def menu(self, ctx: discord.ApplicationContext):
        """Slash command to post a new view with a button for each role."""

        view, msg = self.build_view()
        await ctx.respond(msg, view=view)

    @commands.Cog.listener()
    async def on_ready(self):
        """
        This method is called every time the bot restarts.
        If a view was already created before (with the same custom IDs for buttons),
        it will be loaded and the bot will start watching for button clicks again.
        """
        # Add the view to the bot so that it will watch for button interactions.
        self.guild: discord.Guild = self.bot.data["discord_guild"]

        for i, role in enumerate(copy.deepcopy(roles)):
            role_id = discord.utils.find(
                lambda x: x.name == role["role"], self.guild.roles
            )
            if role_id is None:
                logger.warning(f"Role {role['role']} not found!")
                roles.pop(i)
                continue

            role["id"] = str(role_id.id)
            self.roles[i] = role

        view, _ = self.build_view()
        self.bot.add_view(view)


def setup(bot):  # this is called by Pycord to setup the cog
    bot.add_cog(RolesCog(bot))  # add the cog to the bot
