# test_connect.py
import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0]
        print(f"연결 성공!")
        print(f"URL: {page.url}")
        print(f"제목: {await page.title()}")

asyncio.run(test())
