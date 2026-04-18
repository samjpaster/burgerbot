import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN: str = os.environ["DISCORD_TOKEN"]
BURGER_CHANNEL_ID: int = int(os.environ["BURGER_CHANNEL_ID"])

# Default: 17:00 UTC = 12:00 EST
POST_TIME: str = os.getenv("POST_TIME", "17:00")

EMBED_COLOR: int = 0xF5C518  # Bob's Burgers yellow
