import fluxer
from fluxer import Cog
from fluxer.checks import has_permission
import logging
import asyncio

logger = logging.getLogger(__name__)


class AdminTools(Cog):
    def __init__(self, bot: fluxer.Bot):
        super().__init__(bot)

    async def get_channel_by_name(guild: fluxer.models.guild.Guild, name: str) -> fluxer.models.channel.Channel | None:
        """fluxer has no cache/lookup for guild channels by name, so hit the API directly."""
        data = await self.bot._http.get_guild_channels(guild.id)
        for channel_data in data:
            if channel_data.get("name") == name:
                return fluxer.models.channel.Channel.from_data(channel_data, self.bot._http)
        return None

    @Cog.command()
    @fluxer.has_permission(fluxer.Permissions.ADMINISTRATOR)
    async def clear(self, ctx: fluxer.models.message.Message):
        """
        Description: Clears messages in the current channel.

        Usage: /clear <thing>
        """
        split_message = ctx.content.split()
        if len(split_message) != 2 or "help" in split_message:
            await ctx.send("This command clears all messages in the current channel. Usage: /clear <thing> <help>\nAvailable things: channel")
            return

        match split_message[1]:
            case "channel":
                await self.clear_channel(ctx)
            case _:
                await ctx.send(f"Unknown thing '{split_message[1]}'. Available things: channel")



    @Cog.command()
    @fluxer.has_permission(fluxer.Permissions.ADMINISTRATOR)
    async def clear_channel(self, ctx: fluxer.models.message.Message):
        """
        Description: Does the same as /clear

        Usage: /clear_channel
        """
        split_message = ctx.content.split()
        if (len(split_message) >= 2 or "help" in split_message) and not split_message[1] == "channel":
            await ctx.send("This command clears all messages in the current channel. Usage: /clear_channel <help>")
            return


        # check if the user has administrator permissions
        print(f"Clearing channel: {ctx.channel.name}")
        current_channel = ctx.channel
        # get all messages in the channel
        messages = await current_channel.fetch_messages(limit=100)
        print(f"Found {len(messages)} messages in the channel.")

        # Generate a embed message to confirm the action
        embed = fluxer.Embed(
            title="Clear Channel",
            description=f"Are you sure you want to clear all messages in {ctx.channel.name}?"
        )

        # Give it two reaction options: ✅ for yes, ❌ for no
        confirmation_message = await ctx.send(embed=embed)
        await confirmation_message.add_reaction("✅")
        await confirmation_message.add_reaction("❌")

        # Messages don't cache their reactions (see fluxer's _handle_reaction_add),
        # so we listen for the raw gateway event instead of polling the message.
        future: asyncio.Future = asyncio.get_event_loop().create_future()

        async def on_raw_reaction_add(raw):
            if raw.message_id != confirmation_message.id or raw.user_id != ctx.author.id:
                return
            if raw.emoji.unicode in ("✅", "❌") and not future.done():
                future.set_result(raw.emoji.unicode)

        self.bot._event_handlers.setdefault("on_raw_reaction_add", []).append(on_raw_reaction_add)
        try:
            try:
                choice = await asyncio.wait_for(future, timeout=30)
            except asyncio.TimeoutError:
                await confirmation_message.delete()
                await ctx.send("Channel clear timed out.")
                return
        finally:
            self.bot._event_handlers["on_raw_reaction_add"].remove(on_raw_reaction_add)

        await confirmation_message.delete()

        if choice == "❌":
            await ctx.send("Channel clear cancelled.")
            return

        while True:
            # delete all messages in the channel
            for message in messages:
                try:
                    await message.delete()
                except Exception as e:
                    print(f"Failed to delete message: {e}")

            # fetch the next batch of messages
            messages = await current_channel.fetch_messages(limit=100)
            if not messages:
                break

        await ctx.send("Channel cleared!")

    async def clear_channel_helper(self, channel: fluxer.models.channel.Channel):
        # delete all messages in the channel
        while True:
            messages = await channel.fetch_messages(limit=100)
            print(f"[debug] clear_channel_helper: fetched {len(messages)} messages from channel {channel.id}")
            if not messages:
                break
            for message in messages:
                try:
                    await message.delete()
                    print(f"[debug] clear_channel_helper: deleted message {message.id}")
                except Exception as e:
                    print(f"[debug] clear_channel_helper: FAILED to delete message {message.id}: {e}")

        return
    
    @Cog.command()
    @fluxer.has_permission(fluxer.Permissions.ADMINISTRATOR)
    async def get_data(self, ctx: fluxer.models.message.Message):
        """
        Description: Looks up information about a guild, channel, or user.

        Usage: /get_data <guild|channel|user|users> <id>
        """
        # get the data of the specified thing
        split_message = ctx.content.split()
        if len(split_message) < 2:
            await ctx.send("Please specify what data you want to get. Usage: /get_data <thing> \nAvailable things: guild, channel, user")
            return

        match split_message[1]:
            case "guild":
                if len(split_message) > 3 and split_message[3] != "users":
                    await ctx.send("Please specify a guild ID. Usage: /get_data guild <guild_id>")
                    return
                elif len(split_message) == 3 and split_message[2].isdigit():
                    guild_id = split_message[2]
                    if not guild_id.isdigit():
                        await ctx.send(f"'{guild_id}' is not a valid guild ID.")
                        return
                    try:
                        guild = await self.bot.fetch_guild(guild_id)
                    except fluxer.errors.BadRequest:
                        await ctx.send(f"Could not find a guild with ID '{guild_id}'.")
                        return
                else:
                    guild = ctx.guild

                if guild is not None:
                    await ctx.send(f"Guild name: {guild.name}, Guild ID: {guild.id}, Member count: {guild.member_count}")
                else:
                    await ctx.send("This command can only be used in a guild.")

            case "channel":
                if len(split_message) > 3:
                    await ctx.send("Please specify a channel ID. Usage: /get_data channel <channel_id>")
                    return
                elif len(split_message) == 3:
                    channel_id = split_message[2]
                    channel = await self.bot.fetch_channel(channel_id)
                else:
                    channel = ctx.channel
                    if channel is not None:
                        await ctx.send(f"Channel name: {channel.name}, Channel ID: {channel.id}, Channel type: {channel.type}")
                    else:
                        await ctx.send("This command can only be used in a guild.")

            case "user":
                if len(split_message) < 3:
                    await ctx.send("Please specify a user ID. Usage: /get_data user <user_id>")
                    return
                user_id = split_message[2]
                user = await self.bot.fetch_user(user_id)
                if user:
                    await ctx.send(f"User name: {user.username}, User ID: {user.id}")
                    # check if the user is in the guild
                    guild = ctx.guild
                    if guild is not None:
                        member = await guild.fetch_member(user.id)
                        if member:
                            await ctx.send(f"User is a member of the guild. Member name: {member.user.display_name}, Member ID: {member.user.id}")
                        else:
                            await ctx.send("User is not a member of the guild.")
                    # check online status of the user
                    #status = presence_cache.get(user.id, "unknown")
                    #await ctx.send(f"User status: {status}")
                else:
                    await ctx.send("User not found.")

            case "users":
                # get all users in the guild
                guild = ctx.guild
                if guild is not None:
                    members = [member for member in await guild.fetch_members()]
                    await ctx.send(f"Found {len(members)} members in the guild.")
                    for member in members:
                        await ctx.send(f"Member name: {member.user.username}, Member ID: {member.user.id}")
                else:
                    await ctx.send("This command can only be used in a guild.")
    
    @Cog.command()
    @fluxer.has_permission(fluxer.Permissions.ADMINISTRATOR)
    async def gen_channel_history(self, ctx: fluxer.models.message.Message):
        """
        Description: Generates fake channel history for testing. 
        
        Usage: /gen_channel_history <message_count (optional, default=10-50)> <help>
        """
        
        # generate fake channel history for testing
        # spamming random numbers of random messages in the channel
        # check if the user has administrator permissions

        split_message = ctx.content.split()
        if len(split_message) >= 2:
            if "help" in split_message:
                await ctx.send("This command generates fake channel history for testing. It will spam random numbers of random messages in the channel. Usage: /gen_channel_history <message_count (optional, default=10-50)> <help>")
                return


        import random
        messages = [
            "Hello!",
            "How are you?",
            "This is a test message.",
            "Random message.",
            "Another message.",
            "Testing, testing.",
            "This is a fake message.",
            "Just another message.",
            "Message number 9.",
            "Message number 10.",
            "42"
        ]

        if len(split_message) >= 2 and split_message[1] == "members":
            guild = ctx.guild
            if guild is not None:
                members = [member for member in await guild.fetch_members()]
                if members:
                    random_member = random.choice(members)
                    message = f"Hey {random_member.mention}, you got pinged!"
                    await ctx.send(message)
                    return



        current_channel = ctx.channel
        if len(split_message) >= 2 and split_message[1].isdigit():
            num_messages = int(split_message[1])
        else:
            num_messages = random.randint(10, 50)
        for _ in range(num_messages):
            if random.random() < 0.01: # 1% chance to ping some one
                # Joke chance of pinging a random user of the server
                guild = ctx.guild
                if guild is not None:
                    members = [member for member in await guild.fetch_members()]
                    if members:
                        random_member = random.choice(members)
                        message = f"Hey {random_member.mention}, you got pinged!"
            elif random.random() < 0.05: # 5% chance to send a message with a link
                message = "Check this out: https://www.example.com"
            elif random.random() < 0.05: # 5% chance to send a message with an image
                message = "Look at this image: https://www.example.com/image.png"
            elif random.random() < 0.05: # 5% chance to send a message with an attachment with random data
                await current_channel.send("Here's an attachment with random data.", file=fluxer.File(fp=os.urandom(1024), filename="random.bin"))
                continue
            else:
                message = random.choice(messages)
            await current_channel.send(message)




async def setup(bot: fluxer.Bot):
    await bot.add_cog(AdminTools(bot))
