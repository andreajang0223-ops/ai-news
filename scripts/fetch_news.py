#!/usr/bin/env python3
"""每日 AI 新聞抓取 → Gemini 摘要分類 → 輸出 data/news.json

在 GitHub Actions 上執行,需要環境變數 GEMINI_API_KEY。
本機測試:GEMINI_API_KEY=xxx python scripts/fetch_news.py
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests

# ── 設定 ────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

MODEL = os.environ.get("NEWS_MODEL", "gemini-3.5-flash")
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
HOURS_WINDOW = 36          # 抓取過去 N 小時內的文章
MAX_ITEMS = 40             # 每日最多處理篇數
BATCH_SIZE = 12            # 每次 API 呼叫處理的篇數

# 資料來源:name / url / lang(給 Gemini 的提示)
SOURCES = [
    {"name": "Anthropic", "url": "https://www.anthropic.com/news/rss.xml", "lang": "en"},
    {"name": "OpenAI", "url": "https://openai.com/news/rss.xml", "lang": "en"},
    {"name": "Google AI Blog", "url": "https://blog.google/technology/ai/rss/", "lang": "en"},
    {"name": "Hugging Face", "url": "https://huggingface.co/blog/feed.xml", "lang": "en"},
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "lang": "en"},
    {"name": "The Verge AI", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "lang": "en"},
    {"name": "iThome", "url": "https://www.ithome.com.tw/rss", "lang": "zh"},
    {"name": "arXiv cs.AI", "url": "https://rss.arxiv.org/rss/cs.AI", "lang": "en"},
]

CATEGORIES = ["模型發布", "工具更新", "產業動態", "研究論文"]


# ── 抓取 ────────────────────────────────────────────────

def fetch_entries():
    """從所有 RSS 來源抓取時間窗內的文章。"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_WINDOW)
    entries, seen_titles = [], set()

    for src in SOURCES:
        try:
            feed = feedparser.parse(src["url"])
        except Exception as e:
            print(f"[warn] {src['name']} 抓取失敗:{e}", file=sys.stderr)
            continue

        for e in feed.entries:
            ts = e.get("published_parsed") or e.get("updated_parsed")
            if ts:
                published = datetime(*ts[:6], tzinfo=timezone.utc)
                if published < cutoff:
                    continue
            else:
                published = datetime.now(timezone.utc)

            title = (e.get("title") or "").strip()
            if not title:
                continue
            key = re.sub(r"\W+", "", title.lower())[:60]
            if key in seen_titles:
                continue
            seen_titles.add(key)

            summary = re.sub(r"<[^>]+>", " ", e.get("summary", ""))
            summary = re.sub(r"\s+", " ", summary).strip()[:500]

            entries.append({
                "source": src["name"],
                "title": title,
                "link": e.get("link", ""),
                "published": published.isoformat(),
                "raw_summary": summary,
            })

    entries.sort(key=lambda x: x["published"], reverse=True)
    print(f"[info] 共抓到 {len(entries)} 篇,取前 {MAX_ITEMS} 篇")
    return entries[:MAX_ITEMS]


# ── Gemini 摘要分類 ─────────────────────────────────────

def build_prompt(batch, skills):
    skill_list = "\n".join(
        f"- {s['id']}: {s['name']}(關鍵字:{', '.join(s['keywords'])})"
        for s in skills
    )
    articles = "\n\n".join(
        f"[{i}] 來源:{e['source']}\n標題:{e['title']}\n內容摘錄:{e['raw_summary']}"
        for i, e in enumerate(batch)
    )
    return f"""你是一個 AI 新聞編輯,服務對象是一位台灣的工業設計系學生,他關注 AI 工具的實際應用。

以下是他的技能清單:
{skill_list}

請處理以下 {len(batch)} 篇文章,對每一篇:
1. summary:用繁體中文寫 2 句以內的摘要,說清楚「發生了什麼、為什麼重要」
2. category:從這四類選一個:{" / ".join(CATEGORIES)}
3. importance:1-5 的整數。5=重大模型或工具發布、3=值得知道、1=邊緣消息。與 AI 無關的文章給 0
4. skills:列出相關的技能 id(來自上面的清單),沒有就給空陣列

只回傳 JSON 陣列,不要任何其他文字或 markdown 標記,格式:
[{{"index": 0, "summary": "...", "category": "...", "importance": 3, "skills": ["claude-code"]}}]

文章:
{articles}"""


def call_gemini(prompt, api_key):
    resp = requests.post(
        API_URL,
        headers={
            "x-goog-api-key": api_key,
            "content-type": "application/json",
        },
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "maxOutputTokens": 8000,
            },
        },
        timeout=120,
    )
    resp.raise_for_status()
    candidates = resp.json().get("candidates", [])
    text = "".join(
        part.get("text", "")
        for c in candidates
        for part in c.get("content", {}).get("parts", [])
    )
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(text)


def enrich(entries, skills, api_key):
    """分批呼叫 Gemini,把摘要結果併回文章。API 失敗時保留原始標題。"""
    valid_ids = {s["id"] for s in skills}

    for start in range(0, len(entries), BATCH_SIZE):
        batch = entries[start:start + BATCH_SIZE]
        try:
            results = call_gemini(build_prompt(batch, skills), api_key)
        except Exception as e:
            print(f"[warn] 批次 {start} 摘要失敗:{e}", file=sys.stderr)
            results = []

        by_index = {r.get("index"): r for r in results if isinstance(r, dict)}
        for i, entry in enumerate(batch):
            r = by_index.get(i, {})
            entry["summary"] = r.get("summary", "")
            entry["category"] = r.get("category") if r.get("category") in CATEGORIES else "產業動態"
            entry["importance"] = int(r.get("importance", 0) or 0)
            entry["skills"] = [s for s in r.get("skills", []) if s in valid_ids]
            entry.pop("raw_summary", None)

        time.sleep(1)

    # 過濾與 AI 無關的文章,依重要度排序
    entries = [e for e in entries if e.get("importance", 0) > 0]
    entries.sort(key=lambda x: (-x["importance"], x["published"]), reverse=False)
    return entries


# ── 輸出 ────────────────────────────────────────────────

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[error] 缺少 GEMINI_API_KEY", file=sys.stderr)
        sys.exit(1)

    skills = json.loads((DATA / "skills.json").read_text(encoding="utf-8"))["skills"]
    entries = fetch_entries()
    entries = enrich(entries, skills, api_key)

    today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    payload = {
        "date": today,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(entries),
        "items": entries,
    }

    out = json.dumps(payload, ensure_ascii=False, indent=2)
    (DATA / "archive").mkdir(parents=True, exist_ok=True)
    (DATA / "news.json").write_text(out, encoding="utf-8")
    (DATA / "archive" / f"{today}.json").write_text(out, encoding="utf-8")
    print(f"[done] 輸出 {len(entries)} 篇 → data/news.json")


if __name__ == "__main__":
    main()
