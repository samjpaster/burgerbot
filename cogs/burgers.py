import json
import random
import logging
from datetime import datetime, time, timezone
from pathlib import Path
import nextcord
from nextcord.ext import commands, tasks

log = logging.getLogger("burgers")
from api import get_all_burger_ids, get_burger
from db import get_posted_ids, get_posted_count, mark_posted, reset_pool
from config import EMBED_COLOR, BURGER_CHANNEL_ID, POST_TIME

RECIPES_DIR = Path(__file__).parent.parent / "recipes"

# Parse POST_TIME (HH:MM UTC)
_hour, _minute = map(int, POST_TIME.split(":"))
_post_time_utc = time(hour=_hour, minute=_minute, tzinfo=timezone.utc)


def load_recipe(burger_id: int) -> dict | None:
    """Find and load the recipe JSON file for a given burger ID."""
    matches = list(RECIPES_DIR.glob(f"{burger_id}_*.json"))
    if not matches:
        return None
    try:
        with open(matches[0], encoding="utf-8") as f:
            data = json.load(f)
            return data.get("recipe")
    except Exception as e:
        log.warning(f"Failed to load recipe for burger ID {burger_id}: {e}")
        return None


def _truncate(text: str, limit: int) -> str:
    """Truncate text to fit within a character limit, appending '…' if cut."""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def build_burger_embeds(burger: dict, cycle_reset: bool = False) -> list[nextcord.Embed]:
    """
    Returns a list of embeds:
      [0] — burger info + history
      [1] — ingredients
      [2] — instructions
    If no recipe file is found, returns only embed [0] with a note.
    """
    name = burger["name"].strip('"')

    recipe = load_recipe(burger["id"])

    # ── Embed 1: Info + History ──────────────────────────────────────────
    info_embed = nextcord.Embed(
        title=f"🍔 Burger of the Day: {name}",
        url=burger.get("url", "") or "",
        color=EMBED_COLOR,
    )
    info_embed.add_field(name="Price", value=burger.get("price", "N/A"), inline=True)
    info_embed.add_field(name="Season", value=str(burger["season"]), inline=True)
    info_embed.add_field(name="Episode", value=str(burger["episode"]), inline=True)

    episode_url = burger.get("episodeUrl", "")
    if episode_url:
        info_embed.add_field(name="Episode Link", value=episode_url, inline=False)

    footer = "We've gone through every burger — starting over! Bob's Burgers" if cycle_reset else "Bob's Burgers"

    if not recipe:
        info_embed.set_footer(text=footer)
        return [info_embed]

    history = recipe.get("history", "")
    if history:
        info_embed.add_field(name="📖 History", value=_truncate(history, 1024), inline=False)

    info_embed.set_footer(text=footer)

    # ── Embed 2: Ingredients ─────────────────────────────────────────────
    ingredients = recipe.get("ingredients", [])
    if ingredients:
        lines = [f"• {item}" for item in ingredients]
        ingredients_text = "\n".join(lines)
        ingredients_embed = nextcord.Embed(
            title="🥩 Ingredients",
            description=_truncate(ingredients_text, 4096),
            color=EMBED_COLOR,
        )
    else:
        ingredients_embed = None

    # ── Embed 3: Instructions ────────────────────────────────────────────
    instructions = recipe.get("instructions", [])
    if instructions:
        lines = [f"{step}" for step in instructions]
        instructions_text = "\n".join(lines)
        instructions_embed = nextcord.Embed(
            title="👨‍🍳 Instructions",
            description=_truncate(instructions_text, 4096),
            color=EMBED_COLOR,
        )
    else:
        instructions_embed = None

    embeds = [info_embed]
    if ingredients_embed:
        embeds.append(ingredients_embed)
    if instructions_embed:
        embeds.append(instructions_embed)
    return embeds


async def pick_random_burger(table: str) -> tuple[dict, bool]:
    """
    Returns (burger_data, cycle_reset).
    cycle_reset=True means the pool was exhausted and has been reset.
    """
    all_ids = await get_all_burger_ids()
    posted = await get_posted_ids(table)
    remaining = list(set(all_ids) - posted)

    cycle_reset = False
    if not remaining:
        await reset_pool(table)
        remaining = all_ids
        cycle_reset = True

    chosen_id = random.choice(remaining)
    burger = await get_burger(chosen_id)
    await mark_posted(table, chosen_id)
    return burger, cycle_reset


