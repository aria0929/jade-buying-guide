# -*- coding: utf-8 -*-
"""
一玉了然｜把 jade_data（Numbers 或 Excel）轉成 SQLite 資料庫 jade.db

用法（在 05_程式v2 資料夾執行；jade_data 放在 01_知識庫）：
    python build_db.py            檢查資料，通過後建立 jade.db
    python build_db.py --check    只檢查，不建立資料庫

流程：
    1. 讀取：知識卡、來源、同義詞、選款規則、選款提醒五張表，以及「選項」表（下拉選項與來源等級）
    2. 檢查：欄位、編號格式與重複、必填、下拉值、來源是否存在、日期格式、來源等級
       → 有錯就列出「哪張表、第幾列、什麼問題」並停止，不會產生有問題的資料庫
    3. 建庫：9 張資料表（含 FTS5 全文索引）
       → 重建時保留舊資料庫的 query_log（查詢紀錄）與 staging（爬蟲與 API 暫存區）
"""

import re
import sqlite3
import sys
import unicodedata
from pathlib import Path
import pandas as pd
from read_sheets import read_book

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parent / "01_知識庫"
DATA_FILE = DATA_DIR / "jade_data.numbers"
DB = HERE / "jade.db"

# 每張工作表必須有的欄位（缺少就報錯，避免第 1 列的欄位名稱被改動）
COLUMNS = {
    "知識卡": ["編號", "分類", "問題", "答案", "注意事項", "關鍵字", "來源編號", "熱門", "狀態"],
    "來源": ["編號", "名稱", "機構或作者", "類型", "網址或書名", "存取日期", "取得方式"],
    "同義詞": ["使用者說法", "標準詞"],
    "選款規則": ["編號", "預算", "品項", "用途", "建議1", "建議2", "建議3", "選購重點", "來源編號"],
    "選款提醒": ["類型", "選項", "品項", "提醒", "來源編號"],
}

# 每張工作表不能空白的欄位
REQUIRED = {
    "知識卡": ["編號", "分類", "問題", "答案", "來源編號", "狀態"],
    "來源": ["編號", "名稱", "類型", "網址或書名", "存取日期"],
    "同義詞": ["使用者說法", "標準詞"],
    "選款規則": ["編號", "預算", "品項", "用途", "建議1", "選購重點"],
    "選款提醒": ["類型", "選項", "提醒"],
}

# 有下拉選單的欄位：{工作表: {欄位: 「選項」表的欄名}}
CHOICES = {
    "知識卡": {"分類": "分類", "熱門": "熱門", "狀態": "狀態"},
    "來源": {"類型": "來源類型"},
    "選款規則": {"預算": "預算", "品項": "品項", "用途": "用途"},
    "選款提醒": {"類型": "提醒類型", "品項": "品項"},
}

# 編號格式（正規表示式）
ID_PATTERN = {"知識卡": r"K\d{3}", "來源": r"S[ABC]\d{3}", "選款規則": r"R\d{3}"}
ID_EXAMPLE = {"知識卡": "K001", "來源": "SA001／SB001／SC001", "選款規則": "R001"}

# 來源的取得方式
METHODS = ("爬蟲", "API", "人工摘錄")

