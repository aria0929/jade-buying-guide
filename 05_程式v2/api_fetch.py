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

OPENALEX_URL = "https://api.openalex.org/works"
WIKI_URL = "https://zh.wikipedia.org/w/api.php"

# OpenAlex：(分類, 關鍵字)，搜尋標題含這些字的期刊論文；中國期刊的標題是簡體字，所以關鍵字用簡體
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
    # 《中國寶石》翡翠雕刻題材的寓意
    ("款式寓意", "翡翠的文化灵魂"),
    # 《上海工藝美術》玉果佩、玉器的吉祥寓意
    ("款式寓意", "意必吉祥"),
]
OPENALEX_PER_QUERY = 5

# 維基百科：條目名稱（繁簡都可以，API 會轉成台灣正體）
WIKI_TITLES = ["翡翠", "硬玉", "玉"]

# 維基百科條目從這些段落開始是參考資料，不屬於內文
WIKI_STOPS = ("\n== 參考文獻", "\n== 參考資料", "\n== 外部連結", "\n== 參見")

# %% 1. openalex_abstract() OpenAlex 的摘要是「詞 → 出現位置」的倒排索引，依位置排回原本的句子

def openalex_abstract(inverted):
    if not inverted:
        return ""

    # {"翡翠": [0, 4], "是": [1]} → [(0, "翡翠"), (1, "是"), (4, "翡翠")]
    words = []
    for word, positions in inverted.items():
        for position in positions:
            words.append((position, word))
    words = sorted(words)

    word_list = []
    for position, word in words:
        word_list.append(word)
    text = " ".join(word_list)

    # 中文字超過三分之一就視為中文摘要，去掉詞與詞之間的空白
    chinese = 0
    for char in text:
        if "一" <= char <= "鿿":  # 中文字的範圍（Unicode 4E00～9FFF）
            chinese = chinese + 1
    if chinese > len(text) / 3:
        return text.replace(" ", "")
    return text

# %% 2. get_or_empty() 讀取字典的欄位；沒有這個欄位或值是空的（None）時回傳 default

def get_or_empty(data, key, default):
    value = data.get(key)
    if not value:
        return default
    return value

# %% 3. openalex_citation() 組合出處文字，例：「寶石和寶石學雜誌，2004」

def openalex_citation(work):
    # 期刊名稱在 primary_location → source → display_name；部分論文缺少其中一層，所以逐層檢查
    location = get_or_empty(work, "primary_location", {})
    source = get_or_empty(location, "source", {})
    journal = get_or_empty(source, "display_name", "")
    year = str(get_or_empty(work, "publication_year", ""))

    parts = []
    for part in (journal, year):
        if part:
            parts.append(part)
    return "，".join(parts)

# %% 4. openalex_authors() 作者姓名，最多 5 位

def openalex_authors(work):
    names = []
    for authorship in work.get("authorships", [])[:5]:
        names.append(authorship["author"]["display_name"])
    return "、".join(names)

# %% 5. fetch_openalex() 依 OPENALEX_QUERIES 逐組查詢論文，存進 staging

def fetch_openalex(jade_db, done):
    count = 0
    for i, (category, keywords) in enumerate(OPENALEX_QUERIES):
        if i > 0:
            time.sleep(DELAY)                   # 每次請求間隔，避免造成 API 負擔
        params = {
            "filter": f"title.search:{keywords},has_abstract:true,type:article",
            "sort": "relevance_score:desc",
            "per-page": OPENALEX_PER_QUERY,
            "select": "id,doi,title,publication_year,authorships,primary_location,abstract_inverted_index",
        }
        try:
            response = requests.get(OPENALEX_URL, params=params, headers=HEADERS, timeout=20)
            response.raise_for_status()
            works = response.json()["results"]
        except (requests.RequestException, KeyError, ValueError) as error:
            print(f"✗ OpenAlex「{keywords}」失敗：{error}")
            continue                            # 這組失敗就換下一組，不中斷整個程式

        for work in works:
            # 優先用 DOI（論文的永久識別碼）當網址，沒有才用 OpenAlex 編號
            url = work.get("doi")
            if not url:
                url = work["id"]
            if url in done:
                continue

            # 搜尋結果偶爾不相關：標題沒有提到翡翠就略過
            if "翡翠" not in work["title"] and "jade" not in work["title"].lower():
                continue

            authors = openalex_authors(work)
            citation = openalex_citation(work)
            abstract = openalex_abstract(work.get("abstract_inverted_index"))

            chunks = chunk(["摘要：" + abstract])
            save(jade_db, url, work["title"], chunks, authors, citation, method="API（OpenAlex）")
            done.add(url)
            count = count + 1
            print(f"✓ [{category}] {work['title'][:40]}（{citation}）")
    print(f"OpenAlex：新增 {count} 篇論文摘要")

# %% 6. wiki_paragraphs() 維基百科條目內文：去掉參考資料段落與標題列，保留 10 個字以上的段落

def wiki_paragraphs(text):
    for stop in WIKI_STOPS:
        text = text.split(stop)[0]

    paragraphs = []
    for line in text.split("\n"):
        if len(line.strip()) >= 10 and not line.startswith("=="):
            paragraphs.append(line.strip())
    return paragraphs

# %% 7. wiki_links() 條目引用的外部網址（原始出處），排除維基相關連結

def wiki_links(page):
    links = []
    for link in page.get("extlinks", []):
        if "wiki" not in link["*"]:
            links.append(link["*"])
    return links

# %% 8. fetch_wiki() 依 WIKI_TITLES 逐條查詢維基百科，存進 staging

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
            response = requests.get(WIKI_URL, params=params, headers=HEADERS, timeout=20)
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

        chunks = chunk(wiki_paragraphs(page.get("extract", "")))
        links = wiki_links(page)
        if links:
            chunks.append("原始出處線索（請改引用這些，不要引用維基百科）：\n" + "\n".join(links[:30]))
        save(jade_db, url, page["title"] + "（維基百科）", chunks, "維基百科編者",
             "中文維基百科（只當線索，不直接引用）", method="API（維基百科）")
        done.add(url)
        count = count + 1
        print(f"✓ {page['title']}：{len(chunks)} 段（含 {len(links)} 個原始出處網址）")
    print(f"維基百科：新增 {count} 個條目")

# %% 9. main() 從 OpenAlex、維基百科抓資料，存進暫存區（staging）

def main():
    jade_db = sqlite3.connect(DB)
    try:
        # 已經在 staging 的網址不重複抓
        done = set()
        for row in jade_db.execute("SELECT DISTINCT url FROM staging"):
            done.add(row[0])

        fetch_openalex(jade_db, done)
        fetch_wiki(jade_db, done)
        print("下一步：python crawler.py --export，人工審核後改寫進 jade_data")
    finally:
        jade_db.close()

# %% 執行入口：直接執行 python api_fetch.py 時才執行 main()（被其他程式 import 時不執行）

if __name__ == "__main__":
    main()
