import os
import asyncpg


class Database:
    def __init__(self):
        self.pool = None

    async def init(self):
        self.pool = await asyncpg.create_pool(
            dsn=os.getenv(
                "DATABASE_URL",
                "postgresql://fluxer:fluxerpass@postgres:5432/fluxer",
            ),
            min_size=1,
            max_size=5,
        )
        await self._create_tables()

    async def close(self):
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def _create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hak5_products (
                    guild_id BIGINT NOT NULL,
                    loc TEXT NOT NULL,
                    lastmod TEXT,
                    changefreq TEXT,
                    image_loc TEXT,
                    image_title TEXT,
                    image_caption TEXT,
                    description TEXT,
                    price TEXT,
                    status TEXT,
                    embed_message_id BIGINT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (guild_id, loc)
                )
                """
            )

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hak5_product_interest (
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    product_loc TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (guild_id, user_id, product_loc)
                )
                """
            )

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hak5_new_product_subscribers (
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (guild_id, user_id)
                )
                """
            )

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hak5_server_settings (
                    guild_id BIGINT PRIMARY KEY,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    products_sitemap_url TEXT,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

    async def delete_guild_products(self, guild_id):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM hak5_products WHERE guild_id = $1", guild_id)
            await conn.execute(
                "DELETE FROM hak5_product_interest WHERE guild_id = $1",
                guild_id,
            )

    async def set_server_enabled(self, guild_id, enabled):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO hak5_server_settings (guild_id, enabled)
                VALUES ($1, $2)
                ON CONFLICT (guild_id) DO UPDATE SET enabled = EXCLUDED.enabled, updated_at = NOW()
                """,
                guild_id,
                enabled,
            )

    async def set_products_sitemap_url(self, guild_id, url):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO hak5_server_settings (guild_id, enabled, products_sitemap_url)
                VALUES ($1, TRUE, $2)
                ON CONFLICT (guild_id) DO UPDATE SET products_sitemap_url = EXCLUDED.products_sitemap_url, updated_at = NOW()
                """,
                guild_id,
                url,
            )

    async def get_server_settings(self, guild_id):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT enabled, products_sitemap_url FROM hak5_server_settings WHERE guild_id = $1",
                guild_id,
            )
            if row is None:
                return {"enabled": True, "products_sitemap_url": None}
            return {
                "enabled": row["enabled"],
                "products_sitemap_url": row["products_sitemap_url"],
            }

    async def get_enabled_guilds(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT guild_id FROM hak5_server_settings WHERE enabled = TRUE"
            )
            return [row["guild_id"] for row in rows]

    async def upsert_product(self, guild_id, product):
        if not product.get("loc"):
            return

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO hak5_products (
                    guild_id, loc, lastmod, changefreq, image_loc, image_title,
                    image_caption, description, price, status, embed_message_id
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (guild_id, loc) DO UPDATE SET
                    lastmod = EXCLUDED.lastmod,
                    changefreq = EXCLUDED.changefreq,
                    image_loc = EXCLUDED.image_loc,
                    image_title = EXCLUDED.image_title,
                    image_caption = EXCLUDED.image_caption,
                    description = EXCLUDED.description,
                    price = EXCLUDED.price,
                    status = EXCLUDED.status,
                    embed_message_id = EXCLUDED.embed_message_id,
                    updated_at = NOW()
                """,
                guild_id,
                product.get("loc"),
                product.get("lastmod"),
                product.get("changefreq"),
                product.get("image_loc"),
                product.get("image_title"),
                product.get("image_caption"),
                product.get("description"),
                product.get("price"),
                product.get("status"),
                product.get("embed_message_id"),
            )

    async def get_product(self, guild_id, loc):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT loc, lastmod, changefreq, image_loc, image_title, image_caption,
                       description, price, status, embed_message_id
                FROM hak5_products
                WHERE guild_id = $1 AND loc = $2
                """,
                guild_id,
                loc,
            )
            if row is None:
                return None

            interested_users = await conn.fetch(
                "SELECT user_id FROM hak5_product_interest WHERE guild_id = $1 AND product_loc = $2",
                guild_id,
                loc,
            )
            data = dict(row)
            data["interested_users"] = [record["user_id"] for record in interested_users]
            return data

    async def get_product_by_embed_message_id(self, guild_id, message_id):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT loc FROM hak5_products WHERE guild_id = $1 AND embed_message_id = $2",
                guild_id,
                message_id,
            )
            if row is None:
                return None
            return await self.get_product(guild_id, row["loc"])

    async def add_interest(self, guild_id, user_id, product_loc):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO hak5_product_interest (guild_id, user_id, product_loc)
                VALUES ($1, $2, $3)
                ON CONFLICT DO NOTHING
                """,
                guild_id,
                user_id,
                product_loc,
            )

    async def remove_interest(self, guild_id, user_id, product_loc):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM hak5_product_interest WHERE guild_id = $1 AND user_id = $2 AND product_loc = $3",
                guild_id,
                user_id,
                product_loc,
            )

    async def subscribe_to_new_products(self, guild_id, user_id):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO hak5_new_product_subscribers (guild_id, user_id)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
                """,
                guild_id,
                user_id,
            )

    async def unsubscribe_from_new_products(self, guild_id, user_id):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM hak5_new_product_subscribers WHERE guild_id = $1 AND user_id = $2",
                guild_id,
                user_id,
            )

    async def get_new_product_subscribers(self, guild_id):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT user_id FROM hak5_new_product_subscribers WHERE guild_id = $1",
                guild_id,
            )
            return [row["user_id"] for row in rows]
