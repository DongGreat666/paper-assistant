"""Use browser-use screenshots plus pyautogui to pass ResearchGate's checkbox."""

from __future__ import annotations

import asyncio
import json
import math
import time
from pathlib import Path

import pyautogui
from browser_use import BrowserSession
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SHOT = ROOT / "scripts" / "browser_use_security_check.png"
AFTER = ROOT / "scripts" / "browser_use_after_click.png"
URL = "https://www.researchgate.net/publication/220369917_Attention_Is_All_You_Need"


def find_checkbox_center(image_path: Path) -> tuple[int, int]:
    """Find the Cloudflare checkbox center from a browser-use screenshot."""
    img = Image.open(image_path).convert("RGB")
    width, height = img.size

    # The checkbox lives in the central challenge area. Search a generous band.
    x0, x1 = int(width * 0.25), int(width * 0.65)
    y0, y1 = int(height * 0.45), int(height * 0.75)
    dark = set()

    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b = img.getpixel((x, y))
            if r < 120 and g < 120 and b < 120:
                dark.add((x, y))

    seen: set[tuple[int, int]] = set()
    candidates: list[tuple[float, int, int, int, int]] = []

    for point in list(dark):
        if point in seen:
            continue
        stack = [point]
        seen.add(point)
        xs: list[int] = []
        ys: list[int] = []
        while stack:
            x, y = stack.pop()
            xs.append(x)
            ys.append(y)
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) in dark and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    stack.append((nx, ny))

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        box_w, box_h = max_x - min_x + 1, max_y - min_y + 1
        area = len(xs)

        # Cloudflare checkbox border is roughly a 20-28 px square.
        if 14 <= box_w <= 34 and 14 <= box_h <= 34 and area >= 35:
            square_error = abs(box_w - box_h)
            left_bias = min_x / width
            candidates.append((square_error + left_bias, min_x, min_y, max_x, max_y))

    if candidates:
        _, min_x, min_y, max_x, max_y = sorted(candidates)[0]
        return (min_x + max_x) // 2, (min_y + max_y) // 2

    # Fallback for the current ResearchGate challenge layout.
    return 510, 472


def screenshot_has_security_check(image_path: Path) -> bool:
    # Lightweight OCR-free check: the Cloudflare widget area is visible and has
    # the checkbox or spinner in the same central band.
    img = Image.open(image_path).convert("RGB")
    width, height = img.size
    x0, x1 = int(width * 0.35), int(width * 0.65)
    y0, y1 = int(height * 0.52), int(height * 0.70)
    dark_pixels = 0
    orange_pixels = 0
    green_pixels = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b = img.getpixel((x, y))
            if r < 130 and g < 130 and b < 130:
                dark_pixels += 1
            if r > 210 and 80 < g < 180 and b < 80:
                orange_pixels += 1
            if g > 120 and r < 80 and b < 120:
                green_pixels += 1
    return dark_pixels > 200 or orange_pixels > 20 or green_pixels > 20


async def viewport_to_screen(page, x: int, y: int) -> tuple[int, int]:
    raw = await page.evaluate(
        """() => ({
            screenX: window.screenX,
            screenY: window.screenY,
            outerWidth: window.outerWidth,
            outerHeight: window.outerHeight,
            innerWidth: window.innerWidth,
            innerHeight: window.innerHeight
        })"""
    )
    metrics = json.loads(raw)
    chrome_left = max((metrics["outerWidth"] - metrics["innerWidth"]) / 2, 0)
    chrome_top = max(metrics["outerHeight"] - metrics["innerHeight"] - chrome_left, 0)
    return math.floor(metrics["screenX"] + chrome_left + x), math.floor(metrics["screenY"] + chrome_top + y)


async def main() -> None:
    browser = BrowserSession(
        headless=False,
        accept_downloads=True,
        # browser-use 0.12.7 validates window_position as a ViewportSize.
        args=["--window-position=0,0", "--disable-blink-features=AutomationControlled"],
        window_size={"width": 1280, "height": 900},
        viewport={"width": 1280, "height": 760},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    )
    await browser.start()
    await browser.navigate_to(URL)
    await asyncio.sleep(4)

    page = await browser.get_current_page()

    for attempt in range(1, 31):
        print(f"Attempt {attempt}: taking browser-use screenshot for analysis...")
        await browser.take_screenshot(path=str(SHOT), full_page=False)

        if not screenshot_has_security_check(SHOT):
            print("Security check no longer detected. Leaving browser open.")
            break

        x, y = find_checkbox_center(SHOT)
        sx, sy = await viewport_to_screen(page, x, y)

        print(f"Detected checkbox center: viewport=({x}, {y}), screen=({sx}, {sy})")
        pyautogui.moveTo(sx, sy, duration=0.35)
        time.sleep(0.3)
        pyautogui.click()
        print("Clicked; waiting for Cloudflare result...")
        await asyncio.sleep(10)
        await browser.take_screenshot(path=str(AFTER), full_page=False)

    # Leave the browser open for the user to watch/continue if Cloudflare wants more input.
    print(f"Saved screenshots:\n  latest before/analysis: {SHOT}\n  latest after:           {AFTER}")
    print("Browser will stay open for 10 minutes.")
    await asyncio.sleep(600)
    await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
