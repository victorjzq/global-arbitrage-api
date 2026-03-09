#!/usr/bin/env python3
"""
直接把套利报告发布到 Substack — 第一个真正的变现动作
复用已有的 Substack cookie 和发布函数
"""
import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime

# 复用已有的 Substack 配置
SUBDOMAIN = "victorjia"
USER_ID = 68314544
BASE_URL = f"https://{SUBDOMAIN}.substack.com"

# 从已有 .env 读取 cookie
ENV_FILE = Path(os.path.expanduser("~/dev/Claude-Global/公众号国际化/.env"))
REPORT_DIR = Path(__file__).resolve().parent.parent / "data" / "reports"


def get_cookie():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if "SUBSTACK_SID" in line and "=" in line:
                return line.split("=", 1)[1].strip()
    cookie = os.environ.get("SUBSTACK_SID", "")
    if not cookie:
        print("❌ No SUBSTACK_SID found")
        sys.exit(1)
    return cookie


def md_to_substack_html(md_text):
    """简单 markdown → HTML（Substack 兼容）"""
    import re
    lines = md_text.strip().split("\n")
    html_parts = []
    i = 0
    skip_first = True

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        # 跳过第一个标题（作为 title 单独传）
        if skip_first and line.startswith("#"):
            skip_first = False
            i += 1
            continue
        skip_first = False

        # 标题
        import re
        hm = re.match(r"^(#{1,6})\s+(.*)", line)
        if hm:
            lvl = len(hm.group(1))
            html_parts.append(f"<h{lvl}>{hm.group(2).strip()}</h{lvl}>")
            i += 1
            continue

        # 分隔线
        if line.strip() in ("---", "***"):
            html_parts.append("<hr>")
            i += 1
            continue

        # 表格 → 简单HTML表格
        if "|" in line and i + 1 < len(lines) and "---" in lines[i + 1]:
            headers = [c.strip() for c in line.split("|") if c.strip()]
            i += 2  # 跳过分隔行
            rows = []
            while i < len(lines) and "|" in lines[i]:
                cells = [c.strip() for c in lines[i].split("|") if c.strip()]
                rows.append(cells)
                i += 1
            table = "<table><thead><tr>"
            table += "".join(f"<th>{h}</th>" for h in headers)
            table += "</tr></thead><tbody>"
            for row in rows:
                table += "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
            table += "</tbody></table>"
            html_parts.append(table)
            continue

        # 列表
        lm = re.match(r"^[\*\-✅🟢🟡]\s+(.*)", line)
        if lm:
            items = []
            while i < len(lines) and re.match(r"^[\*\-✅🟢🟡]\s+", lines[i]):
                m = re.match(r"^[\*\-✅🟢🟡]\s+(.*)", lines[i])
                if m:
                    items.append(f"<li>{m.group(1).strip()}</li>")
                i += 1
            html_parts.append(f'<ul>{"".join(items)}</ul>')
            continue

        # 段落
        para = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith("#") and "|" not in lines[i]:
            para.append(lines[i])
            i += 1
        text = " ".join(l.strip() for l in para)
        text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
        if text.strip():
            html_parts.append(f"<p>{text}</p>")

    return "".join(html_parts)


def publish_to_substack(cookie, title, html_body):
    """发布到 Substack"""
    session = requests.Session()
    session.cookies.set("substack.sid", cookie, domain=f"{SUBDOMAIN}.substack.com")

    # 创建草稿
    resp = session.post(
        f"{BASE_URL}/api/v1/drafts",
        json={
            "draft_title": title,
            "draft_body": html_body,
            "type": "newsletter",
            "draft_bylines": [{"id": USER_ID, "is_guest": False}],
        },
    )
    resp.raise_for_status()
    draft = resp.json()
    draft_id = draft.get("id")
    if not draft_id:
        raise Exception(f"No draft ID: {resp.text[:200]}")

    # 发布（不发邮件）
    resp2 = session.post(
        f"{BASE_URL}/api/v1/drafts/{draft_id}/publish",
        json={"send": False},
    )
    resp2.raise_for_status()

    slug = draft.get("slug", "")
    url = f"{BASE_URL}/p/{slug}" if slug else f"{BASE_URL} (draft {draft_id})"
    return draft_id, url


def main():
    cookie = get_cookie()
    print(f"🔑 Cookie loaded")

    # 找最新的英文报告
    en_reports = sorted(REPORT_DIR.glob("*EN*.md"))
    if not en_reports:
        print("❌ No EN reports found")
        return

    report_path = en_reports[-1]
    print(f"📄 Publishing: {report_path.name}")

    md_text = report_path.read_text()

    # 提取标题
    title = "Cross-Border E-Commerce Arbitrage Report — March 2026"
    for line in md_text.splitlines():
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            break

    # 转换并发布
    html = md_to_substack_html(md_text)
    print(f"📝 HTML generated: {len(html)} chars")

    try:
        draft_id, url = publish_to_substack(cookie, title, html)
        print(f"✅ Published! Draft ID: {draft_id}")
        print(f"🔗 URL: {url}")

        # 记录到 inbox
        inbox = Path(os.path.expanduser("~/cowork-brain/inbox.md"))
        with open(inbox, "r") as f:
            content = f.read()
        entry = f"\n## [{datetime.now().strftime('%Y-%m-%d %H:%M')}] ✅ 套利报告已发布 Substack\n- URL: {url}\n- Draft ID: {draft_id}\n- 文件: {report_path.name}\n\n"
        with open(inbox, "w") as f:
            f.write(entry + content)

    except Exception as e:
        print(f"❌ Failed: {e}")


if __name__ == "__main__":
    main()
