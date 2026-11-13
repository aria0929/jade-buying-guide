<h1 align="center">一玉了然｜翡翠選購指南</h1>
<br>

## 【 製作動機 】

- 翡翠買賣資訊不透明，網路上的說法真假難辨，新手常不知道該問什麼、該相信誰。
- 這是一個給翡翠新手的知識查詢網站。把散落在網路上的翡翠知識整理成 69 張知識卡，每個答案都附上參考資料與可信度等級，並依預算、品項、用途提供選款建議。
- 這個網站的回答**全部來自人工審核過的知識卡，並標明出處**；知識庫沒有的問題就直接回答查無資料，不自己編答案。
<br>

## 【 功能 】
<br>
<div align="center">
        
| 分頁 | 做什麼 |
|---|---|
| 新手入門 | 整理翡翠基礎：種、水、色、底、工五個關鍵字、常見迷思、挑選步驟 |
| 知識搜尋 | 用一般人的說法也查得到（例：「灌膠」→ B 貨）；問範圍外的問題（例：鑽石）會回答查無資料 |
| 主題瀏覽 | 依七大主題瀏覽所有知識卡 |
| 選款建議 | 選擇預算、品項、用途，提供款式建議與選購提醒 |
| 避坑清單 | 付款前逐項打勾確認 |
</div>
<br>

 每張知識卡都列出參考資料與來源等級（每張卡至少要有 1 個 A 或 B 級來源，由 `build_db.py` 建資料庫時自動檢查）：

- **A 級**：官方標準、國家級檢驗機構。
- **B 級**：鑑定機構、學術期刊、珠寶公會。
- **C 級**：品牌店家文章（只能當補充）。
  
<br>

## 【 成果 】
<br>
<div align="center">
        
| 項目 | 數量 |
|---|---|
| 知識卡 | 69 張 |
| 參考來源 | 68 筆 |
| 同義詞（使用者說法 → 標準詞） | 452 組 |
| 選款規則／選款提醒 | 30 條／33 句 |
| 測試題 | 72 題（含口語說法與範圍外問題） |
</div>
<br>

## 【 資料來源 】

```
公開網站（爬蟲）、OpenAlex 與維基百科（API）
        ↓ 存進暫存區 staging，等待人工審核
人工審核、改寫成知識卡（01_知識庫/jade_data.numbers）
        ↓ build_db.py 檢查資料並建立資料庫
jade.db（SQLite）
        ↓ search.py 搜尋／recommend.py 選款
網站 app.py（Streamlit）
```

- 爬蟲先檢查各網站的 robots.txt，只抓允許的公開頁面（檢查結果：`03_輸出結果/網站檢查結果.csv`）。
- 抓到的原文不會直接上網站，一律人工審核後用自己的話改寫。
- 本專案的資料庫已清空暫存區的原文，只保留審核後的知識卡。
<br>

## 【 技術 】
<br>
<div align="center">
        
| 用途 | 使用技術 |
|---|---|
| 資料擷取 | requests、BeautifulSoup、正規表示式、OpenAlex API、MediaWiki API |
| 資料處理 | pandas（必填、格式、來源等級等驗證） |
| 資料庫 | SQLite、FTS5 全文檢索（trigram 分詞） |
| 搜尋 | 同義詞展開 → 關鍵詞比對（LIKE）＋全文檢索 → 依命中詞數與 bm25 分數排序 |
| 網站 | Streamlit（部署於 Streamlit Community Cloud） |
| 測試 | 自動小考 quiz.py、matplotlib 畫答對率圖 |
</div>
<br>

## 【 本機執行 】

```bash
pip install -r requirements.txt
cd 05_程式
streamlit run app.py        # 開網站，瀏覽器打開 http://localhost:8501
python quiz.py              # 跑小考
```

- 修改知識庫後重建資料庫（需另外安裝讀取 Numbers 檔的套件）：

```bash
pip install numbers-parser
python build_db.py          # 檢查 01_知識庫/jade_data.numbers 並重建 jade.db
```

- 重新抓取資料（需要網路，結果寫入 staging 等待審核）：

```bash
python crawler.py           # 爬蟲
python api_fetch.py         # API
python crawler.py --export  # 匯出待審核段落
```

- 部署到 Streamlit Community Cloud 時，Main file path 填 `05_程式/app.py`。
<br>

## 【 資料夾 】

```
├─ 01_知識庫/       jade_data.numbers：知識庫原始資料（人工填寫、審核）
├─ 02_測試題/       test_questions.xlsx：小考測試題
├─ 03_輸出結果/     小考成績、答對率圖、各網站 robots.txt 檢查結果
├─ 04_參考文件/     資料字典、架構圖、審核紀錄
├─ 05_程式/
│  ├─ app.py                     網站
│  ├─ search.py                  知識搜尋
│  ├─ recommend.py               選款建議
│  ├─ build_db.py                檢查資料、建立資料庫
│  ├─ read_sheets.py             讀取 Numbers／Excel
│  ├─ crawler.py、api_fetch.py   爬蟲與 API
│  ├─ quiz.py                    小考
│  ├─ jade.db                    資料庫
│  └─ images/                    知識卡配圖（出處與授權見 圖片來源.csv）
└─ requirements.txt
```
<br>

## 【 圖片與資料來源 】

- 知識卡配圖多為作者自行拍攝；其餘來自維基共享資源等開放授權（CC0、CC BY、CC BY-SA），作者與授權列在 `05_程式/images/圖片來源.csv`。
- 知識內容由作者閱讀參考資料後改寫，原始出處列在每張知識卡下方。
<br>

## 【 聲明 】

- 僅供知識查詢與選購參考，不做鑑定、估價或投資建議；實際交易請以專業機構鑑定為準。
