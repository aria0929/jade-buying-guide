# -*- coding: utf-8 -*-
"""
一玉了然｜翠小二：翡翠問答機器人（bot.py）

原理和銀行、官網的客服機器人一樣：不是自己生成答案，而是
    0. 先把注音文、台語、英文、簡體字換成一般說法（normalize.csv），例：ㄐㄧㄚˇ → 假、甘有影 → 是真的嗎
    1. 判斷意圖：閒聊、查知識、挑款式、付款前檢查、網站導覽、帶路到某個分頁
    2. 查知識 → 呼叫 search.py 的 search()，答案一定來自審核過的知識卡（有來源）
    3. 沒把握 → 反問「您想問的是下面哪一題呢？」，列出候選讓使用者點
    4. 挑款式 → 直接帶到「選款建議」分頁，句子裡提到的品項、用途、預算先幫忙選好
    5. 答不出來 → 猜是不是錯字（同音字優先），改正後再找一次
    6. 奇怪的問題（招財、咬咬看、放冰箱、穿越…）→ 奇怪問題題庫 weird.csv 先接住，再帶回有根據的知識卡
    7. 真的答不出來 → 換著說法、不說「很抱歉」，並推薦可以點的題目，對話不會卡住
    8. 每一句都記進 query_log，之後可以分析「哪些問題答不好」

這支程式只負責「大腦」（判斷和回答），不碰畫面；畫面在 app.py。
"""

import csv
import random
import re
from pathlib import Path

from pypinyin import lazy_pinyin

from recommend import BUDGETS, ITEMS, OCCASIONS
from search import clean_text, connect, find_terms, get_cards, get_words, hot_cards
from search import isnt_jade, log_query, pick_terms, score_cards, search

# 想挑款式的說法：強的詞一出現就算；弱的詞（送、買）還要看到品項、用途或預算才算
REC_STRONG = ["推薦", "幫我挑", "幫我選", "挑禮物", "送禮", "禮物", "預算",
              "選什麼款", "什麼款式", "挑款式", "選款式", "哪種款", "哪個款式", "選哪款", "挑哪款"]
REC_WEAK = ["送", "買給", "想買", "要買", "挑", "選哪", "選什麼", "適合"]
# 明確要我們推薦、幫忙挑的說法（一出現就帶去挑款式）
REC_EXPLICIT = ["推薦", "幫我挑", "幫我選", "挑禮物", "選什麼款", "什麼款式", "挑款式", "選款式",
                "哪種款", "哪個款式", "選哪款", "挑哪款"]
# 發問的說法：句子裡有這些、又沒有明確要推薦 → 是在問知識
QUESTION_WORDS = ["嗎", "是不是", "會不會", "算不算", "要不要", "能不能", "可不可以", "夠不夠",
                  "還是", "有什麼", "哪幾", "什麼意思", "差很多", "講究", "幾公斤",
                  "怎麼", "差別", "有沒有差", "差在哪", "哪一點", "先看", "一般", "多少的"]
# 別人推薦（店員推薦…）不是要我們推薦，判斷意圖前先拿掉
OTHERS_RECOMMEND = ["店員推薦", "老闆推薦", "店家推薦", "朋友推薦", "銷售推薦", "櫃姐推薦"]
# 短的追問前後常加的字（那裂呢 → 裂），拿掉後再找一次
LEAD_WORDS = ["那如果是", "那如果", "所以說", "那", "所以", "還有", "如果是"]
TAIL_WORDS = ["呢", "嗎", "咧", "啊", "啦", "喔", "?", "？"]
# 問「方法」的說法：是想查知識（例：手鐲怎麼挑），不是要直接推薦
HOW_WORDS = ["怎麼挑", "如何挑", "怎麼選", "如何選", "怎麼看", "要看什麼", "預算多少", "預算怎麼抓", "預算怎麼", "預算要多少"]
# 付款前檢查的說法
CHECK_WORDS = ["付款前", "避坑", "檢查清單", "怎麼避免被騙", "如何避免被騙", "不想被騙", "不被騙"]
# 導覽：分頁名稱和常見說法；NAV_WORDS 是「想移動」的詞
TAB_WORDS = {"新手入門": ["新手入門", "入門", "基礎"],
             "知識搜尋": ["知識搜尋", "搜尋"],
             "主題瀏覽": ["主題瀏覽", "主題", "分類"],
             "選款建議": ["選款建議", "選款"],
             "避坑清單": ["避坑清單", "避坑", "檢查清單"]}
NAV_WORDS = ["去", "到", "在哪", "打開", "開啟", "帶我", "前往", "看看", "怎麼找"]
# 想了解整個網站怎麼用的說法
GUIDE_WORDS = ["網站怎麼用", "怎麼使用", "有什麼功能", "網站導覽", "介紹網站", "介紹一下網站",
               "網站有什麼", "第一次來", "怎麼開始", "從哪裡開始"]
