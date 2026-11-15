# -*- coding: utf-8 -*-
"""
一玉了然｜爬蟲（crawler.py）：抓取 → 清洗 → 切塊 → 寫入 staging（等待人工審核）

守則：
    • 只抓 robots.txt 允許的公開頁面，每次請求間隔 2 秒
    • 有官方 API 的網站（OpenAlex 論文、維基百科）改用 api_fetch.py，結果寫進同一個 staging
    • 爬下來的內容「不會」直接上網站：人工看過、用自己的話改寫後，
      填進 jade_data（草稿 → 已審核），再執行 build_db.py 才會入庫

用法：
    python crawler.py                    抓下面 URLS 清單裡的網址
    python crawler.py https://...        只抓指定網址
    python crawler.py --export           把待審核段落（含 api_fetch.py 抓的）匯出成 03_輸出結果/staging_待審核.xlsx
"""

import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
DB = HERE / "jade.db"
REPORTS = HERE.parent / "03_輸出結果"

# 要抓的知識型公開頁面（2026-10-29 實測可抓取）；新增網址照格式往下加
URLS = [
    # 《寶石和寶石學雜誌》論文摘要（B）
    "https://jogg.cug.edu.cn/cn/article/id/f5642d34-0d1f-4d14-b741-782e35a112f3",
    # 翡翠結構類型及其成因意義
    "https://jogg.cug.edu.cn/cn/article/id/bed97f88-7988-4d65-ac1a-6300b725c627",
    # GIA 美國寶石學院（B，英文）
    "https://www.gia.edu/jade/buyers-guide",
    "https://www.gia.edu/jade-quality-factor",
    "https://www.gia.edu/jade-history-lore",
    "https://www.gia.edu/jade-care-cleaning",
    # 官方檢驗機構、珠寶公會（2026-10-30 從 KATHY JADE 參考資料清單找到）
    "https://www.ngtc.com.cn/hudong/piyao/65111.html",
    # NGTC：翡翠的五字鑑真法（A）
    "https://www.ngtc.com.cn/jiance/zhubao/67542.html",
    # 香港玉器商會：翡翠玉石知識（B）
    "https://hkja.com.hk/%E7%BF%A1%E7%BF%A0%E7%8E%89%E7%9F%B3%E7%9F%A5%E8%AD%98/",
    # 台灣鑑定所（B，2026-10-30 實測）：香港寶石鑑定所台北（歐陽秋眉教授創辦）消費者相關文章、TGI 鑑定流程
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-202511",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-02",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-03",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-05",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-14",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-13",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-12",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-10",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-38",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-37",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-39",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-40",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-41",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-003",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-04",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-jade-003",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-48",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-0049",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-01",
    "https://gemstw.com.tw/Jewelry-knowledge/jude-Jadeite-006",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-jadecut-007",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-008",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-35",
    "https://gemstw.com.tw/Jewelry-knowledge/Jadeite-36",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-051",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-049",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-28",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-16",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-20260605",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-32",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-65",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-20257",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-20258",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-56",
    "https://gemstw.com.tw/Jewelry-knowledge/Jadeite-31",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-20251",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-20252",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-20253",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-20254",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-20255",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-20256",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-20259",
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-202510",
    # 何謂明貨＆半明半暗貨（賭石，2026-10-30 補）
    "https://gemstw.com.tw/Jewelry-knowledge/jadeite-23",
    # TGI 鑑定流程（證書查詢提醒）
    "https://www.fga-dga-tgi.com.tw/identification.php?id=5",
    # 台灣翡翠店家（C，2026-10-30 實測）：消費者實用知識，只當補充，要搭配 A／B 級來源
    "https://www.kathyjade.com/knowledge",
    # KATHY JADE 翡翠入門知識
    "https://www.kathyjade.com/knowledge/basic",
    # KATHY JADE 翡翠手鐲指南
    "https://www.kathyjade.com/knowledge/bangle",
    # KATHY JADE 翡翠種水與品質
    "https://www.kathyjade.com/knowledge/Jadequality",
    # KATHY JADE 翡翠價格指南
    "https://www.kathyjade.com/knowledge/jadeite_price_market",
    # KATHY JADE 翡翠真假與鑑定
    "https://www.kathyjade.com/knowledge/tureorfake",
    # 東方翡翠寶石：如何測量手鐲手圍
    "https://www.eastgem.com.tw/index.php/fqa/detail/id/12",
    # 磨樣 MODEYANG：新手怎麼挑手鐲
    "https://www.modeyang.com/blogs/jewelrystory/%E6%96%B0%E6%89%8B%E5%B0%8F%E7%99%BD%E6%80%8E%E9%BA%BC%E6%8C%91%E6%89%8B%E9%90%B2-%E8%B3%BC%E8%B2%B7%E6%89%8B%E9%90%B2%E6%82%A8%E4%B8%80%E5%AE%9A%E8%A6%81%E7%9F%A5%E9%81%93%E7%9A%84%E5%B0%8F%E6%8A%80%E5%B7%A7",
]
HEADERS = {"User-Agent": "YiYuLiaoRan-StudentProject/1.0 (educational use)"}
DELAY = 2
MIN_LEN = 300
MAX_LEN = 500

