# -*- coding: utf-8 -*-
"""
一玉了然｜翠小二：翡翠問答機器人（bot.py）

原理和銀行、官網的客服機器人一樣：不自己生成答案，而是依規則判斷後回覆
    0. 先把注音文、台語、英文、簡體字換成一般說法（normalize.csv），例：ㄐㄧㄚˇ → 假、甘有影 → 是真的嗎
    1. 判斷意圖：閒聊、查知識、挑款式、付款前檢查、網站導覽、帶路到某個分頁
    2. 查知識 → 呼叫 search.py 的 search()，答案一定來自審核過的知識卡（有來源）
    3. 沒把握 → 反問「您想問的是下面哪一題呢？」，列出候選題目讓使用者點選
    4. 挑款式 → 依序詢問品項、用途、預算，再帶到「選款建議」分頁並預先選好
    5. 答不出來 → 檢查是否為錯字（只改同音字），改正後再找一次
    6. 奇怪的問題（招財、咬咬看、放冰箱、穿越…）→ 由 weird.csv 先回應，再推薦有根據的知識卡
    7. 真的答不出來 → 不說「很抱歉」，改推薦可以點選的題目，讓對話能繼續
    8. 每一句都記進 query_log，用來找出答不好的問題

這支程式只負責判斷和回答，不處理畫面；畫面在 app.py。
"""

import csv
import random
import re
from pathlib import Path
from pypinyin import lazy_pinyin
from recommend import BUDGETS, ITEMS, OCCASIONS
from search import clean_text, connect, contains_any, find_terms, get_cards, get_words, hot_cards
from search import isnt_jade, log_query, pick_terms, score_cards, search

# ── 判斷意圖用的詞 ──

# 想挑款式：強的詞一出現就算；弱的詞（送、買）還要搭配品項、用途或預算才算
REC_STRONG = ["推薦", "幫我挑", "幫我選", "挑禮物", "送禮", "禮物", "預算",
              "選什麼款", "什麼款式", "挑款式", "選款式", "哪種款", "哪個款式", "選哪款", "挑哪款"]
REC_WEAK = ["送", "買給", "想買", "要買", "挑", "選哪", "選什麼", "適合"]

# 明確要求推薦、幫忙挑選（一出現就帶去挑款式）
REC_EXPLICIT = ["推薦", "幫我挑", "幫我選", "挑禮物", "選什麼款", "什麼款式", "挑款式", "選款式",
                "哪種款", "哪個款式", "選哪款", "挑哪款"]

# 發問的說法：句子裡有這些、又沒有明確要求推薦 → 視為詢問知識
QUESTION_WORDS = ["嗎", "是不是", "會不會", "算不算", "要不要", "能不能", "可不可以", "夠不夠",
                  "還是", "有什麼", "哪幾", "什麼意思", "差很多", "講究", "幾公斤",
                  "怎麼", "差別", "有沒有差", "差在哪", "哪一點", "先看", "一般", "多少的"]

# 別人的推薦（店員推薦…）不是要翠小二推薦，判斷意圖前先去掉
OTHERS_RECOMMEND = ["店員推薦", "老闆推薦", "店家推薦", "朋友推薦", "銷售推薦", "櫃姐推薦"]

# 詢問「方法」：是查知識（例：手鐲怎麼挑），不是要直接推薦
HOW_WORDS = ["怎麼挑", "如何挑", "怎麼選", "如何選", "怎麼看", "要看什麼", "預算多少", "預算怎麼抓", "預算怎麼", "預算要多少"]

# 付款前檢查
CHECK_WORDS = ["付款前", "避坑", "檢查清單", "怎麼避免被騙", "如何避免被騙", "不想被騙", "不被騙"]

# 想了解整個網站怎麼用
GUIDE_WORDS = ["網站怎麼用", "怎麼使用", "有什麼功能", "網站導覽", "介紹網站", "介紹一下網站",
               "網站有什麼", "第一次來", "怎麼開始", "從哪裡開始"]

# 重新開始對話
RESTART_WORDS = ["重新開始", "重來", "取消"]

# 導覽：分頁名稱與常見說法；NAV_WORDS 是表示「想移動」的詞
TAB_WORDS = {"新手入門": ["新手入門", "入門", "基礎"],
             "知識搜尋": ["知識搜尋", "搜尋"],
             "主題瀏覽": ["主題瀏覽", "主題", "分類"],
             "選款建議": ["選款建議", "選款"],
             "避坑清單": ["避坑清單", "避坑", "檢查清單"]}