# 用途的常見說法，例：「生日」→ 紀念
USE_WORDS = {"日常配戴": ["日常", "平常", "上班戴", "上班時", "上班用", "自己戴"],
             "婚嫁": ["結婚", "婚嫁", "嫁妝", "婚戒"],
             "紀念": ["紀念", "生日", "畢業", "週年"],
             "祈福護身": ["祈福", "護身", "保平安", "平安"],
             "收藏": ["收藏", "投資"]}
# 常見說法：不是錯字，改錯字時跳過這些位置（例：「可以」不要被改成別的詞）
COMMON_WORDS = ["什麼", "怎麼", "可以", "是不", "不是", "這個", "那個", "有沒", "沒有", "如何",
                "為什", "為何", "應該", "一下", "比較", "請問", "我想", "想要", "知道", "要買",
                "想買", "送給", "大概", "多少", "左右", "好嗎", "可不", "能不", "會不", "是否",
                "哪裡", "哪個", "哪種", "手機", "今天", "明天", "昨天", "生日", "媽媽", "爸爸",
                "朋友", "老婆", "老公", "男生", "女生"]

# 閒聊題庫：smalltalk.csv（類別、關鍵詞、回答），用 Numbers 就能改，不用動程式
SMALLTALK_FILE = Path(__file__).parent / "smalltalk.csv"
# 奇怪問題題庫：weird.csv（類別、關鍵詞、回答、推薦題目），由上往下比對，越具體的類別放越前面
WEIRD_FILE = Path(__file__).parent / "weird.csv"
# 說法對照表：normalize.csv（類別、原本說法、換成），注音文、台語、英文、簡體字換成一般說法
NORMALIZE_FILE = Path(__file__).parent / "normalize.csv"

WELCOME = "您好！我是翠小二，翡翠的問題都可以問我，想挑款式我也可以帶您過去～"
# 下一步的按鈕：每次從熱門題目隨機挑 2 題，再加 1 個功能（見 start_options）
ACTIONS = ["幫我挑禮物", "付款前要注意什麼？", "網站怎麼用？"]
# 網站導覽：照新手的順序介紹 5 個分頁
GUIDE_TEXT = ("這個網站有 5 個分頁，建議照這個順序看：\n\n"
              "1. **新手入門**：先認識翡翠是什麼、怎麼看好壞\n"
              "2. **知識搜尋**：打關鍵字，找有參考資料的答案\n"
              "3. **主題瀏覽**：照分類，一次看完同一類的題目\n"
              "4. **選款建議**：選預算、品項、用途，看適合的款式照片\n"
              "5. **避坑清單**：付款前一項一項打勾確認\n\n"
              "想去哪一頁，點下面的按鈕我直接帶您過去～")
# 聽不懂、又不是翡翠問題時的回答（隨機挑一句；不說「很抱歉」，每次都給一個具體的問法）
OFF_TOPIC = ["這個方向我還沒研究過～我最擅長翡翠，例如「冰種是什麼」「B 貨怎麼分辨」，都可以問我！",
             "您考到我了！不過翡翠的事我很拿手，要不要從下面這幾題開始？",
             "這題超出我的專長了～換成翡翠的問題，我一定認真回答，例如「送長輩適合什麼翡翠」。",
             "我是只懂翡翠的翠小二，其他事情就幫不上忙了。想挑款式，也可以直接說「幫我挑禮物」喔！",
             "嗯……這個我答不出來，但我知道很多翡翠的冷知識！點下面的題目看看？"]
# 有提到翡翠，但知識卡還沒有答案時（已經記進查詢紀錄，之後補充）
NO_RESULT = ["這題問得好特別！我的知識卡還沒有剛好的答案，已經幫您記下來，之後會補充。先看看這幾題，說不定有您想知道的：",
             "好問題！不過這個我還沒有可靠的資料，不想亂回答您。這題已經記下來了，先從下面幾題看起吧：",
             "這個角度我還沒研究過～已經記進待補清單了。大家常問的這幾題，也許可以先參考：",
             "我還在努力長知識！這題先記下來。換成「手鐲」「B 貨」「種水」這類關鍵字問我，我會答得更好。先看看這些：",
             "這題考倒我了，不過不會放著不管：已經記下來，之後補上。要不要先從這幾題看起？"]
# 分數差不多、沒把握時，請使用者挑一題
ASK_BACK = ["我找到幾題相關的，您想看哪一題呢？",
            "這幾題都有可能，點一下我就詳細說明：",
            "您想問的是下面哪一題呢？"]