# 網站 → (來源機構, 等級, 「來源」表的類型建議)；匯出時自動帶出，填「來源」表時照抄
SOURCE_INFO = {
    "jogg.cug.edu.cn": ("《寶石和寶石學雜誌》（中國地質大學）", "B", "學術資料"),
    "www.gia.edu": ("GIA 美國寶石學院", "B", "鑑定機構"),
    "www.samr.gov.cn": ("國家市場監督管理總局", "A", "官方機構"),
    "std.samr.gov.cn": ("全國標準信息公共服務平台", "A", "官方機構"),
    "www.ngtc.com.cn": ("國家珠寶玉石首飾檢驗集團（NGTC）", "A", "官方機構"),
    "www.gtc-china.cn": ("廣東省珠寶玉石及貴金屬檢測中心（GTC）", "B", "鑑定機構"),
    "www.ttbz.org.cn": ("全國團體標準信息平台", "B", "珠寶公會"),
    "zh.wikipedia.org": ("中文維基百科", "—", "不直接引用：改引用條目裡的原始出處"),
    "gemstw.com.tw": ("香港寶石鑑定所－台北（歐陽秋眉教授創辦）", "B", "鑑定機構"),
    "www.fga-dga-tgi.com.tw": ("TGI 台灣寶石學院暨鑑定所", "B", "鑑定機構"),
    "hkja.com.hk": ("香港玉器商會", "B", "珠寶公會"),
    "www.kathyjade.com": ("KATHY JADE（台灣翡翠品牌）", "C", "品牌或鑑定師"),
    "www.eastgem.com.tw": ("東方翡翠寶石專賣店（台灣）", "C", "品牌或鑑定師"),
    "www.modeyang.com": ("磨樣 MODEYANG（台灣翡翠品牌）", "C", "品牌或鑑定師"),
    "doi.org": ("學術論文（OpenAlex API；期刊名見出處欄）", "B", "學術資料"),
    "openalex.org": ("學術論文（OpenAlex API；期刊名見出處欄）", "B", "學術資料"),
}

# %% 1. allowed() 守規矩：robots.txt

def allowed(url):
    # robots.txt 固定放在網站根目錄
    parts = urlparse(url)
    try:
        response = requests.get(f"{parts.scheme}://{parts.netloc}/robots.txt", headers=HEADERS, timeout=15)
    except requests.RequestException:
        return False
    if response.status_code in (404, 410):
        return True
    if response.status_code != 200:
        return False
    rules = robotparser.RobotFileParser()
    rules.parse(response.text.splitlines())
    return rules.can_fetch(HEADERS["User-Agent"], url)

# %% 2. fetch() 抓取：下載網頁原始碼（HTML）

def fetch(url):
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    try:
        return response.content.decode("utf-8")
    except UnicodeDecodeError:
        response.encoding = response.apparent_encoding
        return response.text


# 遇到這些標題就停止：後面是推薦文章、參考文獻等，跟本文無關
STOP_MARKERS = re.compile(r"^(You Might Also Like|This Month.s|Featured Gems|Related|相關文章|相关文章|參考文獻|参考文献|引用本文|相似文獻|相似文献)", re.I)

# %% 3. link_ratio() 區塊裡「連結文字」占多少；選單、導覽列、作者連結幾乎都是連結

def link_ratio(element):
    total = len(element.get_text(strip=True))
    if total == 0:
        total = 1
    link_total = 0
    for link in element.find_all("a"):
        link_total = link_total + len(link.get_text(strip=True))
    return link_total / total

# %% 4. clean_html() 清洗：把網頁變成乾淨的段落

