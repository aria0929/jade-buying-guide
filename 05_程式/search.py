# -*- coding: utf-8 -*-
"""
一玉了然｜知識檢索（search.py）

流程：
    1. 問句清理：去掉標點與空白；空白輸入回傳提示
    2. 同義詞展開：灌膠 → B貨、鐲子 → 手鐲
    3. 關鍵詞比對（LIKE）：處理「冰種」這類 2 個字的短詞
    4. FTS5 全文檢索：trigram 分詞，處理 3 個字以上的詞
    5. 排序：先比命中關鍵詞數，再比 bm25 分數
    6. 範圍外判斷＋查無結果：問到鑽石等非翡翠問題、或沒有命中時回傳查無資料

四種模式（開發時用來比較每一步改進的效果，也就是「改進歷程」；網站和小考都用 hybrid）：
    like   ：只用 LIKE，不展開同義詞
    fts    ：只用 FTS5（2 個字的詞會抓不到），不展開同義詞
    mix    ：同義詞＋LIKE＋FTS5，還沒有範圍外判斷
    hybrid ：mix＋範圍外判斷（網站用這個）

單獨測試：在 Spyder 按 F5，再到 Console 輸入 search("灌膠的翡翠能買嗎", connect())
"""

import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

# ── 基本設定 ──
HERE = Path(__file__).resolve().parent
DB = HERE / "jade.db"

# 範圍外的詞：問句有這些詞、又沒有提到翡翠，就判定「不是翡翠問題」，回答查無資料
NOT_JADE = ["鑽石", "珍珠", "黃金", "K金", "白金", "和田玉", "水晶", "紅寶石", "藍寶石",
            "琥珀", "珊瑚", "蜜蠟", "銀飾", "手錶"]

# 只要問句裡有這些字，就算有提到鑽石也當作翡翠問題（例如「翡翠和鑽石哪個貴」）
JADE = ["翡翠", "玉", "貨"]

# 七大分類，照新手學習的順序排（要和 jade_data「選項」表一致）
CATEGORIES = ["認識翡翠", "品質判斷", "真假處理", "證書鑑定", "選購價格", "款式寓意", "配戴保養"]

# 要去掉的中英文標點
SYMBOL = "，。、！？；：「」『』（）()《》〈〉,.!?;:'\"…～~·-—_/\\|｜"

# %% 1. connect() 連線到資料庫

def connect():
    # Streamlit 會跨執行緒共用連線，關閉同執行緒檢查
    jade_db = sqlite3.connect(DB, check_same_thread=False)
    jade_db.row_factory = sqlite3.Row
    return jade_db

# %% 2. clean_text() 全形轉半形、去掉標點與空白、英文轉大寫

def clean_text(text):
    half = unicodedata.normalize("NFKC", text)

    result = ""
    for char in half:
        if char.isspace():
            continue
        if char in SYMBOL:
            continue
        result = result + char

    result = result.upper()
    return result

# %% 3. get_words() 詞庫＝知識卡關鍵字＋同義詞（使用者說法與標準詞）

def get_words(jade_db):
    words = set()

    rows = jade_db.execute("SELECT keywords FROM knowledge WHERE status = '已審核'")
    for row in rows:
        keywords = row[0]
        for keyword in keywords.split("、"):
            words.add(clean_text(keyword))

    # {使用者說法: 標準詞}
    synonyms = {}
    rows = jade_db.execute("SELECT term, canonical FROM synonyms")
    for row in rows:
        term = clean_text(row[0])
        standard = clean_text(row[1])
        synonyms[term] = standard

    for term in synonyms:
        words.add(term)
    for standard in synonyms.values():
        words.add(standard)

    # 沒填關鍵字的卡會產生空字串
    words.discard("")
    return words, synonyms

# %% 4. find_terms() 找出問句裡出現的詞庫詞；長詞優先，被長詞包住的短詞不重複算

def find_terms(question, words):

    found = []
    for word in words:
        if word not in question:
            continue
        if len(word) == 1 and question != word:
            continue
        found.append(word)
    found = sorted(found, key=len, reverse=True)

    # 長詞先選；被已選的長詞包住的短詞就不要（例如「手鐲」被「翡翠手鐲」包住）
    terms = []
    for word in found:
        inside = False
        for longer in terms:
            if word in longer:
                inside = True
                break
        if not inside:
            terms.append(word)

    # 問句很短（2～4 個字）又不在詞庫：直接拿整句去找
    if len(terms) == 0 and len(question) >= 2 and len(question) <= 4:
        terms = [question]
    return terms