# 問到鑽石、珍珠這些非翡翠的東西
NOT_JADE = ["這個問題好像不是翡翠的範圍喔～我只回答翡翠的知識，例如「冰種是什麼」「B 貨怎麼分辨」。",
            "這個我不熟，我的專長只有翡翠！想比較的話，可以先看看翡翠的基本知識：",
            "其他寶石我就不班門弄斧了～翡翠的事倒是可以問我很多！"]
# 天馬行空的假設題（翡翠可以／會不會／能不能幫我…），知識卡又沒有明確答案時：先接住，再推薦相關題目
CREATIVE_WORDS = ["能不能幫", "可不可以幫", "可以幫我", "能幫我", "會不會", "能不能", "可不可以", "拿來", "拿去",
                  "當成", "讓我", "想把", "想用", "用翡翠", "會自己", "是不是在", "有沒有可能"]
CREATIVE = ["這題好有創意！翡翠沒有這種魔法，不過它是很耐看的寶石～下面這幾題可能跟您想知道的有關：",
            "這個想像我喜歡！翡翠本身是礦物，做不到這件事，但關於它的真實知識我很多，挑一題看看？",
            "哈，這題很有趣！翡翠的能力沒那麼神奇，不過它的故事和挑法都很精彩，從這幾題開始吧："]
# 沒有任何中文字（asdfgh、1111）或只有符號時的回答
KEYBOARD = ["嗯？這好像是鍵盤的祕密語言～可以用中文問我翡翠的問題，例如「A 貨是什麼」。",
            "收到一串神祕代碼！如果是想說預算，可以打「預算三萬」；想問知識，打「冰種是什麼」就可以了。"]

# %% 1. load_smalltalk() 讀閒聊題庫，整理成 [(關鍵詞清單, 回答清單), ...]

def load_smalltalk():
    talks = []
    with open(SMALLTALK_FILE, encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            words = row["關鍵詞"].split("｜")
            answers = row["回答"].split("｜")
            talks.append((words, answers))
    return talks

# %% 2. load_weird() 讀奇怪問題題庫，整理成 [(類別, 關鍵詞清單, 回答清單, 推薦題目清單), ...]

def load_weird():
    weird = []
    with open(WEIRD_FILE, encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            words = row["關鍵詞"].split("｜")
            answers = row["回答"].split("｜")
            options = row["推薦題目"].split("｜")
            weird.append((row["類別"], words, answers, options))
    return weird

# %% 3. load_normalize() 讀說法對照表，整理成 [(原本說法, 換成), ...]，長的放前面（ㄇㄞˇ 要比 ㄇ 先換）

def load_normalize():
    pairs = []
    with open(NORMALIZE_FILE, encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            for old in row["原本說法"].split("｜"):
                pairs.append((old, row["換成"]))
    pairs.sort(key=lambda pair: len(pair[0]), reverse=True)
    return pairs

# %% 4. load_synonyms() 讀同義詞對照表 {使用者說法: 標準說法}，例：{"手觸": "手鐲", "鐲子": "手鐲"}

def load_synonyms():
    jade_db = connect()
    words, synonyms = get_words(jade_db)
    jade_db.close()
    return synonyms

# %% 5. load_hot_questions() 讀熱門題目（jade_data 標「熱門」的卡），給按鈕隨機挑

def load_hot_questions():
    jade_db = connect()
    questions = []
    for card in hot_cards(jade_db):
        questions.append(card["question"])
    jade_db.close()
    return questions

# %% 6. start_options() 下一步的 3 個按鈕：熱門題目隨機 2 題＋功能 1 個，每次都不一樣

def start_options():
    options = random.sample(HOT_QUESTIONS, 2)
    options.append(random.choice(ACTIONS))
    return options


SMALLTALK = load_smalltalk()
WEIRD = load_weird()
NORMALIZE = load_normalize()
SYNONYMS = load_synonyms()
HOT_QUESTIONS = load_hot_questions()
# 詞 → 在知識卡出現的次數（改錯字時用；第一次需要時才算，見 count_words）
WORD_COUNT = {}

# %% 7. reply() 翠小二的入口：收到一句話，回傳要說的話和可以點的按鈕

def reply(text, jade_db):

    # 注音文、台語、英文、簡體字先換成一般說法（例：這ㄍ會不會是ㄐㄧㄚˇ的 → 這個會不會是假的）
    text = normalize(text)

    # 照原句回答一次；答得好就直接回傳
    answer = reply_once(text, jade_db)
    if not answer.get("failed"):
        return answer

    # 已經找到幾張相關的卡、只是沒把握（反問）→ 不是錯字，不要亂改
    if answer.get("ask"):
        return answer

    # 短的追問（那裂呢、棉多嗎）→ 拿掉前後的字再找一次
    core = strip_short(text)
    if core != text:
        again = reply_once(core, jade_db)
        if not again.get("failed") or again.get("ask"):
            return again

    # 答不好 → 可能是錯字，找找看有沒有可以改的字
    sentences, changes = fix_typo(text, jade_db)
    if len(changes) == 0:
        return answer

    # 有兩種改法 → 反問使用者是哪一句（例：墨綠 → 墨翠？深綠？）
    if len(sentences) > 1:
        return {"text": "您打的字我不太確定，是想問下面哪一句呢？", "options": sentences}

    # 用改好的句子再回答一次；還是答不好就用原本的回答
    second = reply_once(sentences[0], jade_db)
    if second.get("failed") and len(second.get("options", [])) == 0:
        return answer

    # 告訴使用者改了哪裡，例：（我猜您打的是 「冰鍾」→「冰種」）
    notes = []
    for wrong, right in changes:
        notes.append(f"「{wrong}」→「{right}」")
    second["text"] = "（我猜您打的是 " + "、".join(notes) + "）\n\n" + second["text"]
    return second

# %% 8. reply_once() 照意圖回答一次（reply 有錯字時會再呼叫一次）

def reply_once(text, jade_db):

    # 使用者點了按鈕上的知識卡題目（和題目一模一樣）→ 直接回答那張卡
    for card in all_cards(jade_db):
        if card["question"] == text:
            return card_reply(card, [])

    intent = find_intent(text)

    if intent == "weird":
        category, answers, options = find_weird(text)
        log_query(jade_db, text, 0, "機器人｜奇怪｜" + category)
        return {"text": random.choice(answers), "options": options}

    if intent == "restart":
        return {"text": "好的，重新開始。想問翡翠知識，還是要我幫您挑款式？",
                "options": start_options()}

    if intent == "smalltalk":
        log_query(jade_db, text, 0, "機器人｜閒聊")
        return {"text": find_smalltalk(text), "options": start_options()}

    if intent == "check":
        return {"text": "付款前建議逐項確認這 4 組：**證書**、**價格**、**店家**、**實物**。"
                        "到「避坑清單」分頁可以一項一項打勾確認。",
                "options": ["證書要看哪些地方？", "怎麼避免買到處理過的翡翠？"],
                "goto": {"tab": "避坑清單", "label": "到「避坑清單」逐項打勾"}}

    if intent == "guide":
        return {"text": GUIDE_TEXT,
                "options": ["去新手入門", "去知識搜尋", "去主題瀏覽", "去選款建議", "去避坑清單"]}

    # 帶路：auto＝不用再點按鈕，直接切到那一頁
    if intent == "nav":
        tab = find_tab(text)
        return {"text": f"好的，帶您到「{tab}」。",
                "goto": {"tab": tab, "label": f"前往「{tab}」"},
                "auto": True}

    if intent == "rec":
        return answer_rec(text, jade_db)

    # 查知識答不出來、但句子有想挑款式的意思（例：想送她上班戴的，會不會太招搖）→ 改帶去挑款式
    answer = answer_knowledge(text, jade_db)
    if answer.get("failed") and not answer.get("ask") and wants_rec(text):
        return answer_rec(text, jade_db)
    return answer


# strip_short() 短句（8 個字以內）拿掉開頭的「那、所以」和結尾的「呢、嗎」，例：那裂呢 → 裂
def strip_short(text):
    core = clean_text(text)
    if len(core) > 8:
        return text
    for word in LEAD_WORDS:
        if core.startswith(word):
            core = core[len(word):]
            break
    for word in TAIL_WORDS:
        if core.endswith(word):
            core = core[:-len(word)]
            break
    if core == "":
        return text
    return core


# wants_rec() 句子有沒有想挑款式的意思（強的詞，或弱的詞＋品項／用途／預算）
def wants_rec(text):
    for word in REC_STRONG:
        if word in text:
            return True
    for word in REC_WEAK:
        if word in text and has_condition(text):
            return True
    return False

# %% 9. find_intent() 判斷使用者想做什麼，回傳意圖的名字

def find_intent(text):

    # 想重新開始
    for word in ["重新開始", "重來", "取消"]:
        if word in text:
            return "restart"

    # 奇怪的問題（招財、咬咬看、放冰箱、亂碼…）→ 先用奇怪問題題庫接住
    if find_weird(text) is not None:
        return "weird"

    # 不是翡翠的問題（例：鑽石怎麼挑）→ 交給查知識，那邊會說「不是翡翠相關」
    if isnt_jade(clean_text(text)):
        return "knowledge"

    # 網站導覽、閒聊、帶路、付款前檢查
    for word in GUIDE_WORDS:
        if word in text:
            return "guide"
    if find_smalltalk(text) != "":
        return "smalltalk"
    if find_tab(text) != "":
        return "nav"
    for word in CHECK_WORDS:
        if word in text:
            return "check"

    # 問方法（手鐲怎麼挑）→ 查知識；想挑款式 → rec
    for word in HOW_WORDS:
        if word in text:
            return "knowledge"

    # 明確說要推薦、幫忙挑 → rec；沒說、但句子是在發問（會不會、是不是…嗎）→ 查知識
    # 例：「送媽媽的手鐲有一條小紋會不會不吉利」是問知識，不是要挑款式
    asked = text
    for word in OTHERS_RECOMMEND:
        asked = asked.replace(word, "")
    for word in REC_EXPLICIT:
        if word in asked:
            return "rec"
    for word in QUESTION_WORDS:
        if word in text:
            return "knowledge"
    for word in REC_STRONG:
        if word in text:
            return "rec"
    for word in REC_WEAK:
        if word in text and has_condition(text):
            return "rec"

    # 都不是：當成翡翠知識的問題
    return "knowledge"

# %% 10. find_smalltalk() 這句是不是閒聊？是的話回傳一句回答，不是就回傳空字串

def find_smalltalk(text):
    sentence = clean_text(text).lower()

    # 有提到翡翠、玉，或品項、用途、預算 → 正經問題，不當閒聊
    if "翡翠" in sentence or "玉" in sentence or has_condition(text):
        return ""

    # 太長的句子多半是在問問題
    if len(sentence) > 12:
        return ""

    # 由上往下比對題庫，找到就隨機挑一句回答
    for words, answers in SMALLTALK:
        for word in words:
            word = word.lower()
            if word.startswith("="):
                matched = (sentence == clean_text(word[1:]))
            else:
                matched = (word in sentence)
            if matched:
                return random.choice(answers)
    return ""

# %% 11. find_tab() 使用者想去哪個分頁？回傳分頁名稱，不是就回傳空字串

def find_tab(text):
    for tab, words in TAB_WORDS.items():
        for word in words:
            if word not in text:
                continue
            for move in NAV_WORDS:
                if move in text:
                    return tab
            if clean_text(text) == word:
                return tab
    return ""

# %% 12. find_condition() 從句子找出品項、用途、預算，回傳 {"item": …, "use": …, "budget": …}

def find_condition(text):
    condition = {"item": "", "use": "", "budget": ""}

    # 同義詞換成標準說法（手觸、鐲子 → 手鐲），才認得出品項
    for term, standard in SYNONYMS.items():
        if term in text and (standard in ITEMS or standard in OCCASIONS):
            text = text.replace(term, standard)

    # 品項
    for item in ITEMS:
        if item in text:
            condition["item"] = item

    # 用途（直接寫用途名稱，或常見說法）
    for use, words in USE_WORDS.items():
        if use in text:
            condition["use"] = use
        for word in words:
            if word in text:
                condition["use"] = use

    # 預算
    condition["budget"] = read_budget(text)
    return condition


# has_condition() 這句話有沒有提到品項、用途或預算（有一個就算）
def has_condition(text):
    condition = find_condition(text)
    if condition["item"] != "" or condition["use"] != "" or condition["budget"] != "":
        return True
    return False

# %% 13. read_budget() 從句子讀出預算，例：「一萬左右」→ 8,000–12,000、「三萬」→ 12,000–30,000

def read_budget(text):

    # 句子裡直接寫了選項（點按鈕的時候）
    for budget in BUDGETS:
        if budget in text:
            return budget

    # 中文數字換成阿拉伯數字（一萬 → 1萬）
    text = text.replace(",", "")
    numbers = {"一": "1", "兩": "2", "二": "2", "三": "3", "五": "5", "八": "8"}
    for chinese, digit in numbers.items():
        text = text.replace(chinese, digit)

    # 抓「數字＋單位」，例：「1萬」→ 1、萬
    match = re.search(r"(\d+\.?\d*)\s*(萬|千|k|K)?", text)
    if match is None:
        return ""
    money = float(match.group(1))
    unit = match.group(2)
    if unit == "萬":
        money = money * 10000
    elif unit == "千" or unit == "k" or unit == "K":
        money = money * 1000

    # 換成預算選項；太小（例：「2 個」）多半不是錢
    if money < 100:
        return ""
    if money < 8000:
        return BUDGETS[0]
    if money <= 12000:
        return BUDGETS[1]
    if money <= 30000:
        return BUDGETS[2]
    return BUDGETS[3]

# %% 14. answer_rec() 想挑款式 → 直接帶到「選款建議」分頁；句子裡看得出來的條件先幫忙選好

def answer_rec(text, jade_db):
    condition = find_condition(text)
    log_query(jade_db, text, 0, "機器人｜選款")

    # 已經知道的條件（句子裡說了，或前面點過的按鈕）
    got = []
    for name in ["item", "use", "budget"]:
        if condition[name] != "":
            got.append(condition[name])

    # 先在對話裡一個一個問：品項 → 用途 → 預算
    # 按鈕上的字會帶著已經選好的條件（例：「幫我挑：手鐲、紀念」），點了就會回到這裡繼續問下一個
    asks = [("item", ITEMS, "想挑哪一種飾品呢？"),
            ("use", OCCASIONS, "買來做什麼用呢？"),
            ("budget", BUDGETS, "預算大概多少呢？")]
    for name, choices, question in asks:
        if condition[name] == "":
            options = []
            for choice in choices:
                # 按鈕上的字固定照「品項、用途、預算」的順序（例：幫我挑：手鐲、紀念、8,000 以下）
                picked = dict(condition)
                picked[name] = choice
                parts = []
                for key in ["item", "use", "budget"]:
                    if picked[key] != "":
                        parts.append(picked[key])
                options.append("幫我挑：" + "、".join(parts))
            if len(got) == 0:
                lead = "好的！我先問您三個小問題，再帶您去看適合的款式。"
            else:
                lead = "收到～"
            return {"text": lead + question, "options": options}

    # 三個都知道了 → 帶到「選款建議」，條件幫忙選好（rec_item 這些是選單的 key）；auto＝直接跳過去
    fill = {"rec_item": condition["item"], "rec_use": condition["use"], "rec_budget": condition["budget"]}
    return {"text": f"好的！品項「{condition['item']}」、用途「{condition['use']}」、預算「{condition['budget']}」"
                    "都幫您選好了，帶您去看建議的款式～",
            "goto": {"tab": "選款建議", "label": "前往「選款建議」", "fill": fill},
            "auto": True}

# %% 15. answer_knowledge() 查知識：有把握就直接回答，沒把握就反問

def answer_knowledge(text, jade_db):
    result = search(text, jade_db=jade_db)
    log_query(jade_db, text, len(result["results"]), "機器人｜知識")

    # 不是翡翠的問題
    if result["status"] == "NOT_JADE":
        return {"text": random.choice(NOT_JADE),
                "options": ["A 貨是什麼？", "翡翠有幾種顏色？", "幫我挑禮物"]}

    # 句子裡沒有知識庫的詞：有提到翡翠（例：翡翠可以帶上飛機嗎）→ 老實說還沒有資料；
    # 完全沒提到翡翠（例：今天星期幾）→ 友善帶回翡翠話題
    no_terms = len(result["terms"]) == 0
    chat_only = result["status"] == "no_result" and result["terms"] == [clean_text(text)]
    if no_terms or chat_only:
        if mentions_jade(text) and is_creative(text):
            return {"text": random.choice(CREATIVE), "options": start_options()}
        if mentions_jade(text):
            return {"text": random.choice(NO_RESULT), "options": start_options(), "failed": True}
        return {"text": random.choice(OFF_TOPIC), "options": start_options(), "failed": True}

    # 有翡翠的詞，但找不到卡：天馬行空的假設題先接住；其他推薦熱門題目
    if result["status"] == "no_result":
        if is_creative(text):
            return {"text": random.choice(CREATIVE), "options": start_options()}
        return {"text": random.choice(NO_RESULT), "options": start_options(), "failed": True}

    # 第一名明顯領先 → 直接回答；只有一張卡也直接回答
    cards = result["results"]
    top, second = confidence(jade_db, text)
    if (top >= 2 and top > second) or len(cards) == 1:
        return card_reply(cards[0], cards[1:3])

    # 品項的詞（手鐲、吊墜…）很多卡都有，容易蓋過真正想問的詞（例：鐲子有裂 → 重點是「裂」）
    # 拿掉品項的詞再找一次，有把握就直接回答
    shorter = drop_items(text)
    if shorter != text:
        again = search(shorter, jade_db=jade_db)
        top, second = confidence(jade_db, shorter)
        if again["status"] == "ok" and top > second:
            return card_reply(again["results"][0], again["results"][1:3])

    # 分數差不多 → 反問，列出前三名讓使用者點（已經有相關的卡，不用「創意問題」的說法）
    options = []
    for card in cards[:3]:
        options.append(card["question"])
    return {"text": random.choice(ASK_BACK), "options": options, "failed": True, "ask": True}

# %% 16. confidence() 搜尋結果有多可靠：回傳第一名、第二名各命中幾個詞

def confidence(jade_db, text):
    terms = pick_terms(jade_db, text, "hybrid")

    # 同義詞和它的標準詞算同一個（例：送人、送禮 只算一次），不然會重複加分、誤以為很有把握
    concepts = []
    for term in terms:
        standard = SYNONYMS.get(term, term)
        if standard not in concepts:
            concepts.append(standard)
    if len(concepts) == 0:
        return 0, 0
    hits, best = score_cards(jade_db, concepts, "hybrid")
    counts = sorted(hits.values(), reverse=True)
    if len(counts) == 0:
        return 0, 0
    if len(counts) == 1:
        return counts[0], 0
    return counts[0], counts[1]

# %% 17. card_reply() 把一張知識卡變成翠小二的回答（答案＋選購提醒＋參考資料＋按鈕）

def card_reply(card, related):

    # 答案和選購提醒
    lines = [f"**{card['question']}**", "", card["answer"]]
    if card["caution"]:
        lines.append("")
        lines.append(f"➜ **選購提醒**：{card['caution']}")

    # 參考資料（最多列 2 筆）
    sources = []
    for source in card["sources"][:2]:
        sources.append(f"{source['id']}（{source['level']} 級）{source['name']}")

    # 下一步的按鈕：相關題目；沒有相關題目就給固定的兩個，對話才不會卡住
    options = []
    for other in related:
        options.append(other["question"])
    if len(options) == 0:
        options = ["幫我挑禮物", "付款前要注意什麼？"]

    # 導覽按鈕：帶到「主題瀏覽」，打開這張卡的分類
    goto = {"tab": "主題瀏覽", "label": f"看「{card['category']}」的所有題目",
            "fill": {"topic_pill": card["category"]}}
    return {"text": "\n".join(lines), "options": options, "goto": goto,
            "note": "參考資料：" + "；".join(sources) + f"｜知識卡 {card['id']}"}


# all_cards() 所有知識卡（使用者點了候選題目時，用題目找到那張卡）
def all_cards(jade_db):
    ids = []
    for row in jade_db.execute("SELECT id FROM knowledge"):
        ids.append(row["id"])
    return get_cards(jade_db, ids)

# %% 18. fix_typo() 找出錯字並改正，回傳（改好的句子清單, [(錯字, 正確的詞), ...]）

def fix_typo(text, jade_db):

    # 準備詞庫（知識卡關鍵字＋同義詞＋品項＋用途）
    words, synonyms = get_words(jade_db)
    vocabulary = set(words)
    for word in ITEMS + OCCASIONS + ["翡翠"]:
        vocabulary.add(word)
    count_words(jade_db, vocabulary)
    sentence = clean_text(text)

    # 已經認得的詞、常見說法的位置先記下來，這些位置不改
    covered = set()
    known = find_terms(sentence, vocabulary)
    for word in COMMON_WORDS:
        if word in sentence:
            known.append(word)
    for term in known:
        start = sentence.find(term)
        if start >= 0 and len(term) >= 2:
            for spot in range(start, start + len(term)):
                covered.add(spot)

    # 從長的片段（4 個字）找到短的（2 個字）
    changes = []
    for length in [4, 3, 2]:
        same_length = []
        for word in vocabulary:
            if len(word) == length:
                same_length.append(word)

        for start in range(len(sentence) - length + 1):
            piece = sentence[start:start + length]
            if piece in vocabulary:
                continue
            skip = False
            for spot in range(start, start + length):
                if spot in covered:
                    skip = True
            if skip:
                continue
            matches = one_char_off(piece, same_length)
            if len(matches) > 0:
                changes.append((piece, matches))
                for spot in range(start, start + length):
                    covered.add(spot)

    # 每個錯字先用最可能的詞改正
    fixed = sentence
    for wrong, matches in changes:
        fixed = fixed.replace(wrong, matches[0])

    # 有第二個可能的詞，另外做一句「另一種改法」讓使用者選
    sentences = [fixed]
    for wrong, matches in changes:
        if len(matches) > 1:
            sentences.append(fixed.replace(matches[0], matches[1]))
            break

    # 整理「改了哪些字」
    result = []
    for wrong, matches in changes:
        result.append((wrong, matches[0]))
    return sentences, result

# %% 19. one_char_off() 找「一樣長、同一個位置只差一個字」的詞，最多回傳 2 個

def one_char_off(piece, candidates):

    # 只留下和候選詞只差一個字的
    found = []
    for word in candidates:
        same = 0
        for i in range(len(piece)):
            if piece[i] == word[i]:
                same = same + 1
        if same == len(piece) - 1:
            found.append(word)
    if len(found) == 0:
        return []

    # 打錯字多半是「同音字」（注音選錯字），例：鍾／種、化／花、離／璃
    # 只改讀音一樣的；讀音不同多半不是錯字，而是本來就不在知識庫的詞（例：懷孕 ≠ 懷古），不要亂改
    same_sound = []
    for word in found:
        if lazy_pinyin(piece) == lazy_pinyin(word):
            same_sound.append(word)
    if len(same_sound) == 0:
        return []
    found = same_sound

    # 依在知識卡出現的次數排序（多的在前）
    ranking = []
    for word in found:
        ranking.append((-WORD_COUNT.get(word, 0), word))
    ranking.sort()
    best = [ranking[0][1]]

    # 第二名也很常出現（至少 2 次、而且有第一名的 3 成）→ 兩個都可能，一起回傳
    if len(ranking) > 1:
        first = -ranking[0][0]
        second = -ranking[1][0]
        if second >= 2 and second >= first * 0.3:
            best.append(ranking[1][1])
    return best


# count_words() 算每個詞在知識卡題目＋答案裡出現幾次，存進 WORD_COUNT（只算第一次）
def count_words(jade_db, vocabulary):
    if len(WORD_COUNT) > 0:
        return
    all_text = ""
    for row in jade_db.execute("SELECT question, answer FROM knowledge"):
        all_text = all_text + row["question"] + row["answer"]
    for word in vocabulary:
        WORD_COUNT[word] = all_text.count(word)

# %% 20. find_weird() 這句是不是奇怪的問題？是的話回傳（類別, 回答清單, 推薦題目），不是就回傳 None

def find_weird(text):
    sentence = clean_text(text).lower()

    # 由上往下比對題庫，找到就回傳那一類；「=」開頭的詞要整句一樣才算（例：=滾 不會抓到「泡滾水」）
    for category, words, answers, options in WEIRD:
        for word in words:
            if word.startswith("="):
                matched = (sentence == clean_text(word[1:]).lower())
            else:
                matched = (word.lower() in sentence)
            if matched:
                return (category, answers, options)

    # 題庫都沒比對到：沒有任何中文字（asdfgh、1111）或只剩符號 → 當成鍵盤測試
    chinese = 0
    for char in sentence:
        if "一" <= char <= "鿿":
            chinese = chinese + 1
    # 同一兩個字一直重複（啊啊啊啊啊啊）也當成鍵盤測試
    if (chinese == 0 and (len(sentence) >= 4 or sentence == "")) or (len(sentence) >= 6 and len(set(sentence)) <= 2 and not set(sentence) <= set("哈呵嗚耶")):
        return ("鍵盤亂碼", KEYBOARD, ["A 貨是什麼？", "幫我挑禮物", "網站怎麼用？"])
    return None


# %% 21. normalize() 把注音文、台語、英文、簡體字換成一般說法（對照表在 normalize.csv）

def normalize(text):
    sentence = text
    for old, new in NORMALIZE:
        if old.isascii():
            # 英文只換整個字，前後不能接英文字母（ring 不會換到 string 裡面）
            pattern = r"(?<![a-zA-Z])" + re.escape(old) + r"(?![a-zA-Z])"
            sentence = re.sub(pattern, new, sentence, flags=re.IGNORECASE)
        else:
            sentence = sentence.replace(old, new)

    # 對照表沒有的注音，把聲調符號拿掉
    for mark in ["ˊ", "ˇ", "ˋ", "˙", "ˉ"]:
        sentence = sentence.replace(mark, "")
    return sentence


# drop_items() 拿掉句子裡的品項詞（手鐲、鐲子、吊墜…），反問前再找一次用
def drop_items(text):
    words = list(ITEMS)
    for term, standard in SYNONYMS.items():
        if standard in ITEMS:
            words.append(term)
    words.sort(key=len, reverse=True)
    for word in words:
        text = text.replace(word, "")
    return text


# mentions_jade() 這句有沒有提到翡翠或翡翠飾品（有的話，答不出來時要說「還沒有資料」，不能說「其他事情幫不上忙」）
def mentions_jade(text):
    for word in ["翡翠", "玉", "手鐲", "鐲子", "手環", "平安扣", "吊墜", "墜子", "戒指", "戒面", "項鍊", "耳環", "手串"]:
        if word in text:
            return True
    return False


# is_creative() 這句是不是天馬行空的假設題（有「可以幫我、會不會、拿來當」這類說法）
def is_creative(text):
    for word in CREATIVE_WORDS:
        if word in text:
            return True
    return False

# %% 測試區：直接執行這支檔案，在終端機模擬對話

# 直接執行這支檔案，在終端機模擬對話
if __name__ == "__main__":
    jade_db = connect()
    questions = ["你好", "你是誰", "冰鍾是什麼", "想買手觸送媽媽生日", "手鐲", "帶我去避坑清單", "今天星期幾"]
    for question in questions:
        answer = reply(question, jade_db)
        print("問：", question)
        print("答：", answer["text"][:80].replace("\n", " "))
        print("按鈕：", answer.get("options", []))
        print()
