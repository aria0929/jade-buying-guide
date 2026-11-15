# -*- coding: utf-8 -*-
"""
一玉了然｜API 擷取（api_fetch.py）：用網站官方提供的 API 取資料 → 切塊 → 寫入 staging（等待人工審核）

兩個 API：
   • OpenAlex（https://openalex.org）：非營利組織經營的開放學術論文目錄，取翡翠相關論文的作者、期刊、年份、摘要（B 級學術資料）
      1. API 網址：https://api.openalex.org/works ，後面加查詢條件；官方文件：help.openalex.org
      2. 網頁版不一定顯示摘要，但 API 拿得到，所以用 API 取資料
      3. 目前不需要 API 金鑰（2026-11-02 實測）
   • 維基百科（zh.wikipedia.org）：取台灣正體版條目＋條目引用的原始出處網址
      → 只當找資料的線索、不直接引用；知識卡改引用條目列出的原始出處

用法：
    python api_fetch.py              兩個 API 都抓（已經抓過的網址會自動略過）
    python crawler.py --export       匯出待審核段落（爬蟲和 API 的結果一起匯出）
"""

import sqlite3
import time
from urllib.parse import quote
import requests
from crawler import DB, HEADERS, chunk, save

DELAY = 1

# OpenAlex：每組關鍵字搜「標題」含這些字的期刊論文（依七大分類各找幾篇）；要加主題就照格式往下加
OPENALEX_QUERIES = [
    ("認識翡翠", "翡翠 成因"),
    ("品質判斷", "翡翠 颜色"),
    ("品質判斷", "翡翠 种水"),
    ("真假處理", "翡翠 处理"),
    ("真假處理", "翡翠 鉴别"),
    ("證書鑑定", "翡翠 检测"),
    ("選購價格", "翡翠 价格"),
    ("配戴保養", "翡翠 保养"),
    ("認識翡翠", "jadeite jade"),
    ("選購價格", "和消费者谈翡翠"),
    # 《中國寶石》翡翠雕刻題材的寓意（2026-10-30 補寓意來源）
    ("款式寓意", "翡翠的文化灵魂"),
    # 《上海工藝美術》玉果佩、玉器的吉祥寓意
    ("款式寓意", "意必吉祥"),
]
OPENALEX_PER_QUERY = 5

# 維基百科：條目名稱（繁簡都可以，API 會自動轉成台灣正體）
WIKI_TITLES = ["翡翠", "硬玉", "玉"]

# %% 1. openalex_abstract() OpenAlex 的摘要存成「每個字出現在第幾個位置」，要照位置排回一句話

def openalex_abstract(inverted):
    if not inverted:
        return ""
    words = []
    for word, positions in inverted.items():
        for position in positions:
            words.append((position, word))
    words = sorted(words)
    word_list = []
    for position, word in words:
        word_list.append(word)
    text = " ".join(word_list)
    chinese = 0
    for char in text:
        if "一" <= char <= "鿿":
            chinese = chinese + 1
    if chinese > len(text) / 3:
        return text.replace(" ", "")
    return text

# %% 2. fetch_openalex() OpenAlex API

