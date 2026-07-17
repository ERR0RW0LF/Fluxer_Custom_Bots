import asyncio
from calendar import c
import os

import logging
import fluxer
import dotenv
from pprint import pprint

def get_log_level() -> int:
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    return getattr(logging, log_level, logging.INFO)


# Load environment variables from .env file
dotenv.load_dotenv()


BOT_HOSTER_FLUXER_ID = os.getenv("YOUR_FLUXER_USER_ID")

# Set up logging
logging.basicConfig(level=get_log_level())
logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = fluxer.Bot(command_prefix="/", intents=fluxer.Intents.default() | fluxer.Intents.GUILD_PRESENCES)



# fluxer doesn't parse or cache PRESENCE_UPDATE events, so we track statuses ourselves.
presence_cache: dict[int, str] = {}




@bot.command()
@fluxer.has_permission(fluxer.Permissions.ADMINISTRATOR)
async def _bot(ctx: fluxer.models.message.Message):
    if int(ctx.author.id) != int(BOT_HOSTER_FLUXER_ID):
        await ctx.reply("Ask the person hosting the bot!")
        logger.debug(ctx.author.id)
        return
    content = ctx.content
    split_message = content.split()
    if split_message[1] == "reload":
        # Unload and reload the cogs
        await unload_extensions()
        await load_extensions()
        await ctx.reply("Finished reloading cogs.")



@bot.command()
async def test_edit_embed(ctx: fluxer.models.message.Message):
    embed = fluxer.Embed(
        title="Test Embed",
        description="This is a test embed message.",
        url="https://example.com"
    )
    embed_message =await ctx.send(embed=embed)
    await asyncio.sleep(5)
    embed = fluxer.Embed(
        title="Test Embed Edited2",
        description="This is an edited test embed message.",
        url="https://example.com"
    )
    await embed_message.edit(embeds=[embed.to_dict()])



@bot.command()
async def help(ctx: fluxer.models.message.Message):
    # check if the user has administrator permissions
    if not await has_permission(fluxer.Permissions.ADMINISTRATOR, ctx):
        # give only the normal user commands
        await ctx.send("Available commands:\n/ping - Test the bot's responsiveness.\n/help - Show this help message.")
    else:
        # give all commands
        await ctx.send("Available commands:\n/ping - Test the bot's responsiveness.\n/help - Show this help message.\n/clear - Clear all messages in the current channel (admin only).\n/update_hak5_product_list <url> - Update the Hak5 product list from the specified XML URL (admin only).\n/get_data <thing> - Get data about a guild, channel, or user (admin only).")

async def has_permission(permission: fluxer.Permissions, ctx: fluxer.models.message.Message) -> bool:
    # Reworked version of fluxer's has_permission but as a plain check that returns
    # a bool instead of a decorator that gates a whole command, so command bodies
    # (like /help) can branch on it directly.
    if ctx.guild_id is None:
        return False

    if ctx._http is None:
        raise RuntimeError("HTTPClient is required to check permissions")

    guild_data, member_data, roles_data = await asyncio.gather(
        ctx._http.get_guild(ctx.guild_id),
        ctx._http.get_guild_member(ctx.guild_id, ctx.author.id),
        ctx._http.get_guild_roles(ctx.guild_id),
    )

    # If the user is the guild owner, they bypass all permission checks
    if ctx.author.id == int(guild_data["owner_id"]):
        return True

    member_role_ids = {int(r) for r in member_data.get("roles", [])}
    computed = 0
    for role in roles_data:
        role_id = int(role["id"])
        if role_id == ctx.guild_id or role_id in member_role_ids:
            computed |= int(role["permissions"])

    # If a user has admin, they bypass all permission checks
    if computed & int(fluxer.Permissions.ADMINISTRATOR):
        return True

    return (computed & int(permission)) == int(permission)







async def load_extensions():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")

async def unload_extensions():
    extensions = list(bot.extensions)
    for extension in extensions:
        await bot.unload_extension(extension)

@bot.event
async def on_ready():
    if bot.user is not None:
        logger.info(f"Bot is ready! Logged in as {bot.user.username} (ID: {bot.user.id})")
    else:
        logger.error("Logged in, but bot.user is None. Exiting.")

if __name__ == "__main__":
    asyncio.run(load_extensions())
    bot.run(os.getenv("FLUXER_TOKEN"))