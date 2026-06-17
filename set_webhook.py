import asyncio
import aiohttp
import sys

async def set_webhook(token: str, url: str):
    webhook_url = f"{url}/webhook"
    api_url = f"https://api.telegram.org/bot{token}/setWebhook"
    async with aiohttp.ClientSession() as session:
        async with session.post(api_url, json={"url": webhook_url}) as resp:
            data = await resp.json()
            if data.get("ok"):
                print(f"✅ Webhook set to: {webhook_url}")
            else:
                print(f"❌ Error: {data}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python set_webhook.py YOUR_BOT_TOKEN YOUR_RENDER_URL")
        sys.exit(1)
    asyncio.run(set_webhook(sys.argv[1], sys.argv[2]))
