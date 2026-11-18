# -*- coding: utf-8 -*-
"""
一玉了然｜小考（quiz.py）

用 02_測試題/test_questions.xlsx 的題目測試搜尋系統：
    • 標準問法、換句話問：預期的知識卡出現在前 3 名就算答對
    • 範圍外問題：系統回答查無資料才算答對
印出總分、各題型答對率（上次 → 這次）與答錯的題目；
成績存到 03_輸出結果/quiz_result.csv，並畫 fig_quiz.png（上次＝改之前、這次＝改之後）。
"""

import pandas as pd
import matplotlib.pyplot as plt
from search import connect, search

TEST_FILE = "../02_測試題/test_questions.xlsx"
RESULT_FILE = "../03_輸出結果/quiz_result.csv"
FIGURE_FILE = "../03_輸出結果/fig_quiz.png"

KINDS = ["一般", "同義詞或口語", "查無或超出範圍"]
NAMES = {"一般": "標準問法", "同義詞或口語": "換句話問", "查無或超出範圍": "範圍外問題"}

# %% 1. rate_of() 某一種題型的答對率（%）

def rate_of(table, kind):
    part = table[table["題型"] == kind]
    if len(part) == 0:
        return 0
    ok = part[part["結果"] == "✓"]
    return round(len(ok) / len(part) * 100, 1)

# %% 2. is_correct() 判斷一題是否答對

def is_correct(found, answer, top3):

    # 範圍外問題：沒有找到任何卡片才算對
    if answer == "":
        return found["status"] != "ok"

    # 預期答案可能有好幾張（用「、」分隔），任一張在前 3 名就算對
    for card_id in answer.split("、"):
        if card_id in top3:
            return True
    return False

# %% 3. run_quiz() 逐題測試，回傳成績表

def run_quiz():
    tests = pd.read_excel(TEST_FILE, sheet_name="測試題")
    tests = tests.fillna("")

    jade_db = connect()
    results = []
    for i in range(len(tests)):
        number = tests.loc[i, "編號"]
        kind = tests.loc[i, "題型"]
        question = tests.loc[i, "問題"]
        answer = tests.loc[i, "預期答案"]

        # 選款題不經過搜尋，不列入小考
        if kind == "多條件選款":
            continue

        found = search(question, jade_db)
        top3 = []
        for card in found["results"][:3]:
            top3.append(card["id"])

        if is_correct(found, answer, top3):
            mark = "✓"
        else:
            mark = "✗"
        results.append([number, kind, question, answer, "、".join(top3), mark])
    jade_db.close()

    return pd.DataFrame(results, columns=["編號", "題型", "問題", "預期答案", "前3名", "結果"])

# %% 4. 讀上一次的成績（第一次執行時沒有檔案）

try:
    last = pd.read_csv(RESULT_FILE)
except FileNotFoundError:
    last = None

# %% 5. 考試並印出成績：總分 → 各題型（上次 → 這次）→ 答錯的題目

now = run_quiz()

total = len(now)
right = len(now[now["結果"] == "✓"])
print(f"小考結果：{total} 題答對 {right} 題（{round(right / total * 100, 1)}%）")
if last is not None:
    last_right = len(last[last["結果"] == "✓"])
    print(f"上一次：{len(last)} 題答對 {last_right} 題")

print("\n依題型（上次 → 這次）：")
last_rates = []
now_rates = []
for kind in KINDS:
    now_rate = rate_of(now, kind)
    now_rates.append(now_rate)
    if last is None:
        print(f"  {NAMES[kind]}（{kind}）：{now_rate}%")
    else:
        last_rate = rate_of(last, kind)
        last_rates.append(last_rate)
        print(f"  {NAMES[kind]}（{kind}）：{last_rate}% → {now_rate}%")

print("\n答錯的題目：")
wrong = now[now["結果"] == "✗"]
for i in range(len(wrong)):
    row = wrong.iloc[i]
    print(f"  {row['編號']} {row['問題']} → 前 3 名 {row['前3名']}（應為 {row['預期答案']}）")
if len(wrong) == 0:
    print("  沒有，全部答對")

# %% 6. 存這次的成績（utf-8-sig 讓 Excel 正確顯示中文）；下次執行時就是「上次」

now.to_csv(RESULT_FILE, index=False, encoding="utf-8-sig")

# %% 7. 畫圖：上次（灰）和這次（綠）並排比較

plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PingFang TC"]
plt.figure(figsize=(8, 4.8))

x = range(len(KINDS))
labels = []
for kind in KINDS:
    labels.append(f"{NAMES[kind]}\n（{kind}）")

if last is None:
    plt.bar(list(x), now_rates, width=0.5, color="#1F7A5C")
    for i in x:
        plt.text(i, now_rates[i] + 2, f"{now_rates[i]}%", ha="center", fontsize=11)
    plt.title(f"小考結果：{total} 題答對 {right} 題")
else:
    left = []
    right_x = []
    for i in x:
        left.append(i - 0.2)
        right_x.append(i + 0.2)
    plt.bar(left, last_rates, width=0.38, color="#B8C2BF", label=f"改之前（{last_right}/{len(last)}）")
    plt.bar(right_x, now_rates, width=0.38, color="#1F7A5C", label=f"改之後（{right}/{total}）")
    for i in x:
        plt.text(left[i], last_rates[i] + 2, f"{last_rates[i]}%", ha="center", fontsize=10)
        plt.text(right_x[i], now_rates[i] + 2, f"{now_rates[i]}%", ha="center", fontsize=10)
    plt.legend(loc="lower right")
    plt.title("小考前後比較：各題型答對率")

plt.xticks(list(x), labels)
plt.ylim(0, 115)
plt.ylabel("答對率（%）")
plt.tight_layout()
plt.savefig(FIGURE_FILE, dpi=150)
plt.show()
