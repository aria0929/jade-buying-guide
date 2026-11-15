# -*- coding: utf-8 -*-
"""
一玉了然｜小考（quiz.py）

拿 02_測試題/test_questions.xlsx 的測試題去問搜尋系統：
    • 標準問法、換句話問：預期的知識卡出現在前 3 名就算對
    • 範圍外問題：系統回答查無資料才算對
印出總分、各題型答對率（上次 → 這次）、答錯的題目；
成績存到 03_輸出結果/quiz_result.csv，並畫 fig_quiz.png（上次＝改之前、這次＝改之後並排比較）。

"""

import pandas as pd
import matplotlib.pyplot as plt
from search import connect, search

RESULT_FILE = "../03_輸出結果/quiz_result.csv"
KINDS = ["一般", "同義詞或口語", "查無或超出範圍"]

# 題型的白話名稱（印出來、畫圖時用）
NAMES = {"一般": "標準問法", "同義詞或口語": "換句話問", "查無或超出範圍": "範圍外問題"}


# %% 1. rate_of() 算某一種題型的答對率，例：rate_of(成績表, "一般") → 100.0

def rate_of(table, kind):
    part = table[table["題型"] == kind]
    if len(part) == 0:
        return 0
    ok = part[part["結果"] == "✓"]
    return round(len(ok) / len(part) * 100, 1)

# %% 2. 讀上一次的成績（改之前）；第一次跑還沒有檔案，就當作沒有

try:
    last = pd.read_csv(RESULT_FILE)
except FileNotFoundError:
    last = None

# %% 3. 讀測試題、一題一題考

tests = pd.read_excel("../02_測試題/test_questions.xlsx", sheet_name="測試題")
tests = tests.fillna("")

jade_db = connect()
results = []
for i in range(len(tests)):
    number = tests.loc[i, "編號"]
    kind = tests.loc[i, "題型"]
    question = tests.loc[i, "問題"]
    answer = tests.loc[i, "預期答案"]

    # 選款題不是用搜尋找的，這裡先不考
    if kind == "多條件選款":
        continue

    found = search(question, jade_db)

    # 拿出前 3 名的知識卡編號
    top3 = []
    for card in found["results"][:3]:
        top3.append(card["id"])

    ok = False
    if answer == "":
        # 查無題：系統沒有找到卡片（回答查無資料）才算對
        if found["status"] != "ok":
            ok = True
    else:
        # 一般題：預期答案可能有好幾張（用「、」隔開），有一張在前 3 名就算對
        for card_id in answer.split("、"):
            if card_id in top3:
                ok = True

    if ok:
        mark = "✓"
    else:
        mark = "✗"
    results.append([number, kind, question, answer, "、".join(top3), mark])
jade_db.close()

now = pd.DataFrame(results, columns=["編號", "題型", "問題", "預期答案", "前3名", "結果"])

# %% 4. 印出成績：總分 → 各題型（上次 → 這次）→ 答錯的題目

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
    if last is not None:
        last_rate = rate_of(last, kind)
        last_rates.append(last_rate)
        print(f"  {NAMES[kind]}（{kind}）：{last_rate}% → {now_rate}%")
    else:
        print(f"  {NAMES[kind]}（{kind}）：{now_rate}%")

print("\n答錯的題目：")
wrong = now[now["結果"] == "✗"]
for i in range(len(wrong)):
    row = wrong.iloc[i]
    print(f"  {row['編號']} {row['問題']} → 前 3 名 {row['前3名']}（應為 {row['預期答案']}）")
if len(wrong) == 0:
    print("  沒有，全部答對")

# %% 5. 存這次的成績（utf-8-sig：Excel 打開不會亂碼）；下次跑時它就變成「上次」

now.to_csv(RESULT_FILE, index=False, encoding="utf-8-sig")

# %% 6. 畫圖：上次（灰）和這次（綠）並排比較

plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "PingFang TC"]
plt.figure(figsize=(8, 4.8))

x = range(len(KINDS))

labels = []
for kind in KINDS:
    labels.append(f"{NAMES[kind]}\n（{kind}）")
if last is not None:
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
else:
    plt.bar(list(x), now_rates, width=0.5, color="#1F7A5C")
    for i in x:
        plt.text(i, now_rates[i] + 2, f"{now_rates[i]}%", ha="center", fontsize=11)
    plt.title(f"小考結果：{total} 題答對 {right} 題")

plt.xticks(list(x), labels)
plt.ylim(0, 115)
plt.ylabel("答對率（%）")
plt.tight_layout()
plt.savefig("../03_輸出結果/fig_quiz.png", dpi=150)
plt.show()