NAV_WORDS = ["去", "到", "在哪", "打開", "開啟", "帶我", "前往", "看看", "怎麼找"]

# 用途的常見說法，例：「生日」→ 紀念
USE_WORDS = {"日常配戴": ["日常", "平常", "上班戴", "上班時", "上班用", "自己戴"],
             "婚嫁": ["結婚", "婚嫁", "嫁妝", "婚戒"],
             "紀念": ["紀念", "生日", "畢業", "週年"],
             "祈福護身": ["祈福", "護身", "保平安", "平安"],
             "收藏": ["收藏", "投資"]}

# 提到這些詞代表在問翡翠（答不出來時要說「還沒有資料」，而不是「其他事情幫不上忙」）
JADE_ITEM_WORDS = ["翡翠", "玉", "手鐲", "鐲子", "手環", "平安扣", "吊墜", "墜子", "戒指", "戒面", "項鍊", "耳環", "手串"]

# 天馬行空的假設題（翡翠可以／會不會／能不能幫我…）
CREATIVE_WORDS = ["能不能幫", "可不可以幫", "可以幫我", "能幫我", "會不會", "能不能", "可不可以", "拿來", "拿去",
                  "當成", "讓我", "想把", "想用", "用翡翠", "會自己", "是不是在", "有沒有可能"]

# ── 句子整理用的詞 ──

# 短的追問前後常加的字（那裂呢 → 裂），去掉後再找一次
LEAD_WORDS = ["那如果是", "那如果", "所以說", "那", "所以", "還有", "如果是"]
TAIL_WORDS = ["呢", "嗎", "咧", "啊", "啦", "喔", "?", "？"]

# 句尾語助詞：整句比對時「是真的嗎啊」視為「是真的嗎」
PARTICLES = "啊呢喔哦耶啦吧呀嘛欸囉了唷"

# 常見說法不是錯字，改錯字時跳過這些位置（例：「可以」不會被改成別的詞）
COMMON_WORDS = ["什麼", "怎麼", "可以", "是不", "不是", "這個", "那個", "有沒", "沒有", "如何",
                "為什", "為何", "應該", "一下", "比較", "請問", "我想", "想要", "知道", "要買",
                "想買", "送給", "大概", "多少", "左右", "好嗎", "可不", "能不", "會不", "是否",
                "哪裡", "哪個", "哪種", "手機", "今天", "明天", "昨天", "生日", "媽媽", "爸爸",
                "朋友", "老婆", "老公", "男生", "女生"]

# ── 題庫檔案（用 Excel／Numbers 就能修改，不需要改程式）──

SMALLTALK_FILE = Path(__file__).parent / "smalltalk.csv"     # 閒聊：類別、關鍵詞、回答
WEIRD_FILE = Path(__file__).parent / "weird.csv"             # 奇怪問題：類別、關鍵詞、回答、推薦題目（由上往下比對）
NORMALIZE_FILE = Path(__file__).parent / "normalize.csv"     # 說法對照：類別、原本說法、換成

# ── 回覆文字 ──

WELCOME = "您好！我是翠小二，翡翠的問題都可以問我，想挑款式我也可以帶您過去～"

# 對話中固定提供的功能按鈕（start_options 每次隨機挑 1 個）
ACTIONS = ["幫我挑禮物", "付款前要注意什麼？", "網站怎麼用？"]

# 網站導覽：依新手順序介紹 5 個分頁
GUIDE_TEXT = ("這個網站有 5 個分頁，建議照這個順序看：\n\n"
              "1. **新手入門**：先認識翡翠是什麼、怎麼看好壞\n"
              "2. **知識搜尋**：打關鍵字，找有參考資料的答案\n"
              "3. **主題瀏覽**：照分類，一次看完同一類的題目\n"
              "4. **選款建議**：選預算、品項、用途，看適合的款式照片\n"
              "5. **避坑清單**：付款前一項一項打勾確認\n\n"
              "想去哪一頁，點下面的按鈕我直接帶您過去～")

# 聽不懂、又不是翡翠問題（隨機挑一句；不說「很抱歉」，並提供具體的問法）
OFF_TOPIC = ["這個方向我還沒研究過～我最擅長翡翠，例如「冰種是什麼」「B 貨怎麼分辨」，都可以問我！",
             "您考到我了！不過翡翠的事我很拿手，要不要從下面這幾題開始？",
             "這題超出我的專長了～換成翡翠的問題，我一定認真回答，例如「送長輩適合什麼翡翠」。",
             "我是只懂翡翠的翠小二，其他事情就幫不上忙了。想挑款式，也可以直接說「幫我挑禮物」喔！",
             "嗯……這個我答不出來，但我知道很多翡翠的冷知識！點下面的題目看看？"]

