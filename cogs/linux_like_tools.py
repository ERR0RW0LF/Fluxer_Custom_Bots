import fluxer
from fluxer import Cog
from fluxer.checks import has_permission
import logging
import base64

logger = logging.getLogger(__name__)

class LinuxLikeTools(Cog):
    def __init__(self, bot: fluxer.Bot):
        super().__init__(bot)
    
    @Cog.command()
    async def base64(self, ctx: fluxer.models.message.Message):
        """
        Description: Encodes or decodes a string using Base64 and the a similar syntax to Linux.
        
        Usage: /base64 -d <string>  # decode | /base64 <string>  # encode
        """
        # Check if -d is set as flag
        content = ctx.content
        content = content.removeprefix("/base64 ")
        split_message = content.split()
        logger.log(logging.INFO,f"{ctx.content}")
        if content.startswith("-d "):
            content = content.removeprefix("-d ")
            original_string = content
            decoded_bytes = base64.b64decode(original_string)
            decoded_string = decoded_bytes.decode('utf-8')
            
            await ctx.reply(decoded_string)
            return
        else:
            original_string = content
            bytes_data = original_string.encode('utf-8')
            base64_bytes = base64.b64encode(bytes_data)
            base64_string = base64_bytes.decode('utf-8')
            
            await ctx.reply(base64_string)
            return

async def setup(bot: fluxer.Bot):
    await bot.add_cog(LinuxLikeTools(bot))