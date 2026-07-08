import asyncio
from calendar import c
import os

import fluxer
import dotenv
from pprint import pprint

bot = fluxer.Bot(command_prefix="/", intents=fluxer.Intents.default() | fluxer.Intents.GUILD_PRESENCES)

# fluxer doesn't parse or cache PRESENCE_UPDATE events, so we track statuses ourselves.
presence_cache: dict[int, str] = {}

@bot.event
async def on_ready():
    print(f"Bot is ready! Logged in as {bot.user.username}")

@bot.event
async def on_presence_update(data):
    user_id = int(data["user"]["id"])
    presence_cache[user_id] = data.get("status", "offline")

@bot.event
async def on_raw_reaction_add(raw):
    print(f"[debug] on_raw_reaction_add: {raw}")
    if raw.user_id == bot.user.id:
        return
    
    # load hak5_products.json to find the product with the embed message id 
    import json
    try:
        with open("hak5_products.json", "r") as f:
            products = json.load(f)
    except FileNotFoundError:
        products = []
    
    for product in products:
        if product.get("embed_message_id") == raw.message_id:
            # this is a reaction to a product embed message
            print(f"[debug] Reaction to product {product.get('loc')}: {raw.emoji.unicode}")
            product.setdefault("interested_users", [])
            if raw.emoji.unicode == "⭐":
                if raw.user_id not in product["interested_users"]:
                    product["interested_users"].append(raw.user_id)
                    products = [p if p.get("loc") != product.get("loc") else product for p in products]
                    with open("hak5_products.json", "w") as f:
                        json.dump(products, f, indent=4)
                    print(f"[debug] Added user {raw.user_id} to interested_users for product {product.get('loc')}")
                    # dm user that they have been added to the interested_users list for this product
                    user = await bot.fetch_user(raw.user_id)
                    dm = await user.create_dm()
                    await dm.send(f"You have been added to the interested_users list for product {product.get('loc')}. You will be notified when this product is updated.")
                    break

@bot.event
async def on_raw_reaction_remove(raw):
    print(f"[debug] on_raw_reaction_remove: {raw}")
    
    if raw.user_id == bot.user.id:
        return
    
    # load hak5_products.json to find the product with the embed message id 
    import json
    try:
        with open("hak5_products.json", "r") as f:
            products = json.load(f)
    except FileNotFoundError:
        products = []
    
    for product in products:
        if product.get("embed_message_id") == raw.message_id:
            # this is the removal of a reaction to a product embed message
            print(f"[debug] Reaction removed from product {product.get('loc')}: {raw.emoji.unicode}")
            if raw.emoji.unicode == "⭐":
                if raw.user_id in product.get("interested_users", []):
                    product["interested_users"].remove(raw.user_id)
                    products = [p if p.get("loc") != product.get("loc") else product for p in products]
                    with open("hak5_products.json", "w") as f:
                        json.dump(products, f, indent=4)
                    print(f"[debug] Removed user {raw.user_id} from interested_users for product {product.get('loc')}")
                    # dm user that they have been removed from the interested_users list for this product
                    user = await bot.fetch_user(raw.user_id)
                    dm = await user.create_dm()
                    await dm.send(f"You have been removed from the interested_users list for product {product.get('loc')}. You will no longer be notified when this product is updated.")
                    break


# fluxer's GUILD_CREATE handling drops the initial "presences" array, so without
# this the cache stays empty until someone's status changes after we connect.
_original_dispatch = bot._dispatch

async def _dispatch_with_presences(event_name, data):
    if event_name == "GUILD_CREATE":
        presences = data.get("presences", [])
        #print(f"[debug] GUILD_CREATE for {data.get('name')}: {len(presences)} presences, keys={list(data.keys())}")
        for presence in presences:
            uid = presence.get("user", {}).get("id")
            if uid is not None:
                presence_cache[int(uid)] = presence.get("status", "offline")
    elif event_name == "PRESENCE_UPDATE":
        print(f"[debug] PRESENCE_UPDATE: {data}")
    await _original_dispatch(event_name, data)

bot._dispatch = _dispatch_with_presences

async def get_channel_by_name(guild: fluxer.models.guild.Guild, name: str) -> fluxer.models.channel.Channel | None:
    """fluxer has no cache/lookup for guild channels by name, so hit the API directly."""
    data = await bot._http.get_guild_channels(guild.id)
    for channel_data in data:
        if channel_data.get("name") == name:
            return fluxer.models.channel.Channel.from_data(channel_data, bot._http)
    return None

@bot.command()
async def ping(ctx: fluxer.models.message.Message):
    await ctx.reply("Pong!")
    await ctx.add_reaction("🏓")

