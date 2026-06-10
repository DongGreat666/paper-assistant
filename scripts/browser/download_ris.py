"""Download the RIS citation for "Attention Is All You Need" from ResearchGate.

The ResearchGate Cloudflare check is rendered in a real browser window, so the
script uses pyautogui for the checkbox click and Playwright for normal page
automation/download handling.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import pyautogui
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "browser"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "downloads" / "attention_is_all_you_need.ris"
PAPER_URL = "https://www.researchgate.net/publication/220369917_Attention_Is_All_You_Need"


def viewport_to_screen(page: Page, x: float, y: float) -> tuple[int, int]:
    metrics = page.evaluate(
        """() => ({
            screenX: window.screenX,
            screenY: window.screenY,
            outerWidth: window.outerWidth,
            outerHeight: window.outerHeight,
            innerWidth: window.innerWidth,
            innerHeight: window.innerHeight
        })"""
    )
    chrome_left = max((metrics["outerWidth"] - metrics["innerWidth"]) / 2, 0)
    chrome_top = max(metrics["outerHeight"] - metrics["innerHeight"] - chrome_left, 0)
    return int(metrics["screenX"] + chrome_left + x), int(metrics["screenY"] + chrome_top + y)


def pyautogui_click_viewport(page: Page, x: float, y: float, label: str) -> None:
    sx, sy = viewport_to_screen(page, x, y)
    pyautogui.moveTo(sx, sy, duration=0.15)
    pyautogui.click()
    print(f"Clicked {label} at viewport=({x:.0f}, {y:.0f}), screen=({sx}, {sy})")


def is_security_check(page: Page) -> bool:
    text = page.locator("body").inner_text(timeout=3000).lower()
    html = page.content().lower()
    markers = [
        "security check required",
        "complete the security check",
        "cloudflare",
        "checking your browser",
        "请验证您是真人",
    ]
    return any(marker in text or marker in html for marker in markers)


def click_cloudflare_check(page: Page) -> bool:
    selectors = [
        "iframe[title*='Cloudflare']",
        "iframe[src*='turnstile']",
        "iframe[src*='challenge']",
        "iframe",
    ]
    for selector in selectors:
        frame = page.locator(selector).first
        try:
            if not frame.is_visible(timeout=1500):
                continue
            box = frame.bounding_box()
        except Exception:
            continue
        if not box:
            continue
        pyautogui_click_viewport(page, box["x"] + 22, box["y"] + box["height"] / 2, selector)
        return True

    # Fallback for the 1280x760 ResearchGate security page seen in screenshots.
    pyautogui_click_viewport(page, 510, 472, "Cloudflare checkbox fallback")
    return True


def pass_security_check(page: Page, timeout: int = 90) -> bool:
    deadline = time.time() + timeout
    last_click = 0.0
    while time.time() < deadline:
        if not is_security_check(page):
            print("Security check is no longer visible.")
            return True
        if time.time() - last_click > 8:
            print("Security check detected; clicking checkbox with pyautogui...")
            click_cloudflare_check(page)
            last_click = time.time()
        time.sleep(4)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except PlaywrightTimeoutError:
            pass

        page.screenshot(path=str(ARTIFACTS / "cloudflare_timeout.png"), full_page=True)
    print("Security check did not clear before timeout.")
    return False


def click_first_visible(page: Page, patterns: list[str], timeout: int = 3000) -> bool:
    for pattern in patterns:
        locators = [
            page.get_by_role("button", name=re.compile(pattern, re.I)).first,
            page.get_by_role("link", name=re.compile(pattern, re.I)).first,
            page.locator(f"text=/{pattern}/i").first,
        ]
        for locator in locators:
            try:
                if locator.is_visible(timeout=timeout):
                    locator.click(timeout=timeout)
                    print(f"Clicked: {pattern}")
                    return True
            except Exception:
                continue
    return False


def download_ris(page: Page) -> bool:
    print("Looking for citation/export controls...")
    page.screenshot(path=str(ARTIFACTS / "after_security.png"), full_page=True)

    click_first_visible(page, [r"cite", r"citation", r"export citation", r"export"])
    time.sleep(2)

    with page.expect_download(timeout=15000) as download_info:
        if not click_first_visible(page, [r"\bRIS\b", r"Research Information Systems"]):
            return False

    download = download_info.value
    download.save_as(str(OUT))
    print(f"Saved RIS to {OUT}")
    return True


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--window-position=0,0",
                "--window-size=1280,900",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = browser.new_context(
            accept_downloads=True,
            viewport={"width": 1280, "height": 760},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        print("Opening ResearchGate paper page...")
        page.goto(PAPER_URL, wait_until="domcontentloaded", timeout=45000)
        time.sleep(3)

        if not pass_security_check(page):
            browser.close()
            raise SystemExit(2)

        page.wait_for_load_state("domcontentloaded", timeout=30000)
        time.sleep(4)

        if not download_ris(page):
            page.screenshot(path=str(ARTIFACTS / "ris_not_found.png"), full_page=True)
            print("Could not find the RIS download option. Saved ris_not_found.png for inspection.")
            browser.close()
            raise SystemExit(3)

        browser.close()


if __name__ == "__main__":
    main()
