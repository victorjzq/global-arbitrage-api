#!/usr/bin/env python3
"""用 Playwright 从 HTML 报告生成 PDF"""
import sys, os, glob
from pathlib import Path
from playwright.sync_api import sync_playwright

REPORTS_DIR = Path(__file__).resolve().parent.parent / "data" / "reports"

def html_to_pdf(html_path, pdf_path):
    """Convert HTML file to PDF using Chromium"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"file://{html_path}", wait_until="networkidle")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            margin={"top": "20mm", "bottom": "20mm", "left": "15mm", "right": "15mm"},
            print_background=True,
        )
        browser.close()
    print(f"✅ PDF: {pdf_path} ({os.path.getsize(pdf_path) // 1024}KB)")

def main():
    # Find latest HTML reports
    for lang in ["CN", "EN"]:
        pattern = str(REPORTS_DIR / f"*-arbitrage-report-{lang}.html")
        files = sorted(glob.glob(pattern), reverse=True)
        if files:
            html_path = files[0]
            pdf_path = html_path.replace(".html", ".pdf")
            print(f"Converting: {os.path.basename(html_path)}")
            html_to_pdf(html_path, pdf_path)

if __name__ == "__main__":
    main()