# 有提到翡翠，但知識卡還沒有答案（已記錄到查詢紀錄，之後補充）
NO_RESULT = ["這題問得好特別！我的知識卡還沒有剛好的答案，已經幫您記下來，之後會補充。先看看這幾題，說不定有您想知道的：",
             "好問題！不過這個我還沒有可靠的資料，不想亂回答您。這題已經記下來了，先從下面幾題看起吧：",
             "這個角度我還沒研究過～已經記進待補清單了。大家常問的這幾題，也許可以先參考：",
             "我還在努力長知識！這題先記下來。換成「手鐲」「B 貨」「種水」這類關鍵字問我，我會答得更好。先看看這些：",
             "這題考倒我了，不過不會放著不管：已經記下來，之後補上。要不要先從這幾題看起？"]

# 分數差不多、沒有把握時，請使用者挑一題
ASK_BACK = ["我找到幾題相關的，您想看哪一題呢？",
            "這幾題都有可能，點一下我就詳細說明：",
            "您想問的是下面哪一題呢？"]

# 問到鑽石、珍珠等非翡翠的東西
NOT_JADE = ["這個問題好像不是翡翠的範圍喔～我只回答翡翠的知識，例如「冰種是什麼」「B 貨怎麼分辨」。",
            "這個我不熟，我的專長只有翡翠！想比較的話，可以先看看翡翠的基本知識：",
            "其他寶石我就不班門弄斧了～翡翠的事倒是可以問我很多！"]

# 天馬行空的假設題，知識卡又沒有明確答案時：先回應，再推薦相關題目
CREATIVE = ["這題好有創意！翡翠沒有這種魔法，不過它是很耐看的寶石～下面這幾題可能跟您想知道的有關：",
            "這個想像我喜歡！翡翠本身是礦物，做不到這件事，但關於它的真實知識我很多，挑一題看看？",
            "哈，這題很有趣！翡翠的能力沒那麼神奇，不過它的故事和挑法都很精彩，從這幾題開始吧："]

# 沒有任何中文字（asdfgh、1111）或只有符號
KEYBOARD = ["嗯？這好像是鍵盤的祕密語言～可以用中文問我翡翠的問題，例如「A 貨是什麼」。",
            "收到一串神祕代碼！如果是想說預算，可以打「預算三萬」；想問知識，打「冰種是什麼」就可以了。"]
KEYBOARD_OPTIONS = ["A 貨是什麼？", "幫我挑禮物", "網站怎麼用？"]

# %% 1. load_smalltalk() 讀閒聊題庫：[(關鍵詞清單, 回答清單), ...]

def load_smalltalk():
    talks = []
    with open(SMALLTALK_FILE, encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            talks.append((row["關鍵詞"].split("｜"), row["回答"].split("｜")))
    return talks

# %% 2. load_weird() 讀奇怪問題題庫：[(類別, 關鍵詞清單, 回答清單, 推薦題目清單), ...]

def load_weird():
    weird = []
    with open(WEIRD_FILE, encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            words = row["關鍵詞"].split("｜")
            answers = row["回答"].split("｜")
            options = row["推薦題目"].split("｜")
            weird.append((row["類別"], words, answers, options))
    return weird

# %% 3. load_normalize() 讀說法對照表：[(原本說法, 換成), ...]；長的排前面（ㄇㄞˇ 要比 ㄇ 先換）

def load_normalize():
    pairs = []
    with open(NORMALIZE_FILE, encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            for old in row["原本說法"].split("｜"):
                pairs.append((old, row["換成"]))
    pairs.sort(key=lambda pair: len(pair[0]), reverse=True)
    return pairs

# %% 4. load_synonyms() 讀同義詞對照表：{使用者說法: 標準說法}，例：{"鐲子": "手鐲"}

def load_synonyms():
    jade_db = connect()
    words, synonyms = get_words(jade_db)
    jade_db.close()
    return synonyms

# %% 5. load_hot_questions() 讀熱門題目（jade_data 標記「熱門」的卡片）

def load_hot_questions():
    jade_db = connect()
    questions = []
    for card in hot_cards(jade_db):
        questions.append(card["question"])
    jade_db.close()
    return questions


# 程式啟動時讀一次，之後重複使用
SMALLTALK = load_smalltalk()
WEIRD = load_weird()
NORMALIZE = load_normalize()
SYNONYMS = load_synonyms()
HOT_QUESTIONS = load_hot_questions()

# 詞 → 在知識卡出現的次數（改錯字時排序用；第一次需要時才計算，見 count_words）
WORD_COUNT = {}

# %% 6. start_options() 下一步的 3 個按鈕：熱門題目隨機 2 題＋功能 1 個

def start_options():
    options = random.sample(HOT_QUESTIONS, 2)
    options.append(random.choice(ACTIONS))
    return options

# %% 7. reply() 翠小二的入口：收到一句話，回傳要說的話和可以點選的按鈕

def reply(text, jade_db):

    # 注音文、台語、英文、簡體字先換成一般說法（例：這ㄍ會不會是ㄐㄧㄚˇ的 → 這個會不會是假的）
    text = normalize(text)

    # 用原句回答一次；成功就直接回傳
    answer = reply_once(text, jade_db)
    if not answer.get("failed"):
        return answer

    # 已經找到相關的卡、只是沒有把握（反問）→ 不是錯字，不需要改字
    if answer.get("ask"):
        return answer

    # 短的追問（那裂呢、棉多嗎）→ 去掉前後的字再找一次
    core = strip_short(text)
    if core != text:
        again = reply_once(core, jade_db)
        if not again.get("failed") or again.get("ask"):
            return again

    # 仍然答不好 → 檢查是否有錯字
    sentences, changes = fix_typo(text, jade_db)
    if len(changes) == 0:
        return answer

    # 有兩種改法 → 請使用者選（例：墨綠 → 墨翠？深綠？）
    if len(sentences) > 1:
        return {"text": "您打的字我不太確定，是想問下面哪一句呢？", "options": sentences}

    # 用改好的句子再回答一次；還是答不好就沿用原本的回答
    second = reply_once(sentences[0], jade_db)
    if second.get("failed") and len(second.get("options", [])) == 0:
        return answer

    # 告訴使用者改了哪裡，例：（我猜您打的是 「冰鍾」→「冰種」）
    notes = []
    for wrong, right in changes:
        notes.append(f"「{wrong}」→「{right}」")
    second["text"] = "（我猜您打的是 " + "、".join(notes) + "）\n\n" + second["text"]
    return second

# %% 8. reply_once() 依意圖回答一次（reply 改錯字後會再呼叫一次）

def reply_once(text, jade_db):

    # 使用者點了知識卡題目的按鈕（與題目完全相同）→ 直接回答那張卡
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

    # 帶路：auto 表示不必再點按鈕，直接切換到那一頁
    if intent == "nav":
        tab = find_tab(text)
        return {"text": f"好的，帶您到「{tab}」。",
                "goto": {"tab": tab, "label": f"前往「{tab}」"},
                "auto": True}

    if intent == "rec":
        return answer_rec(text, jade_db)

    # 查知識答不出來，但句子有挑款式的意思（例：想送她上班戴的，會不會太招搖）→ 改帶去挑款式
    answer = answer_knowledge(text, jade_db)
    if answer.get("failed") and not answer.get("ask") and wants_rec(text):
        return answer_rec(text, jade_db)
    return answer

# %% 9. find_intent() 判斷使用者想做什麼，回傳意圖名稱

def find_intent(text):

    if contains_any(text, RESTART_WORDS):
        return "restart"

    # 奇怪的問題（招財、咬咬看、放冰箱、亂碼…）優先由奇怪問題題庫回應
    if find_weird(text) is not None:
        return "weird"

    # 非翡翠問題（例：鑽石怎麼挑）交給查知識，由那裡回覆「不是翡翠的範圍」
    if isnt_jade(clean_text(text)):
        return "knowledge"

    if contains_any(text, GUIDE_WORDS):
        return "guide"
    if find_smalltalk(text) != "":
        return "smalltalk"
    if find_tab(text) != "":
        return "nav"
    if contains_any(text, CHECK_WORDS):
        return "check"

    # 詢問方法（手鐲怎麼挑）→ 查知識
    if contains_any(text, HOW_WORDS):
        return "knowledge"

    # 明確要求推薦 → 挑款式；沒有明確要求、但句子是在發問（會不會、是不是…嗎）→ 查知識
    # 例：「送媽媽的手鐲有一條小紋會不會不吉利」是問知識，不是要挑款式
    asked = text
    for word in OTHERS_RECOMMEND:
        asked = asked.replace(word, "")
    if contains_any(asked, REC_EXPLICIT):
        return "rec"
    if contains_any(text, QUESTION_WORDS):
        return "knowledge"
    if wants_rec(text):
        return "rec"

    # 以上都不是：當成翡翠知識的問題
    return "knowledge"

# %% 10. wants_rec() 句子是否有挑款式的意思（強的詞，或弱的詞＋品項／用途／預算）

def wants_rec(text):
    if contains_any(text, REC_STRONG):
        return True
    if contains_any(text, REC_WEAK) and has_condition(text):
        return True
    return False

# %% 11. strip_short() 短句（8 個字以內）去掉開頭的「那、所以」和結尾的「呢、嗎」，例：那裂呢 → 裂

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

# %% 12. drop_particles() 去掉句尾語助詞（啊、呢、喔、耶…）

def drop_particles(sentence):
    while len(sentence) > 1 and sentence[-1] in PARTICLES:
        sentence = sentence[:-1]
    return sentence

# %% 13. word_matches() 題庫的詞是否符合這句話；「=」開頭的詞要整句相同才算（例：=滾 不會抓到「泡滾水」）
# sentence 已轉成小寫，題庫的詞也統一轉小寫後再比（=nice 才能比對到 nice）

def word_matches(word, sentence):
    if word.startswith("="):
        return drop_particles(sentence) == drop_particles(clean_text(word[1:]).lower())
    return word.lower() in sentence

# %% 14. find_smalltalk() 是否為閒聊；是的話回傳一句回答，不是就回傳空字串

def find_smalltalk(text):
    sentence = clean_text(text).lower()

    # 提到翡翠、玉，或品項、用途、預算 → 是正經問題，不當閒聊
    if "翡翠" in sentence or "玉" in sentence or has_condition(text):
        return ""

    # 較長的句子多半是在問問題
    if len(sentence) > 12:
        return ""

    # 由上往下比對題庫，找到就隨機挑一句回答
    for words, answers in SMALLTALK:
        for word in words:
            if word_matches(word, sentence):
                return random.choice(answers)
    return ""

# %% 15. find_tab() 使用者想去哪個分頁；不是就回傳空字串

def find_tab(text):
    for tab, words in TAB_WORDS.items():
        for word in words:
            if word not in text:
                continue
            # 提到分頁名稱，而且有「想移動」的詞，或整句就是分頁名稱
            if contains_any(text, NAV_WORDS) or clean_text(text) == word:
                return tab
    return ""

# %% 16. find_condition() 從句子找出品項、用途、預算：{"item": …, "use": …, "budget": …}

def find_condition(text):
    condition = {"item": "", "use": "", "budget": ""}

    # 先把同義詞換成標準說法（鐲子 → 手鐲），才認得出品項與用途
    for term, standard in SYNONYMS.items():
        if term in text and (standard in ITEMS or standard in OCCASIONS):
            text = text.replace(term, standard)

    for item in ITEMS:
        if item in text:
            condition["item"] = item

    # 用途：直接寫用途名稱，或是常見說法
    for use, words in USE_WORDS.items():
        if use in text or contains_any(text, words):
            condition["use"] = use

    condition["budget"] = read_budget(text)
    return condition

# %% 17. has_condition() 句子是否提到品項、用途或預算（任一個就算）

def has_condition(text):
    condition = find_condition(text)
    return condition["item"] != "" or condition["use"] != "" or condition["budget"] != ""

# %% 18. read_budget() 從句子讀出預算，例：「一萬左右」→ 8,000–12,000、「三萬」→ 12,000–30,000

def read_budget(text):

    # 句子裡直接寫了選項（點按鈕時）
    for budget in BUDGETS:
        if budget in text:
            return budget

    # 中文數字換成阿拉伯數字（一萬 → 1萬）
    text = text.replace(",", "")
    numbers = {"一": "1", "兩": "2", "二": "2", "三": "3", "五": "5", "八": "8"}
    for chinese, digit in numbers.items():
        text = text.replace(chinese, digit)

    # 找出「數字＋單位」，例：「1萬」→ 1、萬
    match = re.search(r"(\d+\.?\d*)\s*(萬|千|k|K)?", text)
    if match is None:
        return ""
    money = float(match.group(1))
    unit = match.group(2)
    if unit == "萬":
        money = money * 10000
    elif unit == "千" or unit == "k" or unit == "K":
        money = money * 1000

    # 對應到預算選項；金額太小（例：「2 個」）多半不是錢
    if money < 100:
        return ""
    if money < 8000:
        return BUDGETS[0]
    if money <= 12000:
        return BUDGETS[1]
    if money <= 30000:
        return BUDGETS[2]
    return BUDGETS[3]

# %% 19. rec_button() 挑款式按鈕的文字，條件固定依「品項、用途、預算」排列（例：幫我挑：手鐲、紀念）

def rec_button(condition, name, choice):
    picked = dict(condition)
    picked[name] = choice
    parts = []
    for key in ["item", "use", "budget"]:
        if picked[key] != "":
            parts.append(picked[key])
    return "幫我挑：" + "、".join(parts)

# %% 20. answer_rec() 挑款式：依序詢問品項 → 用途 → 預算，三個都有了再帶到「選款建議」

def answer_rec(text, jade_db):
    condition = find_condition(text)
    log_query(jade_db, text, 0, "機器人｜選款")

    # 已經知道的條件（句子裡提到的，或前面點過的按鈕）
    got = []
    for name in ["item", "use", "budget"]:
        if condition[name] != "":
            got.append(condition[name])

    # 按鈕文字帶著已選好的條件，點了會回到這裡繼續問下一個
    asks = [("item", ITEMS, "想挑哪一種飾品呢？"),
            ("use", OCCASIONS, "買來做什麼用呢？"),
            ("budget", BUDGETS, "預算大概多少呢？")]
    for name, choices, question in asks:
        if condition[name] != "":
            continue
        options = []
        for choice in choices:
            options.append(rec_button(condition, name, choice))
        if len(got) == 0:
            lead = "好的！我先問您三個小問題，再帶您去看適合的款式。"
        else:
            lead = "收到～"
        return {"text": lead + question, "options": options}

    # 三個條件都有了：提供前往「選款建議」的按鈕並預先選好（rec_item 等是選單的 key）
    # 不自動切換分頁，讓使用者看完訊息再點
    fill = {"rec_item": condition["item"], "rec_use": condition["use"], "rec_budget": condition["budget"]}
    return {"text": f"好的！品項「{condition['item']}」、用途「{condition['use']}」、預算「{condition['budget']}」"
                    "都幫您選好了，點下面的按鈕看建議的款式～",
            "goto": {"tab": "選款建議", "label": "前往「選款建議」", "fill": fill}}

# %% 21. answer_knowledge() 查知識：有把握就直接回答，沒把握就反問

def answer_knowledge(text, jade_db):
    result = search(text, jade_db=jade_db)
    log_query(jade_db, text, len(result["results"]), "機器人｜知識")

    if result["status"] == "NOT_JADE":
        return {"text": random.choice(NOT_JADE),
                "options": ["A 貨是什麼？", "翡翠有幾種顏色？", "幫我挑禮物"]}

    # 句子裡沒有知識庫的詞：
    #   提到翡翠（例：翡翠可以帶上飛機嗎）→ 說明目前還沒有資料
    #   完全沒提到翡翠（例：今天星期幾）→ 把話題帶回翡翠
    no_terms = len(result["terms"]) == 0
    chat_only = result["status"] == "no_result" and result["terms"] == [clean_text(text)]
    if no_terms or chat_only:
        if mentions_jade(text) and is_creative(text):
            return {"text": random.choice(CREATIVE), "options": start_options()}
        if mentions_jade(text):
            return {"text": random.choice(NO_RESULT), "options": start_options(), "failed": True}
        return {"text": random.choice(OFF_TOPIC), "options": start_options(), "failed": True}

    # 有知識庫的詞，但找不到卡：假設題先回應，其他推薦熱門題目
    if result["status"] == "no_result":
        if is_creative(text):
            return {"text": random.choice(CREATIVE), "options": start_options()}
        return {"text": random.choice(NO_RESULT), "options": start_options(), "failed": True}

    # 第一名明顯領先，或只有一張卡 → 直接回答
    cards = result["results"]
    top, second = confidence(jade_db, text)
    if (top >= 2 and top > second) or len(cards) == 1:
        return card_reply(cards[0], cards[1:3])

    # 品項詞（手鐲、吊墜…）很多卡都有，容易蓋過真正想問的詞（例：鐲子有裂 → 重點是「裂」）
    # 去掉品項詞再找一次，有把握就直接回答
    shorter = drop_items(text)
    if shorter != text:
        again = search(shorter, jade_db=jade_db)
        top, second = confidence(jade_db, shorter)
        if again["status"] == "ok" and top > second:
            return card_reply(again["results"][0], again["results"][1:3])

    # 分數接近 → 列出前三名請使用者選
    options = []
    for card in cards[:3]:
        options.append(card["question"])
    return {"text": random.choice(ASK_BACK), "options": options, "failed": True, "ask": True}

# %% 22. confidence() 搜尋結果的可靠程度：回傳第一名、第二名各命中幾個詞

def confidence(jade_db, text):
    terms = pick_terms(jade_db, text, "hybrid")

    # 同義詞和標準詞算同一個（例：送人、送禮只算一次），避免重複計分而誤判為很有把握
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

# %% 23. card_reply() 把一張知識卡組成翠小二的回答（答案＋選購提醒＋參考資料＋按鈕）

def card_reply(card, related):
    lines = [f"**{card['question']}**", "", card["answer"]]
    if card["caution"]:
        lines.append("")
        lines.append(f"➜ **選購提醒**：{card['caution']}")

    # 參考資料最多列 2 筆
    sources = []
    for source in card["sources"][:2]:
        sources.append(f"{source['id']}（{source['level']} 級）{source['name']}")

    # 下一步按鈕：相關題目；沒有相關題目時提供固定的兩個，讓對話能繼續
    options = []
    for other in related:
        options.append(other["question"])
    if len(options) == 0:
        options = ["幫我挑禮物", "付款前要注意什麼？"]

    # 導覽按鈕：帶到「主題瀏覽」並打開這張卡的分類
    goto = {"tab": "主題瀏覽", "label": f"看「{card['category']}」的所有題目",
            "fill": {"topic_pill": card["category"]}}
    return {"text": "\n".join(lines), "options": options, "goto": goto,
            "note": "參考資料：" + "；".join(sources) + f"｜知識卡 {card['id']}"}

# %% 24. all_cards() 所有知識卡（使用者點了候選題目時，用題目找回那張卡）

def all_cards(jade_db):
    ids = []
    for row in jade_db.execute("SELECT id FROM knowledge"):
        ids.append(row["id"])
    return get_cards(jade_db, ids)

# %% 25. fix_typo() 找出錯字並改正，回傳（改好的句子清單, [(錯字, 正確的詞), ...]）

def fix_typo(text, jade_db):

    # 詞庫：知識卡關鍵字＋同義詞＋品項＋用途
    words, synonyms = get_words(jade_db)
    vocabulary = set(words)
    for word in ITEMS + OCCASIONS + ["翡翠"]:
        vocabulary.add(word)
    count_words(jade_db, vocabulary)
    sentence = clean_text(text)

    # 已經認得的詞、常見說法所在的位置不改
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

    # 從長的片段（4 個字）檢查到短的（2 個字）
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
            spots = range(start, start + length)
            if is_covered(spots, covered):
                continue
            matches = one_char_off(piece, same_length)
            if len(matches) > 0:
                changes.append((piece, matches))
                for spot in spots:
                    covered.add(spot)

    # 每個錯字先改成最可能的詞
    fixed = sentence
    for wrong, matches in changes:
        fixed = fixed.replace(wrong, matches[0])

    # 有第二個可能的詞時，另外產生一句讓使用者選
    sentences = [fixed]
    for wrong, matches in changes:
        if len(matches) > 1:
            sentences.append(fixed.replace(matches[0], matches[1]))
            break

    result = []
    for wrong, matches in changes:
        result.append((wrong, matches[0]))
    return sentences, result

# %% 26. is_covered() 這些位置中，是否有任何一個已經被認得的詞占用

def is_covered(spots, covered):
    for spot in spots:
        if spot in covered:
            return True
    return False

# %% 27. one_char_off() 找出「一樣長、只差一個字、讀音相同」的詞，最多回傳 2 個

def one_char_off(piece, candidates):

    # 只差一個字
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

    # 打錯字多半是同音字（注音選錯字），例：鍾／種、化／花、離／璃
    # 讀音不同的多半不是錯字，而是知識庫本來就沒有的詞（例：懷孕 ≠ 懷古），不更改
    same_sound = []
    for word in found:
        if lazy_pinyin(piece) == lazy_pinyin(word):
            same_sound.append(word)
    if len(same_sound) == 0:
        return []

    # 依在知識卡出現的次數排序（多的在前）
    ranking = []
    for word in same_sound:
        ranking.append((-WORD_COUNT.get(word, 0), word))
    ranking.sort()
    best = [ranking[0][1]]

    # 第二名也常出現（至少 2 次，且達第一名的 3 成）→ 兩個都可能，一起回傳
    if len(ranking) > 1:
        first = -ranking[0][0]
        second = -ranking[1][0]
        if second >= 2 and second >= first * 0.3:
            best.append(ranking[1][1])
    return best

# %% 28. count_words() 計算每個詞在知識卡題目＋答案出現幾次，存進 WORD_COUNT（只算一次）

def count_words(jade_db, vocabulary):
    if len(WORD_COUNT) > 0:
        return
    all_text = ""
    for row in jade_db.execute("SELECT question, answer FROM knowledge"):
        all_text = all_text + row["question"] + row["answer"]
    for word in vocabulary:
        WORD_COUNT[word] = all_text.count(word)

# %% 29. count_chinese() 句子裡有幾個中文字

def count_chinese(sentence):
    chinese = 0
    for char in sentence:
        if "一" <= char <= "鿿":  # 中文字的範圍（Unicode 4E00～9FFF）
            chinese = chinese + 1
    return chinese

# %% 30. is_keyboard_noise() 是否像隨手亂打：沒有中文字（asdfgh、1111）、只有符號，或一兩個字一直重複（啊啊啊啊啊啊）

def is_keyboard_noise(sentence):
    no_chinese = count_chinese(sentence) == 0 and (len(sentence) >= 4 or sentence == "")
    repeated = len(sentence) >= 6 and len(set(sentence)) <= 2 and not set(sentence) <= set("哈呵嗚耶")
    return no_chinese or repeated

# %% 31. in_smalltalk() 這句是否符合閒聊題庫的任何一個說法（只判斷，不挑回答）

def in_smalltalk(sentence):
    if sentence == "":                          # 只有標點或空白的句子，整理後是空字串，不算閒聊
        return False
    for words, answers in SMALLTALK:
        for word in words:
            if word_matches(word, sentence):
                return True
    return False

# %% 32. find_weird() 是否為奇怪的問題；是的話回傳（類別, 回答清單, 推薦題目），不是就回傳 None

def find_weird(text):
    sentence = clean_text(text).lower()

    # 由上往下比對題庫，找到就回傳那一類
    for category, words, answers, options in WEIRD:
        for word in words:
            if word_matches(word, sentence):
                return (category, answers, options)

    # 題庫都沒比對到，再判斷是不是隨手亂打（閒聊題庫裡的英文，例如 nice、sorry，不算亂打）
    if is_keyboard_noise(sentence) and not in_smalltalk(sentence):
        return ("鍵盤亂碼", KEYBOARD, list(KEYBOARD_OPTIONS))
    return None

# %% 33. normalize() 把注音文、台語、英文、簡體字換成一般說法（對照表在 normalize.csv）

def normalize(text):
    sentence = text
    for old, new in NORMALIZE:
        if old.isascii():
            # 英文只換完整的字，前後不能接英文字母（ring 不會換到 string 裡面）
            pattern = r"(?<![a-zA-Z])" + re.escape(old) + r"(?![a-zA-Z])"
            sentence = re.sub(pattern, new, sentence, flags=re.IGNORECASE)
        else:
            sentence = sentence.replace(old, new)

    # 對照表沒有的注音，去掉聲調符號
    for mark in ["ˊ", "ˇ", "ˋ", "˙", "ˉ"]:
        sentence = sentence.replace(mark, "")
    return sentence

# %% 34. drop_items() 去掉句子裡的品項詞（手鐲、鐲子、吊墜…），反問前再找一次時使用

def drop_items(text):
    words = list(ITEMS)
    for term, standard in SYNONYMS.items():
        if standard in ITEMS:
            words.append(term)
    words.sort(key=len, reverse=True)
    for word in words:
        text = text.replace(word, "")
    return text

# %% 35. mentions_jade() 句子是否提到翡翠或翡翠飾品

def mentions_jade(text):
    return contains_any(text, JADE_ITEM_WORDS)

# %% 36. is_creative() 是否為天馬行空的假設題（有「可以幫我、會不會、拿來當」這類說法）

def is_creative(text):
    return contains_any(text, CREATIVE_WORDS)

# %% 測試區：直接執行這支檔案，在終端機模擬對話

if __name__ == "__main__":
    jade_db = connect()
    questions = ["你好", "你是誰", "冰鍾是什麼", "想買手觸送媽媽生日", "手鐲", "帶我去避坑清單", "今天星期幾"]
    for question in questions:
        answer = reply(question, jade_db)
        print("問：", question)
        print("答：", answer["text"][:80].replace("\n", " "))
        print("按鈕：", answer.get("options", []))
        print()
