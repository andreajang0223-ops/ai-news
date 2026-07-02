# AI 觀測誌

自用的 AI 新聞彙整站:每天早上 7:00(台北時間)自動抓取 8 個來源的 AI 新聞,由 Gemini 產生中文摘要、分類、重要度評分,並自動標記與你技能檔案相關的消息。零伺服器、零資料庫,整個網站就是這個 repo。

## 部署步驟(約 10 分鐘)

1. **建立 GitHub repo**:把這個資料夾的所有內容 push 上去(repo 設為 public 才能用免費的 GitHub Pages)。

2. **加入 API 金鑰**:到 repo 的 `Settings → Secrets and variables → Actions → New repository secret`,名稱填 `GEMINI_API_KEY`,值填你在 https://aistudio.google.com/apikey 取得的金鑰(用 Google 帳號登入即可建立)。

3. **開啟 GitHub Pages**:`Settings → Pages → Source` 選 `Deploy from a branch`,分支選 `main`、資料夾選 `/ (root)`。

4. **手動跑第一次**:到 `Actions → daily-ai-news → Run workflow`,執行完後 `data/news.json` 就會換成真實新聞,網站約一分鐘後更新。

之後每天早上 7:00 會自動更新,不需要做任何事。

## 日常使用

- **看新聞**:開你的 Pages 網址,依重要度排序,點分類籤或「與我的技能相關」篩選。
- **更新技能**:直接編輯 `data/skills.json`——調整 `level`(1-5)、`last_used`、`note`、`todo`。`keywords` 會影響 Gemini 的技能配對,學了新工具就加一筆。
- **調整來源**:編輯 `scripts/fetch_news.py` 開頭的 `SOURCES` 清單,任何有 RSS 的網站都能加。

## 本機預覽

```bash
python -m http.server
# 開 http://localhost:8000
```

(直接雙擊 index.html 會因瀏覽器安全限制讀不到 JSON,必須用本機伺服器。)

## 成本估算

每天約 30-40 篇文章的摘要,使用 gemini-3.5-flash 且一天只呼叫 3-4 次,Gemini API 的免費層額度通常就夠用,即使超出免費層,每月費用也在 1 美元上下。想更省可以在 workflow 加環境變數 `NEWS_MODEL: gemini-3.1-flash-lite`。

## 檔案結構

```
├── index.html                    # 前端(新聞牆 + 技能檔案)
├── data/
│   ├── news.json                 # 每日新聞(自動產生)
│   ├── skills.json               # 你的技能檔案(手動維護)
│   └── archive/                  # 每日存檔
├── scripts/fetch_news.py         # 抓取 + Gemini 摘要腳本
├── .github/workflows/daily.yml   # 每日排程
└── requirements.txt
```

## 之後可以加的功能(第三階段)

- 每週日讓 Gemini 彙整「本週必知 5 件事」
- 從新聞卡片一鍵加入技能 todo
- 歷史存檔瀏覽頁(data/archive 已經在累積資料了)
