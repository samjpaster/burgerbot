import logging
import logging.handlers
import nextcord
from nextcord.ext import commands
from db import init_db
from config import DISCORD_TOKEN

LOG_PATH = r"D:\development\burgers\bot.log"

_formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_file_handler = logging.handlers.RotatingFileHandler(
    LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(_formatter)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)

logging.basicConfig(level=logging.INFO, handlers=[_file_handler, _console_handler])
log = logging.getLogger("bot")

intents = nextcord.Intents.default()
bot = commands.Bot(intents=intents)


@bot.event
async def on_ready():
    await init_db()
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    log.info("Bot is ready.")


bot.load_extension("cogs.episodes")
bot.load_extension("cogs.burgers")
bot.load_extension("cogs.characters")

bot.run(DISCORD_TOKEN)
