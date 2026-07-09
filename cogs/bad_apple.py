import fluxer
from fluxer import Cog
from fluxer.checks import has_permission
import logging

logger = logging.getLogger(__name__)

class BadApple(Cog):
    def __init__(self, bot: fluxer.Bot):
        super().__init__(bot)
    
    @Cog.command()
    @fluxer.has_permission(fluxer.Permissions.ADMINISTRATOR)
    async def bad_apple(self, ctx: fluxer.models.message.Message):
        """
        Description: Plays the Bad Apple ASCII animation in the channel.

        Usage: /bad_apple
        """
        # spam the channel with a bad apple ascii animation
        # frames are saved in ./frames-ascii/ as text files, with name from out0001.txt to out6572.txt
        # the frames should be dynamically loaded so that the bot doesn't have to load all frames into memory at once
        # and so that the number of frames can be changed without changing the code
        import time
        import glob

        # only one message should be sent and then be edited with each frame, to avoid spamming the channel with thousands of messages
        current_channel = ctx.channel
        frame_files = sorted(glob.glob("./frames-ascii/out*.txt"))
        if not frame_files:
            await ctx.send("No frames found in ./frames-ascii/")
            return

        # send the first frame as a message
        with open(frame_files[0], "r", encoding="utf-8") as f:
            frame = f.read()
            frame = "```\n" + frame + "\n```"
            # # add a symbol to beginning of each line
            # frame = "\n".join("- " + line for line in frame.splitlines())
            frame_message = await ctx.send(frame)

        delta_time = 0.1
        start_time = time.time()
        # Target time for each frame is start_time + i * delta_time, not a rolling
        # "time since last edit" - that reset every loop and got blown past by the
        # Discord API call itself, causing every frame to be skipped.
        for i, frame_file in enumerate(frame_files[1:], start=1):
            target_time = start_time + i * delta_time
            now = time.time()
            if now < target_time:
                time.sleep(target_time - now)
            elif now - target_time > delta_time:
                print(f"Skipping frame {i} to catch up to current time")
                continue
            with open(frame_file, "r", encoding="utf-8") as f:
                frame = f.read()
                frame = "```\n" + frame + "\n```"
                # # add a symbol to beginning of each line
                # frame = "\n".join("- " + line for line in frame.splitlines())
                await frame_message.edit(content=frame)

        embed = fluxer.Embed(
            title="Bad Apple Animation Complete",
            description="The Bad Apple ASCII animation has finished playing."
        )
        await frame_message.edit(content="Animation complete!", embeds=[embed.to_dict()])

async def setup(bot: fluxer.Bot):
    await bot.add_cog(BadApple(bot))