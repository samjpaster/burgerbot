import httpx

BASE_URL = "https://bobsburgers-api.herokuapp.com"

async def get_all_burger_ids() -> list[int]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/burgerOfTheDay")
        resp.raise_for_status()
        data = resp.json()
        return [b["id"] for b in data]

async def get_burger(burger_id: int) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/burgerOfTheDay/{burger_id}")
        resp.raise_for_status()
        return resp.json()

async def get_all_episode_ids() -> list[int]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/episodes")
        resp.raise_for_status()
        data = resp.json()
        return [e["id"] for e in data]

async def get_episode(episode_id: int) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/episodes/{episode_id}")
        resp.raise_for_status()
        return resp.json()