class Burgers(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_burger.start()

    def cog_unload(self):
        self.daily_burger.cancel()

    # ------------------------------------------------------------------ #
    #  Slash command — user-triggered, separate pool                       #
    # ------------------------------------------------------------------ #
    @nextcord.slash_command(name="burger-of-the-day", description="Get a random Burger of the Day")
    async def burger_of_the_day(self, interaction: nextcord.Interaction):
        await interaction.response.defer()
        log.info(f"[/burger-of-the-day] Requested by {interaction.user} (ID: {interaction.user.id}) in #{interaction.channel} at {datetime.now():%Y-%m-%d %H:%M:%S}")
        burger, cycle_reset = await pick_random_burger("requested_burgers")
        name = burger["name"].strip('"')
        if cycle_reset:
            log.info(f"[/burger-of-the-day] Pool exhausted — resetting requested_burgers pool")
        log.info(f"[/burger-of-the-day] Serving: {name} (ID: {burger['id']}) S{burger['season']}E{burger['episode']}")
        embeds = build_burger_embeds(burger, cycle_reset)
        await interaction.followup.send(embeds=embeds)

    @nextcord.slash_command(name="burgers-left", description="See how many burgers have been sent and how many remain")
    async def burgers_left(self, interaction: nextcord.Interaction):
        await interaction.response.defer()
        log.info(f"[/burgers-left] Requested by {interaction.user} (ID: {interaction.user.id}) at {datetime.now():%Y-%m-%d %H:%M:%S}")

        all_ids = await get_all_burger_ids()
        total = len(all_ids)

        scheduled_sent = await get_posted_count("scheduled_burgers")
        requested_sent = await get_posted_count("requested_burgers")

        embed = nextcord.Embed(title="🍔 Burger Tracker", color=EMBED_COLOR)
        embed.add_field(
            name="Daily Auto-Post",
            value=f"**{scheduled_sent}** sent — **{total - scheduled_sent}** remaining",
            inline=False,
        )
        embed.add_field(
            name="User Queries (`/burger-of-the-day`)",
            value=f"**{requested_sent}** sent — **{total - requested_sent}** remaining",
            inline=False,
        )
        embed.set_footer(text=f"Total burgers in the pool: {total}")
        await interaction.followup.send(embed=embed)

    @nextcord.slash_command(name="burger-help", description="List all available Bob's Burgers bot commands")
    async def burger_help(self, interaction: nextcord.Interaction):
        embed = nextcord.Embed(
            title="🍔 Bob's Burgers Bot — Commands",
            color=EMBED_COLOR,
        )
        embed.add_field(
            name="/burger-of-the-day",
            value="Pulls a random Burger of the Day from the show. Won't repeat a burger until all 416 have been served. Includes the full recipe!",
            inline=False,
        )
        embed.add_field(
            name="/random-episode",
            value="Pulls a random Bob's Burgers episode with its description, air date, and viewer count.",
            inline=False,
        )
        embed.add_field(
            name="/random-character",
            value="Get info and a random quote for a Bob's Burgers character. Optionally pass a name (partial match).",
            inline=False,
        )
        embed.add_field(
            name="/burgers-left",
            value="Shows how many burgers have been sent by the daily auto-post and by user queries, and how many remain in each pool.",
            inline=False,
        )
        embed.add_field(
            name="/burger-help",
            value="Shows this help message.",
            inline=False,
        )
        embed.set_footer(text="Daily burger auto-posted at 12:00 EST • Bob's Burgers")
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------ #
    #  Scheduled daily post — separate pool                                #
    # ------------------------------------------------------------------ #
    @tasks.loop(time=_post_time_utc)
    async def daily_burger(self):
        channel = self.bot.get_channel(BURGER_CHANNEL_ID)
        if channel is None:
            log.warning(f"[daily] Could not find channel {BURGER_CHANNEL_ID}")
            return

        burger, cycle_reset = await pick_random_burger("scheduled_burgers")
        name = burger["name"].strip('"')
        if cycle_reset:
            log.info(f"[daily] Pool exhausted — resetting scheduled_burgers pool")
        log.info(f"[daily] Posting to #{channel}: {name} (ID: {burger['id']}) S{burger['season']}E{burger['episode']} at {datetime.now():%Y-%m-%d %H:%M:%S}")
        embeds = build_burger_embeds(burger, cycle_reset)
        await channel.send(embeds=embeds)

    @daily_burger.before_loop
    async def before_daily_burger(self):
        await self.bot.wait_until_ready()


def setup(bot: commands.Bot):
    bot.add_cog(Burgers(bot))