# %% 5. expand_synonyms() 同義詞展開：把使用者說法換成標準詞一起搜尋，例如「灌膠」→ 再加上「B貨」

def expand_synonyms(terms, synonyms):
    all_terms = list(terms)
    for term in terms:
        standard = synonyms.get(term)
        if standard and standard not in all_terms:
            all_terms.append(standard)
    return all_terms


# 問句有其他詞 → 只用其他詞找；問句只剩「翡翠」（例如「翡翠是什麼」）→ 才用翡翠找；
COMMON_WORDS = {"翡翠", "玉", "玉石"}

# %% 6. drop_common() 拿掉「翡翠、玉」這種普通詞，只留有用的詞，例：「翡翠灌膠」→ 只留「灌膠」去搜尋

def drop_common(question, terms):

    specific = []
    for term in terms:
        if term not in COMMON_WORDS:
            specific.append(term)
    if specific:
        return specific

    # 分辨是「真的在問翡翠」還是「問了知識庫沒有的東西」
    remove_words = sorted(COMMON_WORDS, key=len, reverse=True)
    remove_words = remove_words + ["是什麼", "什麼", "介紹", "是", "嗎", "呢", "的"]


    # 刪掉普通詞與虛詞，看還剩什麼
    rest = question
    for word in remove_words:
        rest = rest.replace(word, "")

    # 判斷結果：什麼都不剩 → 真的只是在問翡翠（翡翠是什麼）→ 正常搜尋
    if not rest:
        return terms

    # 還剩別的字 → 問了知識庫沒有的（翡翠要開光嗎 → 剩「要開光」）→ 查無資料
    return []

# %% 7. isnt_jade() 範圍外判斷：有範圍外的詞（鑽石…）而且沒有翡翠相關字 → True

def isnt_jade(question):
    has_other = False
    for word in NOT_JADE:
        if word in question:
            has_other = True

    has_jade = False
    for word in JADE:
        if word in question:
            has_jade = True

    return has_other and not has_jade

# %% 8. _like() LIKE 只比對「問題＋關鍵字」：答案裡順帶提到的詞不算，避免結果太雜

def _like(jade_db, term):
    pattern = f"%{term}%"

    rows = jade_db.execute(
        "SELECT id FROM knowledge WHERE status = '已審核' AND "
        "(UPPER(REPLACE(question,' ','')) LIKE ? OR UPPER(keywords) LIKE ?)", (pattern, pattern))

    found = {}
    for row in rows:
        found[row["id"]] = 0.0
    return found

# %% 9. _fts() FTS5 全文檢索：SQLite 內建的搜尋引擎，trigram ＝ 每 3 個字切一段建索引，中文沒有空白也能搜

def _fts(jade_db, term):

    # trigram 至少要 3 個字，較短的詞交給 LIKE
    if len(term) < 3:
        return {}

    # 前後加雙引號＝照字面找，不要把 + - 當指令（B+C貨 沒引號會找不到）
    phrase = '"' + term.replace('"', "") + '"'

    # bm25 是相關度分數：數字越小（越負）越相關
    rows = jade_db.execute(
        "SELECT f.id, bm25(knowledge_fts) AS score FROM knowledge_fts f "
        "JOIN knowledge k ON k.id = f.id WHERE knowledge_fts MATCH ? AND k.status = '已審核'",
        (phrase,))
    found = {}
    for row in rows:
        found[row["id"]] = row["score"]
    return found

# %% 10. get_cards() 依編號取出知識卡，附上參考資料（JOIN sources）

def get_cards(jade_db, card_ids):
    cards = []

    for card_id in card_ids:
        card = jade_db.execute("SELECT * FROM knowledge WHERE id = ?", (card_id,)).fetchone()

        # 找這張卡的參考資料（JOIN）
        rows = jade_db.execute(
            "SELECT s.* FROM knowledge_sources ks JOIN sources s ON s.id = ks.source_id "
            "WHERE ks.knowledge_id = ? ORDER BY s.level, s.id", (card_id,)).fetchall()

        sources = []
        for row in rows:
            sources.append(dict(row))

        cards.append({
            "id": card["id"], "category": card["category"], "question": card["question"],
            "answer": card["answer"], "caution": card["caution"], "keywords": card["keywords"],
            "hot": bool(card["hot"]), "sources": sources,
        })
    return cards