def fetch_openalex(jade_db, done):
    count = 0
    for i, (category, keywords) in enumerate(OPENALEX_QUERIES):
        if i > 0:
            time.sleep(DELAY)
        params = {
            "filter": f"title.search:{keywords},has_abstract:true,type:article",
            "sort": "relevance_score:desc",
            "per-page": OPENALEX_PER_QUERY,
            "select": "id,doi,title,publication_year,authorships,primary_location,abstract_inverted_index",
        }
        try:
            response = requests.get("https://api.openalex.org/works", params=params, headers=HEADERS, timeout=20)
            response.raise_for_status()
            works = response.json()["results"]
        except (requests.RequestException, KeyError, ValueError) as error:
            print(f"✗ OpenAlex「{keywords}」失敗：{error}")
            continue
        for work in works:
            url = work.get("doi")
            if not url:
                url = work["id"]
            if url in done:
                continue
            if "翡翠" not in work["title"] and "jade" not in work["title"].lower():
                continue

            # 作者最多取 5 位
            names = []
            for authorship in work.get("authorships", [])[:5]:
                names.append(authorship["author"]["display_name"])
            authors = "、".join(names)

            # 期刊名稱：部分論文沒有期刊資料，逐層檢查
            location = work.get("primary_location")
            if not location:
                location = {}
            source = location.get("source")
            if not source:
                source = {}
            journal = source.get("display_name")
            if not journal:
                journal = ""
            year = work.get("publication_year")
            if not year:
                year = ""
            year = str(year)
            parts = []
            for part in (journal, year):
                if part:
                    parts.append(part)
            citation = "，".join(parts)

            abstract = openalex_abstract(work.get("abstract_inverted_index"))
            chunks = chunk(["摘要：" + abstract])
            save(jade_db, url, work["title"], chunks, authors, citation, method="API（OpenAlex）")
            done.add(url)
            count = count + 1
            print(f"✓ [{category}] {work['title'][:40]}（{citation}）")
    print(f"OpenAlex：新增 {count} 篇論文摘要")

# %% 3. fetch_wiki() 維基百科 API（MediaWiki API）

def fetch_wiki(jade_db, done):
    count = 0
    for i, title in enumerate(WIKI_TITLES):
        if i > 0:
            time.sleep(DELAY)
        params = {
            "action": "query", "format": "json", "redirects": 1, "variant": "zh-tw",
            "prop": "extracts|extlinks", "explaintext": 1, "titles": title, "ellimit": "max",
        }
        try:
            response = requests.get("https://zh.wikipedia.org/w/api.php", params=params, headers=HEADERS, timeout=20)
            response.raise_for_status()
            pages = response.json()["query"]["pages"]
            page = list(pages.values())[0]
        except (requests.RequestException, KeyError, ValueError, IndexError) as error:
            print(f"✗ 維基百科「{title}」失敗：{error}")
            continue
        if "missing" in page:
            print(f"✗ 維基百科沒有「{title}」這個條目")
            continue
        url = "https://zh.wikipedia.org/zh-tw/" + quote(page["title"])
        if url in done:
            print(f"－ 「{title}」＝「{page['title']}」條目，已經抓過，略過")
            continue
        text = page.get("extract", "")
        for stop in ("\n== 參考文獻", "\n== 參考資料", "\n== 外部連結", "\n== 參見"):
            text = text.split(stop)[0]
        paragraphs = []
        for line in text.split("\n"):
            if len(line.strip()) >= 10 and not line.startswith("=="):
                paragraphs.append(line.strip())
        links = []
        for link in page.get("extlinks", []):
            if "wiki" not in link["*"]:
                links.append(link["*"])
        chunks = chunk(paragraphs)
        if links:
            chunks.append("原始出處線索（請改引用這些，不要引用維基百科）：\n" + "\n".join(links[:30]))
        save(jade_db, url, page["title"] + "（維基百科）", chunks, "維基百科編者",
             "中文維基百科（只當線索，不直接引用）", method="API（維基百科）")
        done.add(url)
        count = count + 1
        print(f"✓ {page['title']}：{len(chunks)} 段（含 {len(links)} 個原始出處網址）")
    print(f"維基百科：新增 {count} 個條目")

# %% 4. main() 執行入口：從 OpenAlex、維基百科抓資料，存進暫存區（staging）

def main():
    jade_db = sqlite3.connect(DB)
    try:
        done = set()
        for row in jade_db.execute("SELECT DISTINCT url FROM staging"):
            done.add(row[0])
        fetch_openalex(jade_db, done)
        fetch_wiki(jade_db, done)
        print("下一步：python crawler.py --export，人工審核後改寫進 jade_data")
    finally:
        jade_db.close()

# %% 執行入口：直接執行 python api_fetch.py 時才跑 main()（被別的程式 import 時不跑）

if __name__ == "__main__":
    main()
