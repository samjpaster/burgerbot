import json
import logging
import random
from pathlib import Path

import httpx
import nextcord
from nextcord.ext import commands

from config import EMBED_COLOR

log = logging.getLogger("characters")

QUOTES_PATH = Path(r"D:\development\burgers\character_quotes.json")

# ---------------------------------------------------------------------------
# Load quotes at import time (hot-reloadable via /reload-quotes in future)
# ---------------------------------------------------------------------------

def _load_quotes() -> dict[str, dict]:
    if not QUOTES_PATH.exists():
        log.warning(f"character_quotes.json not found at {QUOTES_PATH} — /random-character will have no quotes")
        return {}
    with QUOTES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


_quotes_db: dict[str, dict] = _load_quotes()


# ---------------------------------------------------------------------------
# API helper — search characters by name
# ---------------------------------------------------------------------------

BASE_API = "https://bobsburgers-api.herokuapp.com"


async def search_character(name: str) -> dict | None:
    """Return the first character whose name contains `name` (case-insensitive)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{BASE_API}/characters", params={"name": name})
        resp.raise_for_status()
        results = resp.json()
    if not results:
        return None
    return results[0]


# ---------------------------------------------------------------------------
# Embed builder
# ---------------------------------------------------------------------------

def build_character_embed(char: dict, quote: str | None) -> nextcord.Embed:
    name: str = char.get("name", "Unknown")
    wiki_url: str = char.get("wikiUrl", "")

    embed = nextcord.Embed(
        title=f"🎙️ {name}",
        url=wiki_url or nextcord.Embed.Empty,
        color=EMBED_COLOR,
    )

    # Optional character image (API field: "image")
    image = char.get("image", "")
    if image:
        embed.set_thumbnail(url=image)

    # Voice actor
    voiced_by: str = char.get("voicedBy", "")
    if voiced_by:
        embed.add_field(name="Voiced by", value=voiced_by, inline=True)

    # Gender
    gender: str = char.get("gender", "")
    if gender:
        embed.add_field(name="Gender", value=gender, inline=True)

    # Hair color
    hair: str = char.get("hairColor", "")
    if hair:
        embed.add_field(name="Hair color", value=hair, inline=True)

    # Occupation
    occupation: str = char.get("occupation", "")
    if occupation:
        embed.add_field(name="Occupation", value=occupation, inline=False)

    # Quote
    if quote:
        embed.add_field(name="Quote", value=f'*"{quote}"*', inline=False)
    else:
        embed.add_field(name="Quote", value="*(No quotes available for this character)*", inline=False)

    embed.set_footer(text="Bob's Burgers")
    return embed


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class Characters(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @nextcord.slash_command(
        name="random-character",
        description="Get info and a random quote for a Bob's Burgers character",
    )
    async def random_character(
        self,
        interaction: nextcord.Interaction,
        name: str = nextcord.SlashOption(
            name="name",
            description="Character name (partial match, e.g. 'Bob', 'Linda', 'Tina')",
            required=False,
            default=None,
        ),
    ):
        await interaction.response.defer()

        # ------------------------------------------------------------------
        # If no name given, pick a random character from the quotes DB
        # ------------------------------------------------------------------
        if name is None:
            if _quotes_db:
                name = random.choice(list(_quotes_db.keys()))
                log.info(f"[/random-character] No name given — randomly picked '{name}'")
            else:
                await interaction.followup.send(
                    "No character quotes data available. Run `scrape_quotes.py` first.",
                    ephemeral=True,
                )
                return

        log.info(f"[/random-character] Requested by {interaction.user} for character '{name}'")

        # ------------------------------------------------------------------
        # Fetch character info from API
        # ------------------------------------------------------------------
        try:
            char = await search_character(name)
        except Exception as exc:
            log.error(f"[/random-character] API error: {exc}")
            await interaction.followup.send("Failed to reach the Bob's Burgers API. Try again later.", ephemeral=True)
            return

        if char is None:
            await interaction.followup.send(
                f"No character found matching **{name}**. Try a different name.",
                ephemeral=True,
            )
            return

        char_name: str = char.get("name", name)
        log.info(f"[/random-character] Resolved to API character: '{char_name}'")

        # ------------------------------------------------------------------
        # Look up quotes — try exact match first, then case-insensitive
        # ------------------------------------------------------------------
        quote: str | None = None

        entry = _quotes_db.get(char_name) or next(
            (v for k, v in _quotes_db.items() if k.lower() == char_name.lower()), None
        )
        if entry and entry.get("quotes"):
            quote = random.choice(entry["quotes"])
            log.info(f"[/random-character] Selected quote ({len(quote)} chars)")
        else:
            log.info(f"[/random-character] No quotes found for '{char_name}'")

        embed = build_character_embed(char, quote)
        await interaction.followup.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Characters(bot))