# 資料庫結構（DDL）
SCHEMA = """
CREATE TABLE sources (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, org TEXT, type TEXT NOT NULL,
    level TEXT NOT NULL, url TEXT NOT NULL, accessed TEXT NOT NULL,
    method TEXT                                         -- 取得方式：爬蟲／API／人工摘錄
);
CREATE TABLE knowledge (
    id TEXT PRIMARY KEY, category TEXT NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL,
    caution TEXT, keywords TEXT, hot INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL
);
CREATE TABLE knowledge_sources (
    knowledge_id TEXT NOT NULL REFERENCES knowledge(id),
    source_id TEXT NOT NULL REFERENCES sources(id),
    PRIMARY KEY (knowledge_id, source_id)
);
CREATE TABLE synonyms (term TEXT PRIMARY KEY, canonical TEXT NOT NULL);
CREATE TABLE recommend_rules (
    id TEXT PRIMARY KEY, budget TEXT NOT NULL, item TEXT NOT NULL, use_case TEXT NOT NULL,
    suggestion1 TEXT NOT NULL, suggestion2 TEXT, suggestion3 TEXT, caution TEXT NOT NULL,
    source_ids TEXT, UNIQUE (budget, item, use_case)
);
CREATE TABLE recommend_tips (
    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, option TEXT NOT NULL, item TEXT,
    tip TEXT NOT NULL, source_ids TEXT, UNIQUE (kind, option, item)
);
CREATE TABLE IF NOT EXISTS staging (
    id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT, title TEXT, content TEXT,
    fetched_at TEXT, status TEXT NOT NULL DEFAULT 'pending',
    authors TEXT, citation TEXT,                        -- 爬蟲從網頁讀到的作者與出處
    summary_zh TEXT,                                    -- 中文精簡翻譯（輔助審核用，不是原文）
    method TEXT                                         -- 取得方式：爬蟲／API（OpenAlex）／API（維基百科）
);
CREATE TABLE IF NOT EXISTS query_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, query TEXT,
    hits INTEGER, filters TEXT
);
"""

# 重建時要保留的表：這兩張的資料不是來自試算表，不能被清掉
KEEP_TABLES = ["staging", "query_log"]

# %% 1. clean() 試算表的值轉成乾淨的字串（空白格 → ""）

def clean(value):
    if isinstance(value, float) and pd.isna(value):     # pandas 的空白格是 NaN（float）
        return ""
    return str(value).strip()

# %% 2. to_half() 全形轉半形：Ａ→A、１→1、全形空白→半形空白

def to_half(text):
    return unicodedata.normalize("NFKC", text)

# %% 3. split_multi() 一格寫多個值時用「、」拆開：「SA001、SB002」→ ["SA001", "SB002"]

def split_multi(text):
    parts = []
    for part in text.split("、"):
        if part.strip():
            parts.append(part.strip())
    return parts

# %% 4. strip_note() 去掉欄位名稱後面的括號說明：「使用者說法（用「、」分開）」→「使用者說法」

def strip_note(column):
    return re.sub(r"\s*[（(].*$", "", str(column)).strip()

# %% 5. load() 第 1 步：讀取
# 回傳 sheets：{表名: (欄位, [(試算表列號, 一列資料), ...])}、options：下拉選項、levels：來源類型 → 等級

def load():
    book = read_book(DATA_FILE)

    # 「選項」表：每一欄是一組下拉選項
    option_table = book["選項"]
    options = {}
    for column in option_table.columns:
        values = set()
        for value in option_table[column]:
            if clean(value):
                values.add(clean(value))
        options[column] = values

    # 來源類型 → 來源等級，例：{"鑑定機構": "B"}
    levels = {}
    for source_type, level in zip(option_table["來源類型"], option_table["來源等級"]):
        if clean(source_type):
            levels[clean(source_type)] = clean(level).upper()

    sheets = {}
    for name in COLUMNS:
        table = book[name]

        new_columns = []
        for column in table.columns:
            new_columns.append(strip_note(column))
        table.columns = new_columns

        rows = []
        for row_index, record in table.iterrows():
            row = {}
            for column in COLUMNS[name]:
                row[column] = clean(record.get(column))
            rows.append((row_index + 2, row))       # +2：標題列一列，加上 pandas 從 0 起算
        sheets[name] = (list(table.columns), rows)
    return sheets, options, levels

# %% 6. add_error() 記錄一筆錯誤：哪張表、第幾列、什麼問題

def add_error(errors, sheet, row_number, message):
    errors.append(f"[{sheet}] 第 {row_number} 列：{message}")

# %% 7. check_basic() 每張表的共同檢查：欄位、必填、編號格式與重複、下拉選項

def check_basic(sheets, options, errors):
    for name in sheets:
        columns, rows = sheets[name]
        for column in COLUMNS[name]:
            if column not in columns:
                errors.append(f"[{name}] 少了欄位「{column}」（請不要改第 1 列的欄位名稱）")

        seen = {}       # {編號: 第一次出現的列號}
        for row_number, row in rows:
            for column in REQUIRED[name]:
                if not row[column]:
                    add_error(errors, name, row_number, f"「{column}」不能空白")

            card_id = row.get("編號", "")
            if name in ID_PATTERN and card_id:
                if not re.fullmatch(ID_PATTERN[name], card_id):
                    add_error(errors, name, row_number, f"編號「{card_id}」格式不對，應該像 {ID_EXAMPLE[name]}")
                if card_id in seen:
                    add_error(errors, name, row_number, f"編號「{card_id}」和第 {seen[card_id]} 列重複")
                else:
                    seen[card_id] = row_number

            for column, option_name in CHOICES.get(name, {}).items():
                value = row[column]
                if value and option_name in options and value not in options[option_name]:
                    add_error(errors, name, row_number, f"「{column}」的值「{value}」不在下拉選項裡")

# %% 8. check_sources() 來源表：日期格式、取得方式、等級與編號是否一致；回傳 {來源編號: 等級}

def check_sources(sheets, levels, errors):
    source_level = {}
    for row_number, row in sheets["來源"][1]:
        if row["存取日期"] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["存取日期"]):
            add_error(errors, "來源", row_number, f"存取日期「{row['存取日期']}」請寫成 2026-10-23 的格式")

        level = levels.get(row["類型"], "")
        if row["類型"] and level not in ("A", "B", "C"):
            add_error(errors, "來源", row_number, f"類型「{row['類型']}」在「選項」表沒有對應的來源等級（A／B／C）")

        if row["取得方式"] not in METHODS:
            add_error(errors, "來源", row_number, f"取得方式「{row['取得方式']}」請填：{'、'.join(METHODS)}")

        # 編號的第 2 個字母（SA／SB／SC）要和類型對應的等級一致
        found = re.fullmatch(r"S([ABC])\d{3}", row["編號"])
        if found and level in ("A", "B", "C") and found.group(1) != level:
            add_error(errors, "來源", row_number,
                      f"編號「{row['編號']}」是 {found.group(1)} 級，但類型「{row['類型']}」是 {level} 級，請改編號或類型")
        source_level[row["編號"]] = level
    return source_level

# %% 9. check_source_ids() 知識卡、選款規則、選款提醒填寫的來源編號都要存在

def check_source_ids(sheets, source_level, errors):
    for sheet in ("知識卡", "選款規則", "選款提醒"):
        for row_number, row in sheets[sheet][1]:
            for source_id in split_multi(row["來源編號"]):
                if source_id not in source_level:
                    add_error(errors, sheet, row_number, f"來源編號「{source_id}」在「來源」表裡找不到")

# %% 10. check_card_sources() 已審核的知識卡至少要有 1 個 A／B 級來源；只有 1 個來源的列出提醒

def check_card_sources(sheets, source_level, errors, warnings):
    single = []
    for row_number, row in sheets["知識卡"][1]:
        source_ids = split_multi(row["來源編號"])
        has_ab = False
        for source_id in source_ids:
            if source_level.get(source_id) in ("A", "B"):
                has_ab = True

        if row["狀態"] == "已審核" and source_ids and not has_ab:
            add_error(errors, "知識卡", row_number,
                      f"{row['編號']} 只有 C 級來源；已審核卡至少要有 1 個 A 或 B 級來源（C 級只能補充），請補來源或改回草稿")
        if row["狀態"] == "已審核" and len(source_ids) == 1:
            single.append(row["編號"])

    if single:
        warnings.append(f"這些知識卡只有 1 個來源，建議再找 1 個交叉驗證：{'、'.join(single)}")

# %% 11. check_synonyms() 同一個使用者說法只能對應一個標準詞

def check_synonyms(sheets, errors):
    first_seen = {}     # {使用者說法: (第一次出現的列號, 標準詞)}
    for row_number, row in sheets["同義詞"][1]:
        standard = row["標準詞"]
        for term in split_multi(row["使用者說法"]):
            if term not in first_seen:
                first_seen[term] = (row_number, standard)
            elif first_seen[term][1] != standard:
                first_row, first_standard = first_seen[term]
                add_error(errors, "同義詞", row_number,
                          f"「{term}」已在第 {first_row} 列對應到「{first_standard}」，不能再對應到「{standard}」")

