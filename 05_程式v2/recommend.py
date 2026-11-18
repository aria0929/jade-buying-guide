# -*- coding: utf-8 -*-
"""
一玉了然｜規則式選款建議（recommend.py）

使用者選預算、品項、用途後，從選款規則表找建議；找不到就逐層放寬條件：
    1. 預算、品項、用途完全符合
    2. 用途改為「不限」
    3. 預算改為「不限」
    4. 該品項的通用規則（預算、用途都「不限」）
每個品項都有通用規則，所以任何組合都有建議。

對象、年齡的組合太多，不寫成規則，改從「選款提醒」各找一句提醒附在建議下方。
"""

# 選單選項，需與 jade_data「選項」表一致
BUDGETS = ["8,000 以下", "8,000–12,000", "12,000–30,000", "30,000 以上"]
ITEMS = ["吊墜", "戒指", "手鐲", "耳環", "手串"]
OCCASIONS = ["日常配戴", "婚嫁", "紀念", "祈福護身", "收藏"]
USES = OCCASIONS + ["其他"]     # 「其他」沒有專屬規則，直接使用通用規則

NONE = "不指定"
TARGETS = [NONE, "自己", "家人親戚", "伴侶", "朋友", "同事主管", "商務客戶"]
AGES = [NONE, "嬰幼兒（0–3 歲）", "兒童（4–12 歲）", "青少年（13–17 歲）", "青年（18–29 歲）",
        "中壯年（30–64 歲）", "長者（65 歲以上）"]

ANY = "不限"                    # 僅用於通用規則，網站選單不提供

# %% 1. find_rule() 依四層退回找出選款規則

def find_rule(budget, item, use, jade_db):

    # 每一層：(代號, 網站顯示名稱, 查詢條件)，由精準排到寬鬆
    levels = [
        ("exact",      "完全符合",                   (budget, item, use)),
        ("any_use",    "同品項、同預算（用途不限）", (budget, item, ANY)),
        ("any_budget", "同品項、同用途（預算不限）", (ANY, item, use)),
        ("general",    "該品項的通用建議",           (ANY, item, ANY)),
    ]

    sql = "SELECT * FROM recommend_rules WHERE budget = ? AND item = ? AND use_case = ?"

    for match, label, condition in levels:
        row = jade_db.execute(sql, condition).fetchone()
        if row is None:                             # 這一層沒有規則，放寬到下一層
            continue

        rule = dict(row)
        rule["match"] = match                       # 網站依此判斷是否為通用建議
        rule["match_label"] = label

        # 建議款式最多 3 個，略過空白欄位
        rule["suggestions"] = []
        for suggestion in (row["suggestion1"], row["suggestion2"], row["suggestion3"]):
            if suggestion:
                rule["suggestions"].append(suggestion)
        return rule

    return None                                     # 每個品項都有通用規則，正常不會執行到這裡

# %% 2. find_tips() 依預算、對象、年齡找出選款提醒

def find_tips(target, age, item, budget, jade_db):

    # 品項空白的提醒適用所有品項；ORDER BY item DESC 讓指定品項的提醒排在前面
    sql = ("SELECT * FROM recommend_tips "
           "WHERE kind = ? AND option = ? AND (item = '' OR item = ?) "
           "ORDER BY item DESC")

    tips = []
    for kind, option in [("預算", budget), ("對象", target), ("年齡", age)]:
        if option == NONE or option == ANY:         # 未指定的條件不顯示提醒
            continue

        for row in jade_db.execute(sql, (kind, option, item)).fetchall():
            tips.append(dict(row))
    return tips
