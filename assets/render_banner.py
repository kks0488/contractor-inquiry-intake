"""Render the checked-in HTML banner. Requires Playwright + Chromium."""

from pathlib import Path

from playwright.sync_api import sync_playwright

assets = Path(__file__).resolve().parent
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={"width": 1600, "height": 720}, device_scale_factor=1)
    page.goto((assets / "banner.html").as_uri())
    page.evaluate("document.fonts.ready")
    page.locator(".banner").screenshot(path=str(assets / "banner.png"))
    browser.close()