@bot.command()
@fluxer.has_permission(fluxer.Permissions.ADMINISTRATOR)
async def clear(ctx: fluxer.models.message.Message):
    split_message = ctx.content.split()
    if len(split_message) != 2 or "help" in split_message:
        await ctx.send("This command clears all messages in the current channel. Usage: /clear <thing> <help>\nAvailable things: channel")
        return
    
    match split_message[1]:
        case "channel":
            await clear_channel(ctx)
        case _:
            await ctx.send(f"Unknown thing '{split_message[1]}'. Available things: channel")



@bot.command()
@fluxer.has_permission(fluxer.Permissions.ADMINISTRATOR)
async def clear_channel(ctx: fluxer.models.message.Message):
    
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

    bot._event_handlers.setdefault("on_raw_reaction_add", []).append(on_raw_reaction_add)
    try:
        try:
            choice = await asyncio.wait_for(future, timeout=30)
        except asyncio.TimeoutError:
            await confirmation_message.delete()
            await ctx.send("Channel clear timed out.")
            return
    finally:
        bot._event_handlers["on_raw_reaction_add"].remove(on_raw_reaction_add)

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

async def clear_channel_helper(channel: fluxer.models.channel.Channel):
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


@bot.command()
@fluxer.has_permission(fluxer.Permissions.ADMINISTRATOR)
async def update_hak5_product_list(ctx: fluxer.models.message.Message):
    split_message = ctx.content.split()
    print(split_message)
    if (len(split_message) != 2 and "force" not in split_message and "update" not in split_message) or "help" in split_message or (len(split_message) != 3 and "force" in split_message and "update" in split_message):
        await ctx.send("This command updates the Hak5 product list. Usage: /update_hak5_product_list <url to xml file>")
        return
    
    url = split_message[1]

    if ctx.guild is None:
        await ctx.send("This command can only be used in a guild.")
        return

    channel_name = os.getenv("PRODUCTS_CHANNEL_NAME")
    if not channel_name:
        await ctx.send("PRODUCTS_CHANNEL_NAME is not set in .env.")
        return

    products_channel = await get_channel_by_name(ctx.guild, channel_name)
    if products_channel is None:
        await ctx.send(f"Could not find a channel named '{channel_name}' in this guild.")
        return

    if len(split_message) == 3 and split_message[2] == "force":
        # clear the channel of all messages before updating the product list
        # create cleaning message in product channel
        await ctx.reply("Clearing channel...")
        await clear_channel_helper(products_channel)
        # clear_channel_helper already deletes every message in the channel,
        # including the "Clearing channel..." message itself.

        # delete the hak5_products.json file if it exists
        if os.path.exists("hak5_products.json"):
            os.remove("hak5_products.json")
            await ctx.send("Deleted hak5_products.json file.")



    # download the xml file from the url
    import requests
    response = requests.get(url)
    if response.status_code != 200:
        await ctx.send(f"Failed to download the XML file from {url}. Status code: {response.status_code}")
        return
    # Example data from Hak5 sitemap.xml file:
    """
    <urlset>
    <span id="uas-port"/>
    <url>
    <loc>https://hak5.org/</loc>
    <changefreq>daily</changefreq>
    </url>
    <url>
    <loc>https://hak5.org/products/wifi-pineapple</loc>
    <lastmod>2026-07-07T16:31:24-07:00</lastmod>
    <changefreq>daily</changefreq>
    <image:image>
    <image:loc>
    https://cdn.shopify.com/s/files/1/0068/2142/products/wp-mk7_81d03a53-bf1a-426f-9425-a34c8b3d9c85.jpg?v=1599680489
    </image:loc>
    <image:title>WiFi Pineapple</image:title>
    <image:caption/>
    </image:image>
    </url>
    <url>
    <loc>https://hak5.org/products/ubertooth-one</loc>
    <lastmod>2026-07-07T16:31:24-07:00</lastmod>
    <changefreq>daily</changefreq>
    <image:image>
    <image:loc>
    https://cdn.shopify.com/s/files/1/0068/2142/products/ubertooth.jpg?v=1496213414
    </image:loc>
    <image:title>Ubertooth One</image:title>
    <image:caption/>
    </image:image>
    </url>
    <url>
    <loc>https
    """

    # load the old data from the json file
    import json
    try:
        with open("hak5_products.json", "r") as f:
            old_products = json.load(f)
    except FileNotFoundError:
        old_products = []
        

    # convert the xml file to a list of products with dict for all the product data
    import xml.etree.ElementTree as ET
    root = ET.fromstring(response.content)
    
    # root.tag comes back as "{<namespace-uri>}urlset" - reuse that namespace to
    # query children, since ElementTree won't match bare "url"/"loc" tags otherwise.
    sitemap_ns = root.tag.split("}")[0].strip("{") if root.tag.startswith("{") else ""
    ns = {"sm": sitemap_ns, "image": "http://www.google.com/schemas/sitemap-image/1.1"}

    print(f"Found {len(root)} products in the XML file.")
    print(f"Root tag: {root.tag}, attributes: {root.attrib}")
    products = []
    """ if len(split_message) == 3 and split_message[2] == "update":
        # force update the product list without clearing the channel or deleting the json file only by updating all products
        await ctx.send("Force updating the Hak5 product list...")
        
        for url in root.findall("sm:url", ns):
            loc = url.find("sm:loc", ns)
            loc_text = loc.text if loc is not None else None

            old_product = next((p for p in old_products if p.get("loc") == loc_text), None) if old_products else None
            
            product = {}
            if loc_text is not None:
                product["loc"] = loc_text
            lastmod = url.find("sm:lastmod", ns)
            if lastmod is not None:
                product["lastmod"] = lastmod.text
            changefreq = url.find("sm:changefreq", ns)
            if changefreq is not None:
                product["changefreq"] = changefreq.text
            image = url.find("image:image", ns)
            if image is not None:
                image_loc = image.find("image:loc", ns)
                if image_loc is not None:
                    product["image_loc"] = image_loc.text
                image_title = image.find("image:title", ns)
                if image_title is not None:
                    product["image_title"] = image_title.text
                image_caption = image.find("image:caption", ns)
                if image_caption is not None:
                    product["image_caption"] = image_caption.text
            
            # Hak5's sitemap bumps <lastmod> daily for every product regardless of
            # whether it actually changed (changefreq is "daily"). Only hit the
            # live product page (which rate-limits us at ~30 req/run - see the
            # 429/503s in the logs) when the sitemap's own image fields hint that
            # something really changed; otherwise just carry the old record over.
            sitemap_fields = ("image_loc", "image_title", "image_caption")
            sitemap_unchanged = old_product is not None and all(
                old_product.get(f) == product.get(f) for f in sitemap_fields
            )
            
             """
    



    # For each product, get the loc, lastmod, changefreq, and image data, also generate a embed message with the product data and send it to the channel and add the id of the embed message to the product data dict, then save the product data to a json file
    changed_products = []
    for url in root.findall("sm:url", ns):
        loc = url.find("sm:loc", ns)
        loc_text = loc.text if loc is not None else None

        old_product = next((p for p in old_products if p.get("loc") == loc_text), None) if old_products else None

        product = {}
        if loc_text is not None:
            product["loc"] = loc_text
        lastmod = url.find("sm:lastmod", ns)
        if lastmod is not None:
            product["lastmod"] = lastmod.text
        changefreq = url.find("sm:changefreq", ns)
        if changefreq is not None:
            product["changefreq"] = changefreq.text
        image = url.find("image:image", ns)
        if image is not None:
            image_loc = image.find("image:loc", ns)
            if image_loc is not None:
                product["image_loc"] = image_loc.text
            image_title = image.find("image:title", ns)
            if image_title is not None:
                product["image_title"] = image_title.text
            image_caption = image.find("image:caption", ns)
            if image_caption is not None:
                product["image_caption"] = image_caption.text

        # Hak5's sitemap bumps <lastmod> daily for every product regardless of
        # whether it actually changed (changefreq is "daily"). Only hit the
        # live product page (which rate-limits us at ~30 req/run - see the
        # 429/503s in the logs) when the sitemap's own image fields hint that
        # something really changed; otherwise just carry the old record over.
        sitemap_fields = ("image_loc", "image_title", "image_caption")
        sitemap_unchanged = old_product is not None and all(
            old_product.get(f) == product.get(f) for f in sitemap_fields
        )



        if sitemap_unchanged and "update" not in split_message:
            print(f"Skipping {loc_text} because it hasn't changed since last time.")
            product["description"] = old_product.get("description")
            product["embed_message_id"] = old_product.get("embed_message_id")
            product["interested_users"] = old_product.get("interested_users", [])
            products.append(product)
            continue

        # get description from the website if the loc is pointing to.
        # example which is contained in the response to https://hak5.org/products/zzyzx
        """
        <meta property="og:description" content="Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed non risus. Suspendisse lectus tortor, dignissim sit amet, adipiscing nec, ultricies sed, dolor. Cras elementum ultrices diam. Maecenas ligula massa, varius a, semper congue, euismod non, mi.  Proin porttitor, orci nec nonummy molestie, enim est eleifend mi, n">
        """
        description = None
        if loc_text:
            try:
                response = requests.get(loc_text)
                if response.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(response.content, "html.parser")
                    # price: <meta property="product:price:amount" content="5.00">
  # <meta property="product:price:currency" content="USD">
                    price_meta = soup.find("meta", property="product:price:amount")
                    if price_meta and price_meta.get("content"):
                        product["price"] = price_meta["content"]
                    else:
                        print(f"No price span found for {loc_text}, setting to sold out.")
                        product["price"] = old_product.get("price") if old_product else "Sold Out"
                    # Sold out status:
                    sold_out_span = soup.find("span", class_="text")
                    if sold_out_span and "Sold Out" in sold_out_span.get_text():
                        product["status"] = "Sold Out"
                    else:
                        product["status"] = "In Stock"
                    meta_description = soup.find("meta", property="og:description")
                    if meta_description and meta_description.get("content"):
                        description = meta_description["content"]
                    else:
                        print(f"No og:description meta tag found for {loc_text}, keeping previous description.")
                        description = old_product.get("description") if old_product else None
                else:
                    print(f"Got status {response.status_code} fetching {loc_text}, keeping previous description.")
                    description = old_product.get("description") if old_product else None
            except Exception as e:
                print(f"Failed to get description from {loc_text}: {e}, keeping previous description.")
                description = old_product.get("description") if old_product else None

        if description is not None:
            product["description"] = description

        embed = fluxer.Embed(
            title=f"{product.get('image_title', product.get('loc'))}{' - ' + product.get('price') + ' USD' if product.get('price') else ''}{' (' + product.get('status') + ')' if product.get('status') == 'Sold Out' else ''}",
            description=description or product.get("image_caption") or "No description",
            url=product.get("loc"),
        )

        if product.get("image_loc"):
            embed.set_image(url=product["image_loc"])

        if old_product:
            interested_users = old_product.get("interested_users", [])
            product["interested_users"] = interested_users
            old_embed_message_id = old_product.get("embed_message_id")
            if old_embed_message_id:
                try:
                    old_embed_message = await products_channel.fetch_message(old_embed_message_id)
                    await old_embed_message.edit(embeds=[embed.to_dict()])
                    product["embed_message_id"] = old_embed_message_id
                    # ping the interested users in the channel that the product has been updated using a reaction to the new embed message
                    mentions = " ".join(f"<@{uid}>" for uid in interested_users)
                    if mentions:
                        await old_embed_message.reply(f"Product updated: [{product.get('image_title', product.get('loc'))}]({product.get('loc')})\n{mentions}")
                except Exception as e:
                    print(f"Failed to edit old embed message: {e}, posting a new one instead.")
                    embed_message = await products_channel.send(embed=embed)
                    await embed_message.add_reaction("⭐")  # add a star reaction for users to express interest
                    product["embed_message_id"] = embed_message.id
            else:
                print(f"No old embed message ID for {loc_text}, posting new embed.")
                embed_message = await products_channel.send(embed=embed)
                await embed_message.add_reaction("⭐")  # add a star reaction for users to express interest
                product["embed_message_id"] = embed_message.id
        else:
            interested_users = []
            # sending a new embed message to the channel
            product["interested_users"] = interested_users
            embed_message = await products_channel.send(embed=embed)
            await embed_message.add_reaction("⭐")  # add a star reaction for users to express interest
            product["embed_message_id"] = embed_message.id

        products.append(product)
        changed_products.append(product.get("image_title", product.get("loc")))

    # save the products to a json file
    import json
    with open("hak5_products.json", "w") as f:
        json.dump(products, f, indent=4)

    summary = f"Updated Hak5 product list: {len(changed_products)} product(s) changed and posted to {products_channel.mention}."
    if changed_products:
        # Discord caps message content at 2000 chars - a full catalog's worth of
        # titles can blow past that and fail the send outright, so cap the list.
        shown_names = ", ".join(changed_products[:25])
        if len(changed_products) > 25:
            shown_names += f", and {len(changed_products) - 25} more"
        summary += f"\nUpdated products: {shown_names}"
    await ctx.send(summary)
    
    

@bot.command()
@fluxer.has_permission(fluxer.Permissions.ADMINISTRATOR)
async def get_data(ctx: fluxer.models.message.Message):
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
                    guild = await bot.fetch_guild(guild_id)
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
                channel = await bot.fetch_channel(channel_id)
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
            user = await bot.fetch_user(user_id)
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
@fluxer.has_permission(fluxer.Permissions.ADMINISTRATOR)
async def bad_apple(ctx: fluxer.models.message.Message):
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


@bot.command()
@fluxer.has_permission(fluxer.Permissions.ADMINISTRATOR)
async def gen_channel_history(ctx: fluxer.models.message.Message):
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

if __name__ == "__main__":
    # Load token from .env file 
    dotenv.load_dotenv()
    TOKEN = os.getenv("FLUXER_TOKEN")
    bot.run(TOKEN)