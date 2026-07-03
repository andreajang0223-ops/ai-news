# AI 觀測誌(ai-observatory)

自用的 AI 新聞彙整站 + 個人技能追蹤儀表板。零伺服器架構:GitHub Actions 每日排程抓 RSS,Gemini API 產生中文摘要,輸出 JSON 給靜態前端,部署在 GitHub Pages。

## 架構

```
RSS 來源(23 個:中文媒體 8 + 國際新聞站 5 + 社群媒體 9 + 論文 1)
  → scripts/fetch_news.py(GitHub Actions 每日 UTC 23:00 = 台北 07:00 執行)
  → Gemini API(摘要、分類、重要度 1-5、比對技能標籤)
  → data/news.json + data/archive/YYYY-MM-DD.json
  → index.html(純靜態,fetch JSON 渲染)
  → GitHub Pages
```

## 檔案說明

- `index.html`:唯一的前端檔案,單檔架構(HTML+CSS+JS),三個分頁:今日情報(依類別分組)/ 收藏(localStorage)/ 技能檔案(含 SVG 雷達圖)
- `scripts/fetch_news.py`:抓取 + Gemini 摘要腳本,SOURCES 清單在檔案開頭(含 type 欄位:news / social / paper)。來源以中文媒體為主;FB / IG / Threads / X 經 RSSHub 轉 RSS(見下方慣例)
- `data/skills.json`:技能檔案,**手動維護**,keywords 欄位影響 Gemini 的技能配對
- `data/news.json`:每日新聞,**自動產生,不要手動編輯**(會被下次排程覆蓋)
- `data/archive/`:每日存檔,自動累積
- `.github/workflows/daily.yml`:排程設定,secret 名稱是 `GEMINI_API_KEY`

## 重要慣例

- Gemini 模型:預設 `gemini-3.5-flash`,可用環境變數 `NEWS_MODEL` 覆蓋
- 選材以中文資訊為主:中文媒體來源佔多數,Gemini 提示對中文/華語圈消息略為加分;英文來源的摘要一律轉為繁體中文
- FB / IG / Threads / X 沒有官方 RSS,經 RSSHub 轉出(預設公共實例 `https://rsshub.app`,可用環境變數 `RSSHUB_BASE` 或 repo variable 換成自架實例)。Threads 路由可匿名使用;X 需要 `TWITTER_AUTH_TOKEN`、FB / IG 需要 cookie,公共實例上這三者常失敗——來源失敗只會印警告並跳過,不影響整體更新。社群帳號直接改 SOURCES 清單即可替換
- news.json 的 item 欄位:source / title / link / published / summary / category / importance(1-5)/ skills(id 陣列)
- category 固定六類:模型發布、工具更新、應用案例、產業動態、社群討論、研究論文
- 選材以 AI 應用類為主(重要度評分偏重應用價值);研究論文每日上限 2 篇(`MAX_PAPERS`)
- 每次更新至少 20 篇(`MIN_ITEMS`),不足時放寬過濾補足;單一來源最多 8 篇(`PER_SOURCE_CAP`)
- skills 的 id 必須存在於 skills.json,前端靠 id 對照顯示名稱
- 收藏功能存在瀏覽器 localStorage(key:`aiobs_saved`),換裝置不會同步
- **絕對不要**把 API 金鑰寫進任何會 commit 的檔案

## 設計系統(芫瑞造物誌風格:東方語彙、抽象幾何,避免俗套的復古元素)

- 色彩:瓷白 #F4F4EF / 墨 #21201C / 靛青 #33518F(互動)/ 硃砂 #BC4626(僅用於重要度印記)/ 燼灰 #8A877E
- 字體:Noto Serif TC(標題)/ Noto Sans TC(內文)/ IBM Plex Mono(日期、資料)
- 重要度與熟練度都用五格方塊呈現,不用星星
- 維持單檔 index.html,不引入框架或建置工具

## 常用指令

- 本機預覽:`python -m http.server` → http://localhost:8000
- 本機測試抓取:`$env:GEMINI_API_KEY="金鑰"; python scripts/fetch_news.py`(PowerShell)
- 部署:`git push` 即自動部署,約 1-2 分鐘生效

## 待開發(依優先序)

1. 每週日彙整「本週必知 5 件事」(新 workflow + weekly.json + 前端區塊)
2. 歷史存檔瀏覽頁(data/archive/ 已在累積,需要一個日期索引)
3. 新聞卡片一鍵加入技能 todo(靜態站限制:可考慮產生編輯 skills.json 的 GitHub 網頁連結)
