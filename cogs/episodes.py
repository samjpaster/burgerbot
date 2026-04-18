import random
import logging
from datetime import datetime
import nextcord
from nextcord.ext import commands
from api import get_all_episode_ids, get_episode
from config import EMBED_COLOR

log = logging.getLogger("episodes")


class Episodes(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @nextcord.slash_command(name="random-episode", description="Get a random Bob's Burgers episode")
    async def random_episode(self, interaction: nextcord.Interaction):
        await interaction.response.defer()
        log.info(f"[/random-episode] Requested by {interaction.user} (ID: {interaction.user.id}) in #{interaction.channel} at {datetime.now():%Y-%m-%d %H:%M:%S}")

        episode_ids = await get_all_episode_ids()
        episode_id = random.choice(episode_ids)
        ep = await get_episode(episode_id)
        log.info(f"[/random-episode] Serving: {ep['name'].strip(chr(34))} S{ep['season']}E{ep['episode']}")

        embed = nextcord.Embed(
            title=ep["name"].strip('"'),
            url=ep.get("wikiUrl", ""),
            color=EMBED_COLOR,
        )
        embed.add_field(name="Season", value=str(ep["season"]), inline=True)
        embed.add_field(name="Episode", value=str(ep["episode"]), inline=True)
        embed.add_field(name="Air Date", value=ep.get("airDate", "N/A"), inline=True)
        embed.add_field(name="Total Viewers", value=ep.get("totalViewers", "N/A"), inline=True)
        if ep.get("description"):
            embed.add_field(name="Description", value=ep["description"], inline=False)
        embed.set_footer(text="Bob's Burgers")

        await interaction.followup.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Episodes(bot))
