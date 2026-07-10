import fluxer
from fluxer import Cog
from fluxer.checks import has_permission
import logging

logger = logging.getLogger(__name__)

class Hak5Tools(Cog):
    def __init__(self, bot: fluxer.Bot):
        super().__init__(bot)
    
    @Cog.listener
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

    @Cog.listener
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
    
    async def get_channel_by_name(guild: fluxer.models.guild.Guild, name: str) -> fluxer.models.channel.Channel | None:
        """fluxer has no cache/lookup for guild channels by name, so hit the API directly."""
        data = await bot._http.get_guild_channels(guild.id)
        for channel_data in data:
            if channel_data.get("name") == name:
                return fluxer.models.channel.Channel.from_data(channel_data, bot._http)
        return None

    
    @Cog.command()
    @fluxer.has_permission(fluxer.Permissions.ADMINISTRATOR)
    async def update_hak5_product_list(ctx: fluxer.models.message.Message):
        """
        Description: Updates the Hak5 product list from the specified XML URL.
        
        Usage: /update_hak5_product_list <url to xml file> [force] [update]
        """
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



async def setup(bot: fluxer.Bot):
    await bot.add_cog(Hak5Tools(bot))

async def teardown(bot):
    await bot.remove_cog("Hak5Tools")