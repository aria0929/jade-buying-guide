# -*- coding: utf-8 -*-
"""
一玉了然｜知識檢索（search.py）

流程：
    1. 問句清理：全形轉半形、去掉標點與空白
    2. 同義詞展開：灌膠 → B貨、鐲子 → 手鐲
    3. 關鍵詞比對（LIKE）：負責「冰種」這類 2 個字的短詞
    4. FTS5 全文檢索：trigram 每 3 個字切一段，負責 3 個字以上的詞
    5. 排序：先比命中幾個關鍵詞，再比 bm25 相關度分數
    6. 範圍外判斷：問到鑽石等非翡翠問題，或沒有命中任何卡片時，回傳查無資料

四種模式記錄搜尋的改進過程（網站、小考、翠小二都用 hybrid）：
    like   ：只用 LIKE，不展開同義詞
    fts    ：只用 FTS5（2 個字的詞找不到），不展開同義詞
    mix    ：同義詞＋LIKE＋FTS5，尚未加入範圍外判斷
    hybrid ：mix＋範圍外判斷

單獨測試：在 Spyder 按 F5，再到 Console 輸入 search("灌膠的翡翠能買嗎", connect())
"""

import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / "jade.db"

# 範圍外的詞：問句有這些詞、又沒有提到翡翠，就判定不是翡翠問題
NOT_JADE = ["鑽石", "珍珠", "黃金", "K金", "白金", "和田玉", "水晶", "紅寶石", "藍寶石",
            "琥珀", "珊瑚", "蜜蠟", "銀飾", "手錶"]

# 問句有這些字就視為翡翠問題，即使也提到鑽石（例：翡翠和鑽石哪個貴）
JADE = ["翡翠", "玉", "貨"]

# 幾乎每張卡都有的普通詞，搜尋時優先使用其他詞
COMMON_WORDS = {"翡翠", "玉", "玉石"}

# 判斷「只是在問翡翠本身」時，要一併去掉的虛詞
FILLER_WORDS = ["是什麼", "什麼", "介紹", "是", "嗎", "呢", "的"]

# 七大分類，依新手學習順序排列（與 jade_data「選項」表一致）
CATEGORIES = ["認識翡翠", "品質判斷", "真假處理", "證書鑑定", "選購價格", "款式寓意", "配戴保養"]

# 要去掉的中英文標點
SYMBOL = "，。、！？；：「」『』（）()《》〈〉,.!?;:'\"…～~·-—_/\\|｜"

# %% 1. connect() 連線到資料庫

def connect():
    # Streamlit 會在不同執行緒共用同一個連線，所以關閉同執行緒檢查
    jade_db = sqlite3.connect(DB, check_same_thread=False)
    jade_db.row_factory = sqlite3.Row
    return jade_db

# %% 2. clean_text() 全形轉半形、去掉標點與空白、英文轉大寫

def clean_text(text):
    half = unicodedata.normalize("NFKC", text)

    result = ""
    for char in half:
        if char.isspace() or char in SYMBOL:
            continue
        result = result + char
    return result.upper()

# %% 3. contains_any() 句子裡是否出現清單中的任何一個詞

def contains_any(text, words):
    for word in words:
        if word in text:
            return True
    return False

# %% 4. get_words() 詞庫＝知識卡關鍵字＋同義詞（使用者說法與標準詞）

def get_words(jade_db):
    words = set()

    for row in jade_db.execute("SELECT keywords FROM knowledge WHERE status = '已審核'"):
        for keyword in row[0].split("、"):
            words.add(clean_text(keyword))

    # synonyms：{使用者說法: 標準詞}
    synonyms = {}
    for row in jade_db.execute("SELECT term, canonical FROM synonyms"):
        synonyms[clean_text(row[0])] = clean_text(row[1])

    for term, standard in synonyms.items():
        words.add(term)
        words.add(standard)

    words.discard("")           # 沒填關鍵字的卡會產生空字串
    return words, synonyms

# %% 5. is_inside() 這個詞是否已經被清單裡某個較長的詞包含

def is_inside(word, longer_words):
    for longer in longer_words:
        if word in longer:
            return True
    return False

# %% 6. find_terms() 找出問句裡的詞庫詞；長詞優先，被長詞包含的短詞不重複計算

def find_terms(question, words):

    found = []
    for word in words:
        if word not in question:
            continue
        if len(word) == 1 and question != word:     # 單一個字只在整句就是它時才算
            continue
        found.append(word)
    found = sorted(found, key=len, reverse=True)

    # 例：已選「翡翠手鐲」，就不再選「手鐲」
    terms = []
    for word in found:
        if not is_inside(word, terms):
            terms.append(word)

    # 問句很短（2～4 個字）又不在詞庫：直接用整句搜尋
    if len(terms) == 0 and 2 <= len(question) <= 4:
        terms = [question]
    return terms

# %% 7. expand_synonyms() 同義詞展開：使用者說法加上標準詞一起搜尋（例：灌膠 → 加上 B貨）

def expand_synonyms(terms, synonyms):
    all_terms = list(terms)
    for term in terms:
        standard = synonyms.get(term)
        if standard and standard not in all_terms:
            all_terms.append(standard)
    return all_terms

# %% 8. drop_common() 去掉「翡翠、玉」這類普通詞，只用有鑑別度的詞搜尋

def drop_common(question, terms):

    specific = []
    for term in terms:
        if term not in COMMON_WORDS:
            specific.append(term)
    if specific:
        return specific

    # 只剩普通詞時，要分辨是「真的在問翡翠」還是「問了知識庫沒有的東西」：
    # 去掉普通詞與虛詞後，沒有剩下任何字 → 在問翡翠本身（翡翠是什麼）→ 照常搜尋
    # 還有剩下的字 → 問了知識庫沒有的（翡翠要開光嗎 → 剩「要開光」）→ 查無資料
    rest = question
    for word in sorted(COMMON_WORDS, key=len, reverse=True) + FILLER_WORDS:
        rest = rest.replace(word, "")

    if rest:
        return []
    return terms

# %% 9. isnt_jade() 範圍外判斷：提到鑽石等其他寶石、又沒有提到翡翠 → True

def isnt_jade(question):
    return contains_any(question, NOT_JADE) and not contains_any(question, JADE)

# %% 10. _like() LIKE 比對：只比「問題＋關鍵字」，答案裡順帶提到的詞不算，避免結果太雜

def _like(jade_db, term):
    sql = ("SELECT id FROM knowledge WHERE status = '已審核' AND "
           "(UPPER(REPLACE(question,' ','')) LIKE ? OR UPPER(keywords) LIKE ?)")
    pattern = f"%{term}%"

    found = {}
    for row in jade_db.execute(sql, (pattern, pattern)):
        found[row["id"]] = 0.0
    return found

# %% 11. _fts() FTS5 全文檢索：trigram 每 3 個字切一段建索引，中文沒有空格也能搜尋

def _fts(jade_db, term):

    # trigram 至少需要 3 個字，較短的詞交給 LIKE
    if len(term) < 3:
        return {}

    # 前後加雙引號表示照字面搜尋，避免 + - 被當成 FTS5 指令（例：B+C貨）
    phrase = '"' + term.replace('"', "") + '"'

    # bm25 是相關度分數：數字越小（越負）越相關
    sql = ("SELECT f.id, bm25(knowledge_fts) AS score FROM knowledge_fts f "
           "JOIN knowledge k ON k.id = f.id WHERE knowledge_fts MATCH ? AND k.status = '已審核'")

    found = {}
    for row in jade_db.execute(sql, (phrase,)):
        found[row["id"]] = row["score"]
    return found

# %% 12. get_cards() 依編號取出知識卡，並附上參考資料（JOIN sources）

def get_cards(jade_db, card_ids):
    card_sql = "SELECT * FROM knowledge WHERE id = ?"
    source_sql = ("SELECT s.* FROM knowledge_sources ks JOIN sources s ON s.id = ks.source_id "
                  "WHERE ks.knowledge_id = ? ORDER BY s.level, s.id")

    cards = []
    for card_id in card_ids:
        card = jade_db.execute(card_sql, (card_id,)).fetchone()

        sources = []
        for row in jade_db.execute(source_sql, (card_id,)).fetchall():
            sources.append(dict(row))

        cards.append({
            "id": card["id"], "category": card["category"], "question": card["question"],
            "answer": card["answer"], "caution": card["caution"], "keywords": card["keywords"],
            "hot": bool(card["hot"]), "sources": sources,
        })
    return cards

# %% 13. pick_terms() 挑出關鍵詞 → 補同義詞 → 去掉普通詞（例：手鐲有沒有灌過膠 → 灌過膠、手鐲、B貨）

def pick_terms(jade_db, question, mode):
    words, synonyms = get_words(jade_db)
    terms = find_terms(question, words)

    if mode == "mix" or mode == "hybrid":
        terms = expand_synonyms(terms, synonyms)
    if mode == "hybrid":
        terms = drop_common(question, terms)
    return terms

# %% 14. score_cards() 每個詞各找一次卡片，記錄每張卡命中幾個詞、最好的 bm25 分數

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

# %% 15. search() 搜尋主程式（網站、小考、翠小二都呼叫這個函式）

def search(text, jade_db, mode="hybrid"):

    question = clean_text(text)
    if mode == "hybrid" and isnt_jade(question):
        return {"status": "NOT_JADE", "terms": [], "results": []}

    terms = pick_terms(jade_db, question, mode)
    hits, best = score_cards(jade_db, terms, mode)
    if not hits:
        return {"status": "no_result", "terms": terms, "results": []}

    # 排序依據：命中詞數多 → bm25 分數小 → 編號小（命中數取負號，才能一起由小排到大）
    ranking = []
    for card_id in hits:
        ranking.append((-hits[card_id], best[card_id], card_id))
    ranking.sort()

    # 取前 10 名
    top_ids = []
    for count, score, card_id in ranking[:10]:
        top_ids.append(card_id)
    return {"status": "ok", "terms": terms, "results": get_cards(jade_db, top_ids)}

# %% 16. hot_cards() 常見問題：所有標記為熱門、已審核的知識卡

def hot_cards(jade_db):
    ids = []
    for row in jade_db.execute("SELECT id FROM knowledge WHERE status = '已審核' AND hot = 1 ORDER BY id"):
        ids.append(row["id"])
    return get_cards(jade_db, ids)

# %% 17. categories() 每個分類的已審核卡片張數，依 CATEGORIES 的順序排列

def categories(jade_db):
    sql = "SELECT category, COUNT(*) FROM knowledge WHERE status = '已審核' GROUP BY category"
    counts = {}
    for row in jade_db.execute(sql):
        counts[row[0]] = row[1]

    result = []
    for category in CATEGORIES:
        if category in counts:
            result.append((category, counts[category]))
    return result

# %% 18. cards_by_category() 主題瀏覽：某一個分類的所有已審核知識卡

def cards_by_category(jade_db, category):
    sql = "SELECT id FROM knowledge WHERE status = '已審核' AND category = ? ORDER BY id"
    ids = []
    for row in jade_db.execute(sql, (category,)):
        ids.append(row["id"])
    return get_cards(jade_db, ids)

# %% 19. log_query() 記錄查詢（僅供管理者查看）；寫入失敗（例如雲端唯讀）不影響搜尋

def log_query(jade_db, query, hits, filters=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        jade_db.execute("INSERT INTO query_log (ts, query, hits, filters) VALUES (?,?,?,?)",
                        (now, query, hits, filters))
        jade_db.commit()
    except sqlite3.Error:
        pass