# %% 11. pick_terms() 從句子挑出關鍵詞 → 補同義詞 → 刪常見詞，例：「手鐲有沒有灌過膠」→ [灌過膠, 手鐲, B貨]

def pick_terms(jade_db, question, mode):
    words, synonyms = get_words(jade_db)
    terms = find_terms(question, words)

    if mode == "mix" or mode == "hybrid":
        terms = expand_synonyms(terms, synonyms)
    if mode == "hybrid":
        terms = drop_common(question, terms)
    return terms

# %% 12. score_cards() 每個詞去找卡，邊找邊記分，例：[手鐲, B貨] → 手鐲找到 K049…、B貨找到 K028…

def score_cards(jade_db, terms, mode):
    hits = {}
    best = {}

    for term in terms:
        if mode == "like":
            found = _like(jade_db, term)
        elif mode == "fts":
            found = _fts(jade_db, term)
        else:
            found = _like(jade_db, term)
            if len(term) > 2:
                found.update(_fts(jade_db, term))

        for card_id, score in found.items():
            hits[card_id] = hits.get(card_id, 0) + 1
            best[card_id] = min(best.get(card_id, 0.0), score)

    return hits, best

# %% 13. search() 搜尋主程式（網站和 quiz.py 都呼叫這個函式），例：search("灌膠的翡翠能買嗎", jade_db)

def search(text, jade_db, mode="hybrid"):

    # 先擋掉不用找的情況
    question = clean_text(text)
    if mode == "hybrid" and isnt_jade(question):
        return {"status": "NOT_JADE", "terms": [], "results": []}

    terms = pick_terms(jade_db, question, mode)

    hits, best = score_cards(jade_db, terms, mode)
    if not hits:
        return {"status": "no_result", "terms": terms, "results": []}

    # 排序：命中詞數多 → bm25 分數小 → 編號小
    ranking = []

    for card_id in hits:
        record = (-hits[card_id], best[card_id], card_id)
        ranking.append(record)

    ranking.sort()

    # 取前 10 名的卡號，換成完整的知識卡
    ranked = []
    for item in ranking[:10]:
        ranked.append(item[2])
    return {"status": "ok", "terms": terms, "results": get_cards(jade_db, ranked)}

# %% 14. hot_cards() 知識搜尋頁的常見問題：取出所有標記為熱門、已審核的知識卡

def hot_cards(jade_db):
    ids = []
    rows = jade_db.execute("SELECT id FROM knowledge WHERE status = '已審核' AND hot = 1 ORDER BY id")
    for row in rows:
        ids.append(row["id"])
    return get_cards(jade_db, ids)

# %% 15. categories() 有已審核知識卡的分類與張數，照 CATEGORIES 的學習順序排

def categories(jade_db):
    counts = {}
    rows = jade_db.execute("SELECT category, COUNT(*) FROM knowledge WHERE status = '已審核' GROUP BY category")
    for row in rows:
        counts[row[0]] = row[1]

    result = []
    for category in CATEGORIES:
        if category in counts:
            result.append((category, counts[category]))
    return result

# %% 16. cards_by_category() 主題瀏覽分頁：取出某一個分類的所有已審核知識卡

def cards_by_category(jade_db, category):
    ids = []
    rows = jade_db.execute(
        "SELECT id FROM knowledge WHERE status = '已審核' AND category = ? ORDER BY id", (category,))
    for row in rows:
        ids.append(row["id"])
    return get_cards(jade_db, ids)

# %% 17. log_query() 查詢紀錄只給自己看；寫入失敗（例如雲端唯讀）也不影響搜尋

def log_query(jade_db, query, hits, filters=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        jade_db.execute("INSERT INTO query_log (ts, query, hits, filters) VALUES (?,?,?,?)",
                    (now, query, hits, filters))
        jade_db.commit()
    except sqlite3.Error:
        pass
