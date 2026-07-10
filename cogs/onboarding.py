import asyncio
import fluxer
from fluxer import Cog
from fluxer.checks import has_permission
import logging

logger = logging.getLogger(__name__)

class Onboarding(Cog):
    def __init__(self, bot: fluxer.Bot):
        super().__init__(bot)
    
    @Cog.command()
    async def markdown(self, ctx: fluxer.models.message.Message):
        """
        Description: Shows a help message for formatting Markdown
        
        Usage: /markdown
        """
        
        # Generate a embed message to confirm the action
        embed = fluxer.Embed(
            title="Markdown Choice",
            description=f"With which Markdown do you need help?React with for:\n- 0️⃣ Both\n- 1️⃣ GitHub\n- 2️⃣ Fluxer"
        )

        confirmation_message = await ctx.send(embed=embed)
        await confirmation_message.add_reaction("0️⃣")
        await confirmation_message.add_reaction("1️⃣")
        await confirmation_message.add_reaction("2️⃣")

        # Messages don't cache their reactions (see fluxer's _handle_reaction_add),
        # so we listen for the raw gateway event instead of polling the message.
        future: asyncio.Future = asyncio.get_event_loop().create_future()

        async def on_raw_reaction_add(raw):
            if raw.message_id != confirmation_message.id or raw.user_id != ctx.author.id:
                return
            if raw.emoji.unicode in ("0️⃣", "1️⃣", "2️⃣") and not future.done():
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
        
        
        
        # ======== Fluxer ========
        
        # --- Text styles ---
        # *italic* or _italic_
        # **bold**
        # ***bold italic***
        # __underline__
        # __*underline italic*__
        # __**underline bold**__
        # __***underline bold italic***__
        # ~~strikethrough~~
        # ||spoiler||

        # --- Headers ---
        # # Header 1
        # ## Header 2
        # ### Header 3
        # -# Subtext (small greyed-out text)

        # --- Quotes ---
        # > single line quote
        # >>> multiline block quote (everything after this is quoted)

        # --- Lists ---
        # - bullet item
        # * bullet item
        # 1. numbered item

        # --- Code ---
        # `inline code`
        # ```lang
        # code block (lang enables syntax highlighting, e.g. py, js, diff)
        # ```
        # ```ansi
        # ANSI colored code block (supports terminal color codes)
        # ```

        # --- Links ---
        # [label](https://example.com) masked link
        # <https://example.com> suppress link embed/preview
        # \* escape markdown characters with a backslash

        # --- Mentions & timestamps ---
        # <@user_id> mention a user
        # <@&role_id> mention a role
        # <#channel_id> mention a channel
        # <t:unix_timestamp> default timestamp
        # <t:unix_timestamp:t/T/d/D/f/F/R> short time, long time, short date,
        #   long date, short date/time, long date/time, relative time
        
        fluxer_markdown_message  = "Markdown Formatting for Fluxer: \n"
        fluxer_markdown_message += "- _italic_: \\*italic\\* or \\_italic\\_\n"
        fluxer_markdown_message += "- **bold**: \\*\\*bold\\*\\*\n"
        fluxer_markdown_message += "- ***bold italic***: \\*\\*\\*bold italic\\*\\*\\*\n"
        fluxer_markdown_message += "- __underline__: \\_\\_underline\\_\\_\n"
        fluxer_markdown_message += "- __*underline italic*__: \\_\\_\\*underline italic\\*\\_\\_\n"
        fluxer_markdown_message += "- __**underline bold**__: \\_\\_\\*\\*underline bold\\*\\*\\_\\_\n"
        fluxer_markdown_message += "- __***underline bold italic***__: \\_\\_\\*\\*\\*underline bold italic\\*\\*\\*\\_\\_\n"
        fluxer_markdown_message += "- ~~strikethrough~~: \\~\\~strikethrough\\~\\~\n"
        fluxer_markdown_message += "- ||spoiler||: \\|\\|spoiler\\|\\|\n"
        fluxer_markdown_message += "- # Header 1: \\# Header 1\n"
        fluxer_markdown_message += "- ## Header 2: \\#\\# Header 2\n"
        fluxer_markdown_message += "- ### Header 3: \\#\\#\\# Header 3\n"
        fluxer_markdown_message += "- -# Subtext: \\-\\# Subtext\n"
        fluxer_markdown_message += "- > quote: \\> quote\n"
        fluxer_markdown_message += "- >>> block quote: \\>\\>\\> block quote\n"
        fluxer_markdown_message += "- bullet list: \\- item or \\* item\n"
        fluxer_markdown_message += "- numbered list: 1\\. item\n"
        fluxer_markdown_message += "- `inline code`: \\`inline code\\`\n"
        fluxer_markdown_message += "- code block: \\`\\`\\`lang ... \\`\\`\\`\n"
        fluxer_markdown_message += "- ansi code block: \\`\\`\\`ansi ... \\`\\`\\`\n"
        fluxer_markdown_message += "- [label](url) masked link: \\[label\\]\\(url\\)\n"
        fluxer_markdown_message += "- <url> suppress link embed: \\<url\\>\n"
        fluxer_markdown_message += "- \\\\\\* escape a markdown character\n"
        fluxer_markdown_message += "- <@user_id> mention a user\n"
        fluxer_markdown_message += "- <@&role_id> mention a role\n"
        fluxer_markdown_message += "- <#channel_id> mention a channel\n"
        fluxer_markdown_message += "- <t:unix_timestamp:FORMAT> timestamp (FORMAT: t/T/d/D/f/F/R)\n"

        fluxer_embed = fluxer.Embed(
            title="Fluxer Markdown",
            description=fluxer_markdown_message
        )

        # ======== GitHub ========

        # --- Text styles ---
        # *italic* or _italic_
        # **bold**
        # ***bold italic***
        # ~~strikethrough~~
        # ~subscript~
        # `inline code`

        # --- Headers ---
        # # H1
        # ## H2
        # ### H3
        # #### H4
        # ##### H5
        # ###### H6

        # --- Quotes & alerts ---
        # > blockquote
        # > [!NOTE]
        # > highlighted informational note
        # > [!TIP]
        # > helpful tip
        # > [!IMPORTANT]
        # > crucial information
        # > [!WARNING]
        # > critical content needing immediate attention
        # > [!CAUTION]
        # > negative potential consequences of an action

        # --- Lists ---
        # - bullet item
        # * bullet item
        # 1. numbered item
        #   - nested item (indent 2+ spaces)
        # - [ ] unchecked task list item
        # - [x] checked task list item

        # --- Code blocks ---
        # ```lang
        # code block (lang enables syntax highlighting, e.g. py, js, diff)
        # ```
        # ~~~lang
        # tilde-fenced code block (alternative to backticks)
        # ~~~

        # --- Links & images ---
        # [label](https://example.com) link
        # [label](https://example.com "tooltip title") link with title
        # ![alt text](https://example.com/image.png) image
        # <https://example.com> autolink
        # [label][ref] ... [ref]: https://example.com  reference-style link
        # [Relative link](../other-file.md) relative repo link
        # [Section link](#header-name) anchor link to a heading

        # --- Tables ---
        # | Header 1 | Header 2 |
        # | -------- | -------- |
        # | Cell 1   | Cell 2   |
        # | :--      | --:      |  left / right align (:-: for center)

        # --- Other GitHub-flavored extras ---
        # \* escape markdown characters with a backslash
        # Line ending in two trailing spaces  forces a line break
        # @username mentions a user
        # #123 references an issue or pull request
        # owner/repo#123 references an issue/PR in another repository
        # commit-sha references a commit
        # :emoji_name: emoji shortcode, e.g. :tada: :rocket: :bug:
        # <details><summary>Label</summary>hidden content</details> collapsible section
        # <kbd>Ctrl</kbd>+<kbd>C</kbd> keyboard key styling
        # ---  or  ***  horizontal rule
        # $inline math$ and $$block math$$ (LaTeX, via KaTeX)
        # [^1] footnote reference ... [^1]: footnote definition

        github_markdown_message  = "Markdown Formatting for GitHub: \n"
        github_markdown_message += "- _italic_: \\*italic\\* or \\_italic\\_\n"
        github_markdown_message += "- **bold**: \\*\\*bold\\*\\*\n"
        github_markdown_message += "- ***bold italic***: \\*\\*\\*bold italic\\*\\*\\*\n"
        github_markdown_message += "- ~~strikethrough~~: \\~\\~strikethrough\\~\\~\n"
        github_markdown_message += "- ~subscript~: \\~subscript\\~\n"
        github_markdown_message += "- `inline code`: \\`inline code\\`\n"
        github_markdown_message += "- # H1 ... ###### H6: \\# H1 ... \\#\\#\\#\\#\\#\\# H6\n"
        github_markdown_message += "- > blockquote: \\> blockquote\n"
        github_markdown_message += "- > [!NOTE] / [!TIP] / [!IMPORTANT] / [!WARNING] / [!CAUTION]: \\> \\[\\!NOTE\\]\n"
        github_markdown_message += "- bullet list: \\- item or \\* item\n"
        github_markdown_message += "- numbered list: 1\\. item\n"
        github_markdown_message += "- nested list: indent 2+ spaces before \\- item\n"
        github_markdown_message += "- unchecked task: \\- \\[ \\] item\n"
        github_markdown_message += "- checked task: \\- \\[x\\] item\n"
        github_markdown_message += "- code block: \\`\\`\\`lang ... \\`\\`\\`\n"
        github_markdown_message += "- tilde code block: \\~\\~\\~lang ... \\~\\~\\~\n"
        github_markdown_message += "- [label](url) link: \\[label\\]\\(url\\)\n"
        github_markdown_message += "- [label](url \"title\") link with title: \\[label\\]\\(url \\\"title\\\"\\)\n"
        github_markdown_message += "- ![alt](url) image: \\!\\[alt\\]\\(url\\)\n"
        github_markdown_message += "- <url> autolink: \\<url\\>\n"
        github_markdown_message += "- [label][ref] reference link: \\[label\\]\\[ref\\]\n"
        github_markdown_message += "- [text](#heading) anchor link: \\[text\\]\\(\\#heading\\)\n"
        github_markdown_message += "- table: \\| Header \\| Header \\|\\n\\| \\-\\- \\| \\-\\- \\|\\n\\| cell \\| cell \\|\n"
        github_markdown_message += "- \\\\\\* escape a markdown character\n"
        github_markdown_message += "- line ending in two spaces forces a line break\n"
        github_markdown_message += "- @username mentions a user\n"
        github_markdown_message += "- #123 references an issue or pull request\n"
        github_markdown_message += "- owner/repo#123 references an issue/PR in another repo\n"
        github_markdown_message += "- commit-sha references a commit\n"
        github_markdown_message += "- :emoji_name: emoji shortcode, e.g. \\:tada\\: \\:rocket\\: \\:bug\\:\n"
        github_markdown_message += "- <details><summary>label</summary>content</details> collapsible section\n"
        github_markdown_message += "- <kbd>Ctrl</kbd>+<kbd>C</kbd> keyboard key styling\n"
        github_markdown_message += "- \\-\\-\\- or \\*\\*\\* horizontal rule\n"
        github_markdown_message += "- $inline math$ and $$block math$$ (LaTeX)\n"
        github_markdown_message += "- [^1] footnote reference / \\[\\^1\\]: footnote definition\n"

        github_embed = fluxer.Embed(
            title="GitHub Markdown",
            description=github_markdown_message
        )

        
        
        if choice == "0️⃣":
            await ctx.send(embeds=[fluxer_embed, github_embed])
        elif choice == "1️⃣":
            await ctx.send(embed=github_embed)
        elif choice == "2️⃣":
            await ctx.send(embed=fluxer_embed)


async def setup(bot: fluxer.Bot):
    await bot.add_cog(Onboarding(bot))

async def teardown(bot):
    await bot.remove_cog("Onboarding")