def clean_html(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "select", "option"]):
        tag.decompose()
    title = ""
    if soup.title:
        title = soup.title.get_text(strip=True)

    # 正文在哪裡：先找 <main>，沒有就找 <article>，再沒有就用整個 <body>
    body = soup.find("main")
    if not body:
        body = soup.find("article")
    if not body:
        body = soup.body
    if not body:
        body = soup

    paragraphs = []
    seen = set()
    for element in body.find_all(["p", "li", "h2", "h3", "td"]):
        text = re.sub(r"\s+", " ", element.get_text(" ", strip=True))
        if STOP_MARKERS.match(text):
            break
        if link_ratio(element) > 0.6:
            continue
        text = re.sub(r"(分享|列印|回上頁|Copyright.*)$", "", text).strip()
        inside = False
        for paragraph in paragraphs:
            if text in paragraph:
                inside = True
        if len(text) >= 10 and text not in seen and not inside:
            seen.add(text)
            paragraphs.append(text)
    return title, paragraphs

# %% 5. journal_abstract() 期刊網頁的 <meta> 標籤會記錄標題、作者、摘要（給學術搜尋引擎看的），直接讀這裡最乾淨

def journal_abstract(html):
    soup = BeautifulSoup(html, "html.parser")
    if not soup.find("meta", attrs={"name": "citation_journal_title"}):
        return None

    # get_meta() 讀某一個 <meta> 的內容；沒有就回傳空字串
    def get_meta(name):
        tag = soup.find("meta", attrs={"name": name})
        if not tag:
            return ""
        return re.sub(r"\s+", " ", tag.get("content", "")).strip()

    abstract = get_meta("dc.description")
    if not abstract:
        abstract = get_meta("citation_abstract")
    if not abstract:
        return None

    raw_keywords = get_meta("dc.keywords")
    if not raw_keywords:
        raw_keywords = get_meta("citation_keywords")
    for separator in ["，", ";", "；"]:
        raw_keywords = raw_keywords.replace(separator, ",")
    keyword_list = []
    for keyword in raw_keywords.split(","):
        if keyword.strip():
            keyword_list.append(keyword.strip())
    keywords = "、".join(keyword_list)

    result = ["摘要：" + abstract]
    if keywords:
        result.append("關鍵詞：" + keywords)
    return result

# %% 6. page_meta() 從網頁的 <meta> 讀作者與出處（期刊論文多半有；沒有就回傳空字串）

def page_meta(html):
    soup = BeautifulSoup(html, "html.parser")

    # get_metas() 找出名稱在 names 清單裡的所有 <meta>，回傳它們的內容
    def get_metas(names):
        contents = []
        for tag in soup.find_all("meta"):
            name = tag.get("name")
            if not name:
                name = ""
            content = tag.get("content", "").strip()
            if name.lower() in names and content:
                contents.append(content)
        return contents

    # 作者（重複的只留一個，順序不變）
    authors = []
    for author in get_metas(["dc.creator", "citation_author"]):
        if author not in authors:
            authors.append(author)
    if not authors:
        all_authors = ",".join(get_metas(["citation_authors"]))
        for author in all_authors.split(","):
            if author.strip():
                authors.append(author.strip())

    # 出處：先找 dc.source，沒有再找期刊名稱
    citation = ""
    sources = get_metas(["dc.source"])
    if not sources:
        sources = get_metas(["citation_journal_title"])
    if sources:
        citation = sources[0]
    return "、".join(authors), re.sub(r"\s+", " ", citation)

# %% 7. split_sentences() 把一段文字切成一句一句：中文的「。！？」後面斷開；英文的「.!?」後面有空白才斷開（空白丟掉）

def split_sentences(text):
    sentences = []
    current = ""
    i = 0
    while i < len(text):
        char = text[i]
        current = current + char
        i = i + 1
        if char in "。！？":
            sentences.append(current)
            current = ""
        elif char in ".!?":
            j = i
            while j < len(text) and text[j].isspace():
                j = j + 1
            if j > i:
                sentences.append(current)
                current = ""
                i = j
    sentences.append(current)
    return sentences

# %% 8. ends_with_period() 這句是不是用中文句號（。！？）結尾（最後一個換行不算）

def ends_with_period(text):
    if text.endswith("\n"):
        text = text[:-1]
    return text != "" and text[-1] in "。！？"

