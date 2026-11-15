# -*- coding: utf-8 -*-
"""
一玉了然｜規則式選款建議（recommend.py）

使用者選「預算＋品項＋用途」，依序找規則，找到就停：
    1. 完全符合：預算、品項、用途都一樣
    2. 同品項、同預算，用途「不限」
    3. 同品項、同用途，預算「不限」
    4. 該品項的通用規則：預算、用途都「不限」
→ 每個品項只要有通用規則，任何選法都不會空白；用途選「其他」也會落到通用規則。

對象、年齡不寫成規則（組合太多），只從「選款提醒」各找一句提醒附在建議下面。

"""

# 要和 jade_data「選項」表一致（「不限」只給通用規則用，不放進網站選單）
BUDGETS = ["8,000 以下", "8,000–12,000", "12,000–30,000", "30,000 以上"]
ITEMS = ["吊墜", "戒指", "手鐲", "耳環", "手串"]
OCCASIONS = ["日常配戴", "婚嫁", "紀念", "祈福護身", "收藏"]

# 「其他」沒有專屬規則，直接用通用規則
USES = OCCASIONS + ["其他"]
NONE = "不指定"
TARGETS = [NONE, "自己", "家人親戚", "伴侶", "朋友", "同事主管", "商務客戶"]
AGES = [NONE, "嬰幼兒（0–3 歲）", "兒童（4–12 歲）", "青少年（13–17 歲）", "青年（18–29 歲）",
        "中壯年（30–64 歲）", "長者（65 歲以上）"]
ANY = "不限"

# 四層退回規則的名稱（順序很重要：越前面越精準）；網站會顯示用到哪一層，讓使用者知道建議怎麼來的
LEVELS = [
    ("exact", "完全符合"),
    ("any_use", "同品項、同預算（用途不限）"),
    ("any_budget", "同品項、同用途（預算不限）"),
    ("general", "該品項的通用建議"),
]

# %% 1. find_rule() 回傳規則 dict（含 match、match_label）

def find_rule(budget, item, use, jade_db):

    # 依序嘗試四種條件：完全符合 → 用途不限 → 預算不限 → 都不限（通用規則）
    tries = [(budget, item, use), (budget, item, ANY), (ANY, item, use), (ANY, item, ANY)]

    # 由精準到寬鬆逐層查，命中即回傳
    for i in range(len(LEVELS)):
        level_key, level_label = LEVELS[i]
        condition = tries[i]
        row = jade_db.execute("SELECT * FROM recommend_rules WHERE budget = ? AND item = ? AND use_case = ?",
                      condition).fetchone()
        if row:
            rule = dict(row)
            rule["match"] = level_key
            rule["match_label"] = level_label

            # 建議最多 3 個，空白的不放進清單
            rule["suggestions"] = []
            for suggestion in (row["suggestion1"], row["suggestion2"], row["suggestion3"]):
                if suggestion:
                    rule["suggestions"].append(suggestion)
            return rule

# %% 2. find_tips() 依照預算、對象、年齡，找出所有相關的提醒，專門寫給這個品項的排前面。

def find_tips(target, age, item, budget, jade_db):
    tips = []

    # 預算、對象、年齡各查一次；選「不指定」或「不限」就跳過，不顯示提醒
    for kind, option in (("預算", budget), ("對象", target), ("年齡", age)):
        if option == NONE or option == ANY:
            continue

        # 品項空白＝所有品項都適用；ORDER BY item DESC 讓「有指定品項」的提醒排在前面（比較精準）
        rows = jade_db.execute("SELECT * FROM recommend_tips WHERE kind = ? AND option = ? AND (item = '' OR item = ?) "
                       "ORDER BY item DESC", (kind, option, item)).fetchall()
        for row in rows:
            tips.append(dict(row))
    return tips
