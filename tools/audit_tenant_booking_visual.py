"""Read-only Playwright audit for public room-to-booking entry screens."""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "luu_tru" / "kiem_thu" / "module_02" / "ui_tenant_booking_qa"
BASE_URL = "http://127.0.0.1:8012"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
VIEWPORTS = {"1440": (1440, 1000), "1024": (1024, 900), "768": (768, 900), "390": (390, 844)}


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
        for width_name, (width, height) in VIEWPORTS.items():
            for page_name, path in (("rooms", "/phong/"), ("room_detail", "/phong/1/")):
                page = browser.new_page(viewport={"width": width, "height": height})
                errors = []
                page.on("console", lambda message: errors.append(f"console:{message.type}:{message.text}") if message.type == "error" else None)
                page.on("pageerror", lambda error: errors.append(f"page:{error}"))
                response = page.goto(BASE_URL + path, wait_until="networkidle")
                metrics = page.evaluate("""() => ({
                    clientWidth: document.documentElement.clientWidth,
                    scrollWidth: document.documentElement.scrollWidth,
                    brokenImages: [...document.images].filter(i => i.complete && i.naturalWidth === 0).length
                })""")
                screenshot = OUTPUT / f"{page_name}_{width_name}.png"
                page.screenshot(path=str(screenshot), full_page=True)
                results.append({"page": page_name, "width": width, "status": response.status if response else None,
                                "overflow": metrics["scrollWidth"] > metrics["clientWidth"],
                                "broken_images": metrics["brokenImages"], "errors": errors,
                                "screenshot": screenshot.name})
                page.close()
        browser.close()
    (OUTPUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