# %% 9. tidy_spaces() 去掉多餘空白：連續空白變一個、換行前面的空白和 Tab 拿掉

def tidy_spaces(text):
    while "  " in text:
        text = text.replace("  ", " ")
    while " \n" in text or "\t\n" in text:
        text = text.replace(" \n", "\n").replace("\t\n", "\n")
    return text.strip()

# %% 10. chunk() 切塊：把長文章切成 300–500 字一段

def chunk(paragraphs):
    chunks = []
    buffer = ""
    for paragraph in paragraphs:
        for sentence in split_sentences(paragraph):
            if sentence and not ends_with_period(sentence):
                sentence = sentence + " "
            if len(buffer) + len(sentence) > MAX_LEN and len(buffer) >= MIN_LEN:
                chunks.append(buffer)
                buffer = ""
            buffer += sentence
        buffer += "\n"
    if buffer.strip():
        chunks.append(buffer.strip())
    result = []
    for text in chunks:
        result.append(tidy_spaces(text))
    return result

# %% 11. save() 存檔：寫進資料庫的 staging 表（狀態＝pending 等待審核）

def save(jade_db, url, title, chunks, authors="", citation="", method="爬蟲"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for text in chunks:
        rows.append((url, title, text, now, authors, citation, method))
    jade_db.executemany("INSERT INTO staging (url, title, content, fetched_at, status, authors, citation, method) "
                    "VALUES (?,?,?,?, 'pending',?,?,?)", rows)
    jade_db.commit()

# %% 12. source_info() 網址 → (來源機構, 等級, 類型)；SOURCE_INFO 沒有的網站就請自己查

def source_info(url):
    site = urlparse(url).netloc
    return SOURCE_INFO.get(site, ("（請自己查是哪個機構）", "", ""))

# %% 13. export() 匯出：把 pending 的段落輸出成 Excel（Numbers 也能開），方便人工審核

def export(jade_db):
    staging = pd.read_sql("SELECT id, url, title, authors, citation, fetched_at, summary_zh, content, method "
                          "FROM staging WHERE status = 'pending'", jade_db)
    info = staging["url"].map(source_info)
    out_table = pd.DataFrame({
        "編號": staging["id"],
        "取得方式": staging["method"].fillna("爬蟲"),
        "來源機構": info.str[0],
        "作者": staging["authors"].fillna(""),
        "出處（期刊、年份、卷期）": staging["citation"].fillna(""),
        "文章標題": staging["title"],
        "網址": staging["url"],
        "存取日期": staging["fetched_at"].str[:10],
        "等級": info.str[1],
        "「來源」表類型選": info.str[2],
        "中文翻譯（精簡）": staging["summary_zh"].fillna(""),
        "內容": staging["content"],
    })
    out = REPORTS / "staging_待審核.xlsx"
    out_table.to_excel(out, index=False)
    print(f"✓ 匯出 {len(out_table)} 段待審核內容到 {REPORTS.name}/{out.name}（每段都有來源機構、作者、網址）")

# %% 14. main() 主流程：每個網址 → 檢查 robots.txt → 抓取 → 清洗 → 切塊 → 存 staging

def main():
    jade_db = sqlite3.connect(DB)
    try:
        if "--export" in sys.argv:
            export(jade_db)
            return
        urls = []
        for argument in sys.argv[1:]:
            if argument.startswith("http"):
                urls.append(argument)
        if not urls:
            urls = URLS
        for i, url in enumerate(urls):
            if i > 0:
                time.sleep(DELAY)
            if not allowed(url):
                print(f"✗ 跳過（robots.txt 不允許或讀不到）：{url}")
                continue
            try:
                html = fetch(url)
                title, paragraphs = clean_html(html)
                abstract = journal_abstract(html)
                if abstract:
                    paragraphs = abstract
                authors, citation = page_meta(html)
            except requests.RequestException as error:
                print(f"✗ 抓取失敗：{url}（{error}）")
                continue
            chunks = chunk(paragraphs)
            save(jade_db, url, title, chunks, authors, citation)
            name = title
            if not name:
                name = url
            print(f"✓ {name}：{len(chunks)} 段寫入 staging（pending）")
        print("下一步：python crawler.py --export，人工審核後改寫進 jade_data")
    finally:
        jade_db.close()

# %% 執行入口：直接執行 python crawler.py 時才跑 main()（被別的程式 import 時不跑）

if __name__ == "__main__":
    main()
