import asyncio
import fluxer
from fluxer import Cog
from fluxer.checks import has_permission
import logging

logger = logging.getLogger(__name__)

# Discord embed limits (kept conservative to leave headroom)
EMBED_MAX_FIELD_CHARS = 1024
EMBED_MAX_FIELDS_PER_PAGE = 20
EMBED_MAX_TOTAL_CHARS = 5000

FIRST_EMOJI = "⏮️"
PREV_EMOJI = "◀️"
NEXT_EMOJI = "▶️"
LAST_EMOJI = "⏭️"
NAV_EMOJIS = (FIRST_EMOJI, PREV_EMOJI, NEXT_EMOJI, LAST_EMOJI)
PAGE_TIMEOUT = 120  # seconds of inactivity before navigation stops listening


class Help(Cog):
    def __init__(self, bot: fluxer.Bot):
        super().__init__(bot)




    # Dynamically generate help command based on all commands in the bot
    # using the """Description: ... Usage: ...""" docstring format for each command
    # loading this from the files
    @Cog.command()
    async def help(self, ctx: fluxer.models.message.Message):
        """
        Description: Displays this help message.

        Usage: /help
        """
        pages = await self.build_help_pages()
        await self.send_paginated(ctx, pages)

    # Turn a cog module name like "admin_tools" into a display title like "Admin Tools"
    def format_cog_name(self, cog_name: str) -> str:
        return cog_name.replace("_", " ").title()

    # Build one or more embeds containing all commands, splitting across
    # pages as needed to stay under Discord's embed size limits.
    async def build_help_pages(self):
        all_commands = await self.get_all_commands()

        commands_by_cog = {}
        for cog_name, command_name, description, usage in all_commands:
            commands_by_cog.setdefault(cog_name, []).append((command_name, description, usage))

        # Build (field_name, field_value) pairs, splitting any cog whose
        # command list would exceed a single embed field's character limit.
        fields = []
        for cog_name in sorted(commands_by_cog):
            lines = []
            for command_name, description, usage in sorted(commands_by_cog[cog_name], key=lambda c: c[0]):
                line = f"**`{usage if usage else f'/{command_name}'}`**"
                if description:
                    line += f"\n{description}"
                lines.append(line)

            title = self.format_cog_name(cog_name)
            chunk, chunk_len, part = [], 0, 1
            for line in lines:
                if chunk and chunk_len + len(line) + 2 > EMBED_MAX_FIELD_CHARS:
                    fields.append((title if part == 1 else f"{title} (cont.)", "\n\n".join(chunk)))
                    part += 1
                    chunk, chunk_len = [], 0
                chunk.append(line)
                chunk_len += len(line) + 2
            if chunk:
                fields.append((title if part == 1 else f"{title} (cont.)", "\n\n".join(chunk)))

        # Pack fields into pages, respecting Discord's per-embed limits.
        pages_fields = []
        current, current_len = [], 0
        for name, value in fields:
            entry_len = len(name) + len(value)
            if current and (
                len(current) >= EMBED_MAX_FIELDS_PER_PAGE
                or current_len + entry_len > EMBED_MAX_TOTAL_CHARS
            ):
                pages_fields.append(current)
                current, current_len = [], 0
            current.append((name, value))
            current_len += entry_len
        pages_fields.append(current)

        total = len(pages_fields)
        pages = []
        for i, page_fields in enumerate(pages_fields, start=1):
            embed = fluxer.Embed(
                title=f"Help{f' (page {i}/{total})' if total > 1 else ''}",
                description="Here are the available commands:"
            )
            for name, value in page_fields:
                embed.add_field(name=name, value=value, inline=False)
            if total > 1:
                embed.set_footer(text=f"{FIRST_EMOJI} {PREV_EMOJI} {NEXT_EMOJI} {LAST_EMOJI}  to navigate pages")
            pages.append(embed)

        return pages

    # Send the first page and, if there's more than one, let the invoker
    # flip between pages using the reactions below the embed.
    async def send_paginated(self, ctx: fluxer.models.message.Message, pages: list):
        index = 0
        message = await ctx.send(embed=pages[index])

        if len(pages) <= 1:
            return

        for emoji in NAV_EMOJIS:
            await message.add_reaction(emoji)

        while True:
            future: asyncio.Future = asyncio.get_event_loop().create_future()

            async def on_raw_reaction_add(raw):
                if raw.message_id != message.id or raw.user_id != ctx.author.id:
                    return
                if raw.emoji.unicode in NAV_EMOJIS and not future.done():
                    future.set_result(raw.emoji.unicode)

            self.bot._event_handlers.setdefault("on_raw_reaction_add", []).append(on_raw_reaction_add)
            try:
                try:
                    choice = await asyncio.wait_for(future, timeout=PAGE_TIMEOUT)
                except asyncio.TimeoutError:
                    break
            finally:
                self.bot._event_handlers["on_raw_reaction_add"].remove(on_raw_reaction_add)

            if choice == FIRST_EMOJI:
                index = 0
            elif choice == LAST_EMOJI:
                index = len(pages) - 1
            elif choice == NEXT_EMOJI:
                index = (index + 1) % len(pages)
            else:  # PREV_EMOJI
                index = (index - 1) % len(pages)

            message = await message.edit(embeds=[pages[index].to_dict()])

            try:
                await message.remove_reaction(choice, ctx.author.id)
            except Exception:
                pass

        try:
            await message.clear_reactions()
        except Exception:
            pass

    # ========= Helper functions =========
    
    

    # Get all cogs files from the cogs folder
    async def get_all_cogs(self):
        import os
        import importlib
        cogs = []
        for filename in os.listdir("cogs"):
            if filename.endswith(".py") and not filename.startswith("__"):
                cog_name = filename[:-3]
                cogs.append(cog_name)
        return cogs
    
    # Find the Cog subclass defined in a cog module
    def get_cog_class(self, cog_module):
        for attr_name in dir(cog_module):
            attr = getattr(cog_module, attr_name)
            if isinstance(attr, type) and issubclass(attr, Cog) and attr is not Cog:
                return attr
        return None

    # Read the docstring of a command and return the description and usage
    async def get_command_docstring(self, cog_name, command_name):
        import importlib
        cog_module = importlib.import_module(f"cogs.{cog_name}")
        cog_class = self.get_cog_class(cog_module)
        command_method = getattr(cog_class, command_name)
        docstring = command_method.__doc__
        if docstring is None:
            return None, None
        lines = docstring.strip().splitlines()
        description = None
        usage = None
        for line in lines:
            line = line.strip()
            if line.startswith("Description:"):
                description = line[len("Description:"):].strip()
            elif line.startswith("Usage:"):
                usage = line[len("Usage:"):].strip()
        return description, usage
    
    # Get all commands in a cog and return a list of tuples (command_name, description, usage)
    async def get_all_commands_in_cog(self, cog_name):
        import importlib
        cog_module = importlib.import_module(f"cogs.{cog_name}")
        cog_class = self.get_cog_class(cog_module)
        commands = []
        for attr_name in dir(cog_class):
            attr = getattr(cog_class, attr_name)
            if callable(attr) and getattr(attr, "__cog_command__", False):
                command_name = attr_name
                description, usage = await self.get_command_docstring(cog_name, command_name)
                commands.append((command_name, description, usage))
        return commands
    
    # Get all commands in the bot and return a list of tuples (cog_name, command_name, description, usage)
    async def get_all_commands(self):
        cogs = await self.get_all_cogs()
        all_commands = []
        for cog_name in cogs:
            commands = await self.get_all_commands_in_cog(cog_name)
            for command_name, description, usage in commands:
                all_commands.append((cog_name, command_name, description, usage))
        return all_commands
    
    # Create a help embed for a specific command
    async def create_help_embed_for_command(self, cog_name, command_name):
        description, usage = await self.get_command_docstring(cog_name, command_name)
        embed = fluxer.Embed(
            title=f"Help for {command_name}",
            description=description or "No description available.",
            fields=[
                {"name": "Usage", "value": usage or "No usage available.", "inline": False}
            ]
        )
        return embed
    
    
    
    


async def setup(bot: fluxer.Bot):
    await bot.add_cog(Help(bot))

async def teardown(bot):
    await bot.remove_cog("Help")