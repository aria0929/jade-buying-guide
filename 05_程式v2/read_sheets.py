# -*- coding: utf-8 -*-
"""
一玉了然｜讀取試算表（read_sheets.py）：build_db.py 用

支援 Excel（.xlsx）與 Numbers（.numbers）：
    • Excel 直接用 pandas 讀
    • Numbers 需要 numbers-parser 套件：pip install numbers-parser
"""

from pathlib import Path
import pandas as pd

# %% 1. drop_blank_rows() 去掉表格最下面的空白列

def drop_blank_rows(rows):
    while rows:
        last_row = rows[-1]
        filled = 0
        for value in last_row:
            if value not in (None, ""):
                filled = filled + 1
        if filled > 0:
            break
        rows.pop()
    return rows

# %% 2. make_header() 第 1 列當欄位名稱；空白的欄位自動命名為「欄8」這種格式

def make_header(first_row):
    header = []
    for i, title in enumerate(first_row):
        if title is None:
            header.append(f"欄{i + 1}")
        else:
            header.append(str(title).strip())
    return header

# %% 3. read_book() 讀整個檔案，回傳 {工作表名稱: DataFrame}

def read_book(path):
    path = Path(path)

    if path.suffix == ".xlsx":
        return pd.read_excel(path, sheet_name=None, dtype=object)

    # Numbers 檔 pandas 不支援；只有讀 Numbers 時才需要這個套件
    from numbers_parser import Document

    book = {}
    for sheet in Document(str(path)).sheets:
        rows = drop_blank_rows(sheet.tables[0].rows(values_only=True))
        header = make_header(rows[0])
        book[sheet.name] = pd.DataFrame(rows[1:], columns=header)
    return book
