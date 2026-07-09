import fluxer
from fluxer import Cog
from fluxer.checks import has_permission
import logging

logger = logging.getLogger(__name__)

class Ping(Cog):
    def __init__(self, bot: fluxer.Bot):
        super().__init__(bot)
    
    @Cog.command()
    async def ping(self, ctx: fluxer.models.message.Message):
        """
        Description: Responds with 'Pong!' and adds a ping pong emoji reaction.

        Usage: /ping
        """
        await ctx.reply("Pong!")
        await ctx.add_reaction("🏓")

async def setup(bot: fluxer.Bot):
    await bot.add_cog(Ping(bot))