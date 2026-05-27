import asyncio
from pathlib import Path

from browser_use import BrowserSession


ROOT = Path(__file__).resolve().parents[1]


async def main():
    browser = BrowserSession(
        cdp_url="http://127.0.0.1:9223",
        keep_alive=True,
        accept_downloads=True,
        downloads_path=str(ROOT / "downloads"),
    )
    await browser.start()
    print("browser-use connected to normal Chrome on CDP 9223", flush=True)
    await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
