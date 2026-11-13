# -*- coding: utf-8 -*-
"""
一玉了然｜讀取試算表（read_sheets.py）：build_db.py 用

Numbers（.numbers）和 Excel（.xlsx）都能讀：
    • 讀 Numbers 需要先安裝：pip install numbers-parser（只做一次）
"""

from pathlib import Path
import pandas as pd

# Numbers 檔：pandas 不支援，改用 numbers-parser 套件（第一次要先 pip install numbers-parser）
from numbers_parser import Document

# %% read_book() 讀整個檔案 → {工作表名稱: DataFrame}；第 1 列當欄位名稱

def read_book(path):
    path = Path(path)
    if path.suffix == ".xlsx":
        return pd.read_excel(path, sheet_name=None, dtype=object)

    book = {}
    for sheet in Document(str(path)).sheets:
        rows = sheet.tables[0].rows(values_only=True)

        # 去掉最下面的空白列（整列都是空的）
        while rows:
            last_row = rows[-1]
            filled = 0
            for value in last_row:
                if value not in (None, ""):
                    filled = filled + 1
            if filled > 0:
                break
            rows.pop()

        # 第 1 列當欄位名稱；沒寫名稱的欄位自動取名「欄8」這樣，避免出錯
        header = []
        for i, title in enumerate(rows[0]):
            if title is not None:
                header.append(str(title).strip())
            else:
                header.append(f"欄{i + 1}")
        table = pd.DataFrame(rows[1:], columns=header)
        book[sheet.name] = table
    return book