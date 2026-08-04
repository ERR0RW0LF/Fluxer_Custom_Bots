import asyncio
import logging
import os
from urllib.parse import urlparse

import fluxer
from fluxer import Cog, has_permission

from database import Database

logger = logging.getLogger(__name__)


class Hak5Tools(Cog):
    def __init__(self, bot: fluxer.Bot):
        super().__init__(bot)
        self._periodic_task = None

    async def clear_channel_helper(self, channel: fluxer.models.channel.Channel):
        while True:
            messages = await channel.fetch_messages(limit=100)
            if not messages:
                break
            for message in messages:
                try:
                    await message.delete()
                except Exception as exc:
                    print(f"[debug] clear_channel_helper failed: {exc}")

    async def notify_new_product_subscribers(self, guild_id, product_title, product_loc):
        subscribers = await self.bot.db.get_new_product_subscribers(guild_id)
        for user_id in subscribers:
            try:
                user = await self.bot.fetch_user(user_id)
                dm = await user.create_dm()
                await dm.send(
                    f"New Hak5 product added: {product_title}\n{product_loc}"
                )
            except Exception as exc:
                print(f"[debug] Failed to notify subscriber {user_id}: {exc}")

    async def _is_guild_owner(self, ctx: fluxer.models.message.Message):
        if ctx.guild is None or ctx.author is None:
            return False

        author_id = getattr(ctx.author, "id", None)
        if author_id is None:
            logger.debug("No author ID")
            return False

        owner_id = getattr(ctx.guild, "owner_id", None)
        if owner_id is None:
            guild_id = getattr(ctx.guild, "id", None)
            if guild_id is not None:
                try:
                    guild_data = await self.bot._http.get_guild(guild_id)
                    owner_id = guild_data.get("owner_id")
                except Exception as exc:
                    logger.debug("Failed to fetch guild owner via HTTP: %s", exc)
            if owner_id is None:
                owner = getattr(ctx.guild, "owner", None)
                owner_id = getattr(owner, "id", None)

        if owner_id is None:
            logger.debug("No Owner ID")
            return False

        return int(author_id) == int(owner_id)

    async def _discover_products_sitemap_url(self, base_url="https://hak5.org/sitemap.xml"):
        import requests
        import xml.etree.ElementTree as ET

        response = requests.get(base_url, timeout=15)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to download {base_url}: {response.status_code}")

        root = ET.fromstring(response.content)
        sitemap_ns = root.tag.split("}")[0].strip("{") if root.tag.startswith("{") else ""
        ns = {"sm": sitemap_ns}
        sitemap_nodes = root.findall("sm:sitemap", ns)
        if sitemap_nodes:
            candidate_nodes = sitemap_nodes
        else:
            candidate_nodes = root.findall("sm:url", ns)

        for item in candidate_nodes:
            loc = item.find("sm:loc", ns)
            if loc is None or loc.text is None:
                continue
            loc_text = loc.text.strip()
            parsed_loc = urlparse(loc_text)
            loc_path = parsed_loc.path.lower()
            if "product" in loc_path and loc_path.endswith(".xml"):
                return loc_text
        raise RuntimeError("Could not find a product sitemap URL in the Hak5 sitemap")

    async def _refresh_guild_products(self, guild_id, guild, force=False):
        settings = await self.bot.db.get_server_settings(guild_id)
        if not settings.get("enabled", True):
            return None

        channel_name = os.getenv("PRODUCTS_CHANNEL_NAME")
        if not channel_name:
            return None

        if guild is None:
            try:
                guild = await self.bot.fetch_guild(guild_id)
            except Exception:
                return None

        products_channel = await self.get_channel_by_name(guild, channel_name)
        if products_channel is None:
            return None

        sitemap_url = settings.get("products_sitemap_url")
        if not sitemap_url:
            sitemap_url = await self._discover_products_sitemap_url()
            await self.bot.db.set_products_sitemap_url(guild_id, sitemap_url)

        import requests
        import xml.etree.ElementTree as ET

        response = requests.get(sitemap_url, timeout=15)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to download {sitemap_url}: {response.status_code}")

        root = ET.fromstring(response.content)
        sitemap_ns = root.tag.split("}")[0].strip("{") if root.tag.startswith("{") else ""
        ns = {"sm": sitemap_ns, "image": "http://www.google.com/schemas/sitemap-image/1.1"}

        changed_products = []
        for item in root.findall("sm:url", ns):
            loc = item.find("sm:loc", ns)
            loc_text = loc.text if loc is not None else None
            if not loc_text:
                continue

            old_product = await self.bot.db.get_product(guild_id, loc_text)
            product = {"loc": loc_text}

            lastmod = item.find("sm:lastmod", ns)
            if lastmod is not None:
                product["lastmod"] = lastmod.text
            changefreq = item.find("sm:changefreq", ns)
            if changefreq is not None:
                product["changefreq"] = changefreq.text

            image = item.find("image:image", ns)
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

            sitemap_fields = ("image_loc", "image_title", "image_caption")
            sitemap_unchanged = old_product is not None and all(
                old_product.get(f) == product.get(f) for f in sitemap_fields
            )

            if sitemap_unchanged and not force:
                product["description"] = old_product.get("description")
                product["embed_message_id"] = old_product.get("embed_message_id")
                product["interested_users"] = old_product.get("interested_users", [])
                await self.bot.db.upsert_product(guild_id, product)
                continue

            description = None
            try:
                product_response = requests.get(loc_text, timeout=15)
                if product_response.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(product_response.content, "html.parser")
                    price_meta = soup.find("meta", property="product:price:amount")
                    if price_meta and price_meta.get("content"):
                        product["price"] = price_meta["content"]
                    else:
                        product["price"] = old_product.get("price") if old_product else "Sold Out"

                    sold_out_span = soup.find("span", class_="text")
                    if sold_out_span and "Sold Out" in sold_out_span.get_text():
                        product["status"] = "Sold Out"
                    else:
                        product["status"] = "In Stock"

                    meta_description = soup.find("meta", property="og:description")
                    if meta_description and meta_description.get("content"):
                        description = meta_description["content"]
                    else:
                        description = old_product.get("description") if old_product else None
                else:
                    description = old_product.get("description") if old_product else None
            except Exception as exc:
                print(f"[debug] Failed to get description from {loc_text}: {exc}")
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
                        mentions = " ".join(f"<@{uid}>" for uid in interested_users)
                        if mentions:
                            await old_embed_message.reply(
                                f"Product updated: [{product.get('image_title', product.get('loc'))}]({product.get('loc')})\n{mentions}"
                            )
                    except Exception as exc:
                        print(f"Failed to edit old embed message: {exc}, posting a new one instead.")
                        embed_message = await products_channel.send(embed=embed)
                        await embed_message.add_reaction("⭐")
                        product["embed_message_id"] = embed_message.id
                else:
                    embed_message = await products_channel.send(embed=embed)
                    await embed_message.add_reaction("⭐")
                    product["embed_message_id"] = embed_message.id
            else:
                product["interested_users"] = []
                embed_message = await products_channel.send(embed=embed)
                await embed_message.add_reaction("⭐")
                product["embed_message_id"] = embed_message.id
                await self.notify_new_product_subscribers(guild_id, product.get("image_title", product.get("loc")), product.get("loc"))
                changed_products.append(product.get("image_title", product.get("loc")))

            await self.bot.db.append_price_history(guild_id, product)
            await self.bot.db.upsert_product(guild_id, product)
            if old_product:
                changed_products.append(product.get("image_title", product.get("loc")))

        return changed_products

    async def start_periodic_updates(self):
        if self._periodic_task is not None:
            return
        self._periodic_task = asyncio.create_task(self._periodic_loop())

    async def stop_periodic_updates(self):
        if self._periodic_task is not None:
            self._periodic_task.cancel()
            self._periodic_task = None

    async def _periodic_loop(self):
        while True:
            try:
                for guild_id in await self.bot.db.get_enabled_guilds():
                    try:
                        guild = self.bot.get_guild(guild_id)
                        await self._refresh_guild_products(guild_id, guild)
                    except Exception as exc:
                        print(f"[debug] periodic refresh failed for guild {guild_id}: {exc}")
            except Exception as exc:
                print(f"[debug] periodic refresh loop failed: {exc}")
            await asyncio.sleep(3600)

    @Cog.listener()
    async def on_raw_reaction_add(self, raw: fluxer.models.reaction.RawReactionActionEvent):
        print(f"[debug] on_raw_reaction_add: {raw}")
        if raw.user_id == self.bot.user.id:
            return

        product = await self.bot.db.get_product_by_embed_message_id(raw.guild_id, raw.message_id)
        if product is None:
            return

        emoji = getattr(raw.emoji, "unicode", None)
        if emoji == "⭐" and raw.user_id not in product.get("interested_users", []):
            await self.bot.db.add_interest(raw.guild_id, raw.user_id, product["loc"])
            print(f"[debug] Added user {raw.user_id} to interested_users for product {product.get('loc')}")
            user = await self.bot.fetch_user(raw.user_id)
            dm = await user.create_dm()
            await dm.send(
                f"You have been added to the interested_users list for product {product.get('loc')}. You will be notified when this product is updated."
            )

    @Cog.listener()
    async def on_raw_reaction_remove(self, raw):
        print(f"[debug] on_raw_reaction_remove: {raw}")

        if raw.user_id == self.bot.user.id:
            return

        product = await self.bot.db.get_product_by_embed_message_id(raw.guild_id, raw.message_id)
        if product is None:
            return

        emoji = getattr(raw.emoji, "unicode", None)
        if emoji == "⭐" and raw.user_id in product.get("interested_users", []):
            await self.bot.db.remove_interest(raw.guild_id, raw.user_id, product["loc"])
            print(f"[debug] Removed user {raw.user_id} from interested_users for product {product.get('loc')}")
            user = await self.bot.fetch_user(raw.user_id)
            dm = await user.create_dm()
            await dm.send(
                f"You have been removed from the interested_users list for product {product.get('loc')}. You will no longer be notified when this product is updated."
            )

    async def get_channel_by_name(self, guild: fluxer.models.guild.Guild, name: str) -> fluxer.models.channel.Channel | None:
        """fluxer has no cache/lookup for guild channels by name, so hit the API directly."""
        data = await self.bot._http.get_guild_channels(guild.id)
        for channel_data in data:
            if channel_data.get("name") == name:
                return fluxer.models.channel.Channel.from_data(channel_data, self.bot._http)
        return None

    @Cog.command()
    @has_permission(fluxer.Permissions.ADMINISTRATOR)
    async def update_hak5_product_list(self, ctx: fluxer.models.message.Message):
        """
        Description: Updates the Hak5 product list from the discovered product sitemap.

        Usage: /update_hak5_product_list [force] [update]
        """
        split_message = ctx.content.split()
        if len(split_message) > 2 or (len(split_message) == 2 and split_message[1] not in {"force", "update"}):
            await ctx.send("Usage: /update_hak5_product_list [force|update]")
            return

        if ctx.guild is None:
            await ctx.send("This command can only be used in a guild.")
            return

        #if not await self._is_guild_owner(ctx):
        #    await ctx.send("Only the server owner can manage Hak5 product updates.")
        #    return

        update_mode = len(split_message) == 2 and split_message[1] == "update"
        force_mode = len(split_message) == 2 and split_message[1] == "force"

        channel_name = os.getenv("PRODUCTS_CHANNEL_NAME")
        if not channel_name:
            await ctx.send("PRODUCTS_CHANNEL_NAME is not set in .env.")
            return

        products_channel = await self.get_channel_by_name(ctx.guild, channel_name)
        if products_channel is None:
            await ctx.send(f"Could not find a channel named '{channel_name}' in this guild.")
            return

        if force_mode:
            await ctx.reply("Clearing channel...")
            await self.clear_channel_helper(products_channel)
            await self.bot.db.delete_guild_products(ctx.guild_id)
            await ctx.send("Deleted previous Hak5 product records from the database.")

        try:
            changed_products = await self._refresh_guild_products(ctx.guild_id, ctx.guild, force=force_mode or update_mode)
        except Exception as exc:
            await ctx.send(f"Failed to refresh Hak5 products: {exc}")
            return

        summary = f"Updated Hak5 product list: {len(changed_products or [])} product(s) changed and posted to {products_channel.mention}."
        if changed_products:
            shown_names = ", ".join(changed_products[:25])
            if len(changed_products) > 25:
                shown_names += f", and {len(changed_products) - 25} more"
            summary += f"\nUpdated products: {shown_names}"
        await ctx.send(summary)

    @Cog.command()
    @has_permission(fluxer.Permissions.ADMINISTRATOR)
    async def enable_hak5_products(self, ctx: fluxer.models.message.Message):
        if ctx.guild is None:
            await ctx.send("This command can only be used in a guild.")
            return
        if not await self._is_guild_owner(ctx):
            await ctx.send("Only the server owner can enable Hak5 products.")
            return

        await self.bot.db.set_server_enabled(ctx.guild_id, True)
        await ctx.send("Hak5 product updates are now enabled for this server.")

    @Cog.command()
    @has_permission(fluxer.Permissions.ADMINISTRATOR)
    async def disable_hak5_products(self, ctx: fluxer.models.message.Message):
        if ctx.guild is None:
            await ctx.send("This command can only be used in a guild.")
            return
        if not await self._is_guild_owner(ctx):
            await ctx.send("Only the server owner can disable Hak5 products.")
            return

        await self.bot.db.set_server_enabled(ctx.guild_id, False)
        await ctx.send("Hak5 product updates are now disabled for this server.")

    @Cog.command()
    async def subscribe_hak5_updates(self, ctx: fluxer.models.message.Message):
        if ctx.guild_id is None:
            await ctx.send("Use this command in a server.")
            return

        await self.bot.db.subscribe_to_new_products(ctx.guild_id, ctx.author.id)
        await ctx.send("You will now receive a DM when a new Hak5 product is added in this server.")

    @Cog.command()
    async def unsubscribe_hak5_updates(self, ctx: fluxer.models.message.Message):
        if ctx.guild_id is None:
            await ctx.send("Use this command in a server.")
            return

        await self.bot.db.unsubscribe_from_new_products(ctx.guild_id, ctx.author.id)
        await ctx.send("You will no longer receive new-product notifications from this server.")

    @Cog.command()
    async def get_raw_full_price_product_history(self, ctx: fluxer.models.message.Message):
        content = ctx.content
        product_loc = content.removeprefix("/get_raw_full_price_product_history ").strip()
        db: Database = self.bot.db
        rows = await db.get_full_history_of_product(ctx.guild_id, product_loc)
        if not rows:
            await ctx.reply(f"No data found for: {product_loc}")
            return
        
        await ctx.reply(f"{rows}")
    
    @Cog.command()
    async def price_history(self, ctx: fluxer.models.message.Message):
        """
        Description: Get the price history of a Hak5 product and display it as a graph generated using matplotlib.
        
        Usage: /price_history <product_url>
        """
        
        content = ctx.content
        product_loc = content.removeprefix("/price_history ").strip()
        db: Database = self.bot.db
        
        rows = await db.get_full_history_of_product(ctx.guild_id, product_loc)
        if not rows:
            await ctx.reply(f"No price history found for: {product_loc}")
            return
        
        from matplotlib import pyplot as plt
        import io
        
        # Extract dates and prices from the rows
        dates = [row['observed_at'] for row in rows]
        prices = [float(row['price']) for row in rows]
        
        # Create the plot
        plt.figure(figsize=(10, 5))
        plt.plot(dates, prices, marker='o')
        plt.title(f"Price History for {product_loc}")
        plt.xlabel("Date")
        plt.ylabel("Price (USD)")
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Save the plot to a BytesIO object
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        await ctx.send(file=fluxer.File(buf, filename="price_history.png"))

async def setup(bot: fluxer.Bot):
    cog = Hak5Tools(bot)
    await bot.add_cog(cog)
    await cog.start_periodic_updates()


async def teardown(bot):
    cog = bot.get_cog("Hak5Tools")
    if cog is not None:
        await cog.stop_periodic_updates()
    await bot.remove_cog("Hak5Tools")