# %% 12. check_tips() 選款提醒的選項要屬於它的類型（例：對象、年齡）

def check_tips(sheets, options, errors):
    for row_number, row in sheets["選款提醒"][1]:
        kind = row["類型"]
        option = row["選項"]
        if kind in options and option and option not in options[kind]:
            add_error(errors, "選款提醒", row_number,
                      f"「{option}」不是「{kind}」的選項（請照「選項」表的「{kind}」欄填）")

# %% 13. check_data() 第 2 步：依序執行所有檢查

def check_data(sheets, options, levels):
    errors = []
    warnings = []
    check_basic(sheets, options, errors)
    source_level = check_sources(sheets, levels, errors)
    check_source_ids(sheets, source_level, errors)
    check_card_sources(sheets, source_level, errors, warnings)
    check_synonyms(sheets, errors)
    check_tips(sheets, options, errors)
    return errors, warnings, source_level

# %% 14. read_kept_rows() 重建前，先讀出舊 jade.db 要保留的資料；回傳 {表名: (欄位, 所有資料)}

def read_kept_rows():
    kept = {}
    if not DB.exists():
        return kept

    old = sqlite3.connect(DB)
    for table in KEEP_TABLES:
        cursor = old.execute(f"SELECT * FROM {table}")
        columns = []
        for info in cursor.description:
            columns.append(info[0])
        kept[table] = (columns, cursor.fetchall())
    old.close()
    return kept

# %% 15. insert_sheets() 把五張表寫進資料庫（全部用 ? 參數化查詢，避免 SQL injection）

def insert_sheets(jade_db, sheets, source_level):

    for row_number, row in sheets["來源"][1]:
        jade_db.execute("INSERT INTO sources VALUES (?,?,?,?,?,?,?,?)",
                        (row["編號"], row["名稱"], row["機構或作者"], row["類型"], source_level[row["編號"]],
                         row["網址或書名"], row["存取日期"], row["取得方式"]))

    # 知識卡：關鍵字統一轉半形；一格多個來源編號拆成 knowledge_sources 的多列
    for row_number, row in sheets["知識卡"][1]:
        half_keywords = []
        for keyword in split_multi(row["關鍵字"]):
            half_keywords.append(to_half(keyword))
        keywords = "、".join(half_keywords)

        hot = 0
        if row["熱門"] == "是":
            hot = 1

        jade_db.execute("INSERT INTO knowledge VALUES (?,?,?,?,?,?,?,?)",
                        (row["編號"], row["分類"], row["問題"], row["答案"], row["注意事項"],
                         keywords, hot, row["狀態"]))
        for source_id in split_multi(row["來源編號"]):
            jade_db.execute("INSERT OR IGNORE INTO knowledge_sources VALUES (?,?)", (row["編號"], source_id))

    # 同義詞：一格多個使用者說法，各存成一列
    for row_number, row in sheets["同義詞"][1]:
        for term in split_multi(row["使用者說法"]):
            jade_db.execute("INSERT OR IGNORE INTO synonyms VALUES (?,?)", (to_half(term), to_half(row["標準詞"])))

    for row_number, row in sheets["選款規則"][1]:
        source_ids = "、".join(split_multi(row["來源編號"]))
        jade_db.execute("INSERT INTO recommend_rules VALUES (?,?,?,?,?,?,?,?,?)",
                        (row["編號"], row["預算"], row["品項"], row["用途"], row["建議1"], row["建議2"],
                         row["建議3"], row["選購重點"], source_ids))

    for row_number, row in sheets["選款提醒"][1]:
        source_ids = "、".join(split_multi(row["來源編號"]))
        jade_db.execute("INSERT INTO recommend_tips (kind, option, item, tip, source_ids) VALUES (?,?,?,?,?)",
                        (row["類型"], row["選項"], row["品項"], row["提醒"], source_ids))

# %% 16. build_fts() 建立 FTS5 全文索引（trigram：每 3 個字切一段，中文不需斷詞）

def build_fts(jade_db):
    jade_db.execute("CREATE VIRTUAL TABLE knowledge_fts USING fts5("
                    "id UNINDEXED, question, answer, caution, keywords, tokenize='trigram')")
    fts_rows = []
    for card in jade_db.execute("SELECT id, question, answer, caution, keywords FROM knowledge"):
        values = [card[0]]
        for text in card[1:]:
            values.append(to_half(text))
        fts_rows.append(tuple(values))
    jade_db.executemany("INSERT INTO knowledge_fts VALUES (?,?,?,?,?)", fts_rows)

# %% 17. restore_kept() 把重建前保留的 staging、query_log 寫回新資料庫

def restore_kept(jade_db, kept):
    for table in kept:
        columns, rows = kept[table]
        if rows:
            marks = ",".join("?" * len(columns))
            jade_db.executemany(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({marks})", rows)

# %% 18. build() 第 3 步：建庫
# 先寫到 jade.db.tmp，全部成功才取代舊的 jade.db；中途出錯時舊資料庫不受影響

def build(sheets, source_level):
    kept = read_kept_rows()
    temp_file = DB.with_name("jade.db.tmp")
    if temp_file.exists():
        temp_file.unlink()

    jade_db = sqlite3.connect(temp_file)
    jade_db.executescript(SCHEMA)
    insert_sheets(jade_db, sheets, source_level)
    build_fts(jade_db)
    restore_kept(jade_db, kept)
    jade_db.commit()
    jade_db.close()
    temp_file.replace(DB)

    counts = {}
    for table in kept:
        counts[table] = len(kept[table][1])
    return counts

# %% 19. count_by() 計算每個值出現幾次，例：分類 → 張數

def count_by(values):
    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts

# %% 20. main() 主流程：讀取 → 檢查 → 通過才建庫 → 印出統計

def main():
    check_only = "--check" in sys.argv
    sheets, options, levels = load()
    errors, warnings, source_level = check_data(sheets, options, levels)

    synonym_count = 0
    for row_number, row in sheets["同義詞"][1]:
        synonym_count = synonym_count + len(split_multi(row["使用者說法"]))
    print(f"讀取 {DATA_FILE.name}：知識卡 {len(sheets['知識卡'][1])} 筆、來源 {len(sheets['來源'][1])} 筆、"
          f"同義詞 {synonym_count} 個說法、選款規則 {len(sheets['選款規則'][1])} 條、"
          f"選款提醒 {len(sheets['選款提醒'][1])} 句")
    for warning in warnings:
        print("提醒：" + warning)

    if errors:
        print(f"\n檢查沒過，共 {len(errors)} 個問題：")
        for error in errors:
            print("  ✗ " + error)
        print("\n請修改 jade_data 後再執行一次。jade.db 沒有變動。")
        sys.exit(1)
    print("✓ 檢查通過")
    if check_only:
        return

    kept = build(sheets, source_level)
    print(f"✓ 已建立 {DB.name}")

    categories = []
    for row_number, row in sheets["知識卡"][1]:
        categories.append(row["分類"])
    category_texts = []
    for category, count in count_by(categories).items():
        category_texts.append(f"{category} {count}")
    print("  分類分布：" + "、".join(category_texts))

    level_counts = count_by(source_level.values())
    level_texts = []
    for level in sorted(level_counts):
        level_texts.append(f"{level} 級 {level_counts[level]}")
    print("  來源等級：" + "、".join(level_texts))
    print("  全文檢索（FTS5 trigram）：已建立")

    if sum(kept.values()) > 0:
        kept_texts = []
        for table, count in kept.items():
            kept_texts.append(f"{table} {count} 筆")
        print("  已保留：" + "、".join(kept_texts))

# %% 執行入口：直接執行 python build_db.py 時才執行 main()（被其他程式 import 時不執行）

if __name__ == "__main__":
    main()
