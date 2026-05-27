import asyncio
from pathlib import Path

from browser_use import BrowserSession


ROOT = Path(__file__).resolve().parents[1]
CHROME_CANDIDATES = [
    Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
    Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
]


async def main():
    chrome = next(path for path in CHROME_CANDIDATES if path.exists())
    browser = BrowserSession(
        executable_path=str(chrome),
        headless=False,
        keep_alive=True,
        enable_default_extensions=False,
        user_data_dir=str(ROOT / ".browser-use-clean-profile"),
        accept_downloads=True,
        downloads_path=str(ROOT / "downloads"),
        window_size={"width": 1280, "height": 900},
        no_viewport=True,
    )
    await browser.start()
    print("normal Chrome opened through browser-use and kept alive", flush=True)
    await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
