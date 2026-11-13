# -*- coding: utf-8 -*-
"""
一玉了然｜翡翠選購指南（Streamlit 網站）

執行方式（在終端機）：
    1. 第一次使用先安裝：pip install -r ../requirements.txt
    2. 切換到這個資料夾，先建資料庫：python build_db.py
    3. 啟動：streamlit run app.py
    4. 手機與電腦連同一個 Wi-Fi 時，可以用終端機顯示的 Network URL 在手機上測試。

查詢紀錄（query_log）只給自己看：側邊欄輸入管理密碼後可查看與下載。
注意：雲端網站重啟後查詢紀錄會清空，想保留就先下載。
"""

from datetime import datetime
from pathlib import Path
import pandas as pd
import base64
import csv
import random

import streamlit as st
from streamlit import config

# 網站只呼叫 search.py、recommend.py 的函式（模組化）
from recommend import AGES, BUDGETS, ITEMS, TARGETS, USES, find_rule, find_tips
from search import DB, cards_by_category, categories, connect, hot_cards, log_query, search

# %% 0. 頁面設定與樣式

# 網頁分頁標題與版面寬度（一定要寫在最前面）
# 把 Streamlit 的主題色從預設紅色換成翡翠綠（.streamlit 資料夾不會上傳，所以寫在程式裡）
config.set_option("theme.primaryColor", "#0B7A6B")
config.set_option("theme.greenColor", "#0B7A6B")
config.set_option("theme.greenTextColor", "#0B7A6B")
st.set_page_config(page_title="一玉了然｜翡翠選購指南", layout="wide", initial_sidebar_state="collapsed")

# 分頁：電腦上等寬；手機（640px 以下）恢復原寬度、可左右滑
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@500;600;700&display=swap');
.stTabs [data-baseweb="tab-list"] { width: 100%; }
.stTabs [data-baseweb="tab"] { flex: 1; justify-content: center; }
@media (max-width: 640px) {
  .stTabs [data-baseweb="tab"] { flex: none; }
}
[data-testid="stButtonGroup"] button { padding: 0.3rem 0.55rem; min-height: 2.4rem; flex: 0 0 auto; max-width: none; }
[data-testid="stButtonGroup"] button p { font-size: 0.93rem; white-space: nowrap; overflow: visible; }
[data-testid="stButtonGroup"] button div { overflow: visible; max-width: none; }
[data-testid="stBaseButton-pillsActive"], [data-testid="stBaseButton-pillsActive"]:hover, [data-testid="stBaseButton-pillsActive"]:focus, [data-testid="stBaseButton-pillsActive"]:active { background-color: #E3F3EF !important; border-color: #0B7A6B !important; }
[data-testid^="stBaseButton-pills"] { -webkit-tap-highlight-color: transparent; outline: none !important; }
[data-testid="stBaseButton-pillsActive"] p { color: #0B7A6B !important; }
[data-testid="stBaseButton-pillsActive"] p { white-space: normal !important; font-weight: 600; }
[data-testid="stTable"] th, [data-testid="stTable"] td { text-align: center !important; }
details.qa { border: 1px solid #5FB8A8; border-radius: 0.5rem; margin-bottom: 0.9rem; overflow: hidden; }
details.qa summary { cursor: pointer; list-style: none; background: #DFF3EE; padding: 0.6rem 1rem; font-size: 1.2rem; font-weight: 700; color: #0B7A6B; }
details.qa summary:hover { background: #CDEBE3; }
details.qa summary::-webkit-details-marker { display: none; }
details.qa summary::before { content: "›"; display: inline-block; margin-right: 0.75rem; transition: transform 0.15s; }
details.qa[open] summary::before { transform: rotate(90deg); }
.qa-body { padding: 1rem 1rem 0.25rem; }
.caution { margin-top: 1rem; }
.card-title { display: flex; justify-content: space-between; align-items: center; gap: 1rem; background: #0B7A6B; color: white; padding: 0.6rem 1rem; border-radius: 0.5rem; font-size: 1.4rem; font-weight: 700; }
.card-title small { font-size: 0.85rem; font-weight: 400; white-space: nowrap; }
.card-badge { background: white; color: #0B7A6B; font-weight: 600; padding: 0.15rem 0.55rem; border-radius: 0.4rem; margin-right: 0.6rem; }
[class*="st-key-strong-box"] { border: 2px solid #5FB8A8 !important; }
.box-title { font-size: 1.25rem; font-weight: 700; }
.box-good { color: #0B7A6B; }
.box-bad { color: #C2570C; }
.answer { margin-left: 1.5rem; font-size: 1.12rem; line-height: 1.85; color: #1F2A26; white-space: pre-line; }
.caution { margin-left: 1.5rem; font-size: 1rem; line-height: 1.7; color: #0B7A6B; }
.caution b { color: #0B7A6B; }
.sources-head { display: flex; justify-content: space-between; }
[data-testid="stTable"] { width: min(900px, 100%) !important; margin: 0 auto; }
[data-testid="stTable"] td { font-size: 1.08rem !important; }
[data-testid="stTable"] th * { font-weight: 700 !important; }
[data-testid="stTable"] th { font-size: 1.12rem !important; font-weight: 700 !important; color: #0B7A6B !important; background: #DFF3EE !important; }
[class*="st-key-result-panel"] { margin-top: 1.5rem; padding: 1.5rem; gap: 1.5rem; background: #CDEBE3; border-radius: 0.75rem; }
[class*="st-key-result-card"] { background: white; border: 2px solid #5FB8A8 !important; box-shadow: 0 4px 12px rgba(11, 92, 69, 0.15); }
[class*="st-key-result-sug"] { background: #EAF6F2; border: 1px solid #5FB8A8 !important; }
[data-testid="stElementContainer"]:has([data-testid="stButtonGroup"]), [data-testid="stButtonGroup"] { width: 100%; }
[data-testid="stButtonGroup"] [role="radiogroup"] { margin: 0 auto; justify-content: center; }
.next-grid { display: flex; flex-wrap: wrap; gap: 1rem; margin-top: 2rem; }
.next-col { flex: 1 1 320px; background: #E3F3EF; border-radius: 0.5rem; padding: 1rem 1.25rem; text-align: center; }
.next-col div { font-size: 1.15rem; font-weight: 700; color: #0B4F45; margin-bottom: 0.6rem; }
.next-col a { display: inline-block; margin: 0.2rem 0.3rem; padding: 0.35rem 0.9rem; background: #0B7A6B; color: white !important; border-radius: 0.4rem; text-decoration: none; font-weight: 600; }
[data-testid="stHeaderActionElements"] { display: none; }
.center-note { margin-top: 2.5rem; text-align: center; color: #808495; font-size: 0.875rem; padding-bottom: 1rem; }
.result-count { font-size: 1.25rem; font-weight: 600; color: #0B4F45; }
.hot-tip, .st-key-search_query [data-testid="stWidgetLabel"] p { font-size: 1.25rem; font-weight: 600; color: #0B4F45; }
.st-key-search_query [data-testid="stWidgetLabel"] { margin-bottom: 0.7rem; }
.st-key-search_query [data-baseweb="input"] { border: 2px solid #5FB8A8 !important; background: white !important; }
.st-key-search_clear { margin-top: -3.35rem; margin-left: auto; margin-right: 0.35rem; width: fit-content; z-index: 5; }
.st-key-search_clear button { border: none !important; background: transparent !important; min-height: 2.2rem; padding: 0 0.6rem; }
.st-key-search_clear button p { font-size: 1.25rem !important; font-weight: 700; color: #0B7A6B; }
.st-key-search_query [data-baseweb="input"]:focus-within { border-color: #0B7A6B !important; }
.st-key-search_query input { background: white !important; font-size: 1.15rem !important; padding: 0.75rem 1rem !important; color: #1F2A26; }
.st-key-search_query input::placeholder { color: #A9B3BC !important; opacity: 1; }
/* 整個網頁四邊鋪滿淡淡的翡翠綠，中間的內容放在一張白色的「紙」上 */
.stApp, [data-testid="stHeader"] { background: #E6F3F0 !important; }
[data-testid="stMain"] .stMainBlockContainer { background: white; border-radius: 1rem; box-shadow: 0 2px 18px rgba(15, 76, 58, 0.10); margin-top: 1.5rem; margin-bottom: 1.5rem; }
@media (min-width: 900px) { [data-testid="stMain"] .stMainBlockContainer { width: calc(100% - 4rem); } }
/* 網站標題：明體字、淡淡的翡翠綠，上下細線，走雅致的書卷風 */
.site-head { text-align: center; padding: 1.4rem 1rem 1.2rem; border-top: 1px solid #B5DCD3; border-bottom: 1px solid #B5DCD3; }
.site-name { font-family: "Noto Serif TC", "Songti TC", "PMingLiU", serif; font-size: 3rem; font-weight: 600; color: #0B5C52; letter-spacing: 0.5em; text-indent: 0.5em; line-height: 1.3; }
.site-sub { display: inline-block; margin-top: 0.5rem; font-family: "Noto Serif TC", "Songti TC", "PMingLiU", serif; font-size: 1.05rem; color: #5A6E66; letter-spacing: 0.2em; }
.site-sub::before, .site-sub::after { content: ""; display: inline-block; width: 2.5rem; height: 1px; background: #9CCFC3; vertical-align: middle; margin: 0 0.8rem; }
/* 全站統一用標題的明體（思源宋體）；圖示（stIconMaterial）要排除，不然箭頭、重新整理等小圖示會變成文字 */
.stApp *:not([data-testid="stIconMaterial"]), .stApp input, .stApp button, .stApp textarea { font-family: "Noto Serif TC", "Songti TC", "PMingLiU", serif !important; }
@media (max-width: 640px) {
  [data-testid="stHeader"] { background: transparent !important; }
  [data-testid="stMain"] .stMainBlockContainer { padding-top: 0.75rem !important; }
  .site-head { padding: 0.7rem 0.5rem 0.6rem; }
  [data-testid="stForm"] [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 0.4rem; }
  [data-testid="stForm"] [data-testid="stColumn"] { flex: 1 1 0 !important; width: auto !important; min-width: 0 !important; }
  [data-testid="stForm"] [data-baseweb="select"] div { font-size: 0.82rem; }
  [data-testid="stForm"] [data-baseweb="select"] > div { padding-left: 0; }
  [data-testid="stForm"] [data-baseweb="select"] > div > div:first-child { padding-left: 0.45rem !important; padding-right: 0 !important; }
  [data-testid="stForm"] [data-baseweb="select"] > div > div:last-child { padding-right: 0.1rem !important; padding-left: 0 !important; }
  [data-testid="stForm"] [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(3)) > [data-testid="stColumn"]:nth-child(1) { flex: 1.45 1 0 !important; }
  [data-testid="stForm"] [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(3)) > [data-testid="stColumn"]:nth-child(3) { flex: 1.15 1 0 !important; }
  [data-testid="stForm"] [data-baseweb="select"] [aria-label*="Clear"], [data-testid="stForm"] [data-baseweb="select"] svg[title*="Clear"] { display: none !important; }
  .site-name { font-size: 1.8rem; letter-spacing: 0.3em; text-indent: 0.3em; }
  .site-sub { margin-top: 0.15rem; font-size: 0.8rem; letter-spacing: 0.08em; }
  .site-sub::before, .site-sub::after { width: 1.2rem; margin: 0 0.4rem; }
}
.topic-mobile { display: none; }
[data-testid^="stBaseButton-pills"]:hover, [data-testid^="stBaseButton-pills"]:focus, [data-testid^="stBaseButton-pills"]:active { border-color: #0B7A6B !important; box-shadow: none !important; }
[data-testid^="stBaseButton-pills"]:hover p, [data-testid^="stBaseButton-pills"]:focus p, [data-testid^="stBaseButton-pills"]:active p { color: #0B7A6B !important; }
@media (max-width: 640px) {
  [data-testid="stButtonGroup"] [role="radiogroup"] { display: grid !important; grid-template-columns: 1fr 1fr; gap: 0.5rem; width: 100% !important; max-width: none !important; margin: 0 !important; }
  [data-testid="stButtonGroup"] button { width: 100%; justify-content: center; }
  [data-testid="stButtonGroup"] button:last-child { grid-column: 1 / -1; }
  .topic-mobile { display: block; text-align: center; font-size: 1.25rem; font-weight: 700; color: #0B4F45; }
}
@media (max-width: 370px) { [data-testid="stForm"] [data-baseweb="select"] div { font-size: 0.74rem !important; } }
.sec-head { display: flex; align-items: center; gap: 0.7rem; font-size: 1.5rem; font-weight: 700; color: #0B4F45; border-bottom: 2px solid #0B7A6B; padding-bottom: 0.5rem; }
.sec-num { display: inline-flex; align-items: center; justify-content: center; flex: none; width: 2.4rem; height: 2.4rem; border-radius: 50%; background: #0B7A6B; color: white; font-size: 1.3rem; }
.footer-short { display: none; }
@media (max-width: 640px) {
  .footer-full { display: none; }
  .footer-short { display: inline; }
  .footer { font-size: 0.72rem !important; white-space: nowrap; padding: 0.35rem 0.25rem !important; }
  [class*="st-key-result-card"] h3 { font-size: 1.2rem !important; }
}
.sub-title { font-size: 1.2rem; font-weight: 700; color: #1F2A26; }
.topic-title { text-align: center; font-size: 1.25rem; font-weight: 600; color: #0B4F45; margin-bottom: 3rem; }
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within { border-color: #0B7A6B !important; }
.sources { margin-left: 1.5rem; margin-top: 1.5rem; margin-bottom: 0.75rem; padding-top: 0.6rem; border-top: 1px solid rgba(128, 132, 149, 0.25); color: #808495; font-size: 0.8rem; line-height: 1.6; }
.sources a { color: inherit; }
@media (max-width: 640px) { .sources { margin-left: 0; font-size: 0.7rem; line-height: 1.5; } .sources .src-date { display: none; } }
.card-img { margin: 1.2rem auto 0.4rem; text-align: center; max-width: 620px; }
.card-img img { max-width: 100%; border-radius: 0.5rem; border: 1px solid #D5E3DC; }
[class*="st-key-result-sug"] .card-img img { aspect-ratio: 1 / 1; object-fit: contain; background: white; }
.card-img figcaption { margin-top: 0.4rem; font-size: 0.95rem; color: #3F4A45; }
.card-img figcaption span { font-size: 0.78rem; color: #808495; }
.card-img figcaption a { color: inherit; }
.stMainBlockContainer { max-width: 1500px; padding-top: 2rem !important; padding-bottom: 4.5rem; }
@media (min-width: 900px) { .stMainBlockContainer { padding-left: 2.5rem !important; padding-right: 2.5rem !important; } }
[class*="st-key-strong-box-search"] { margin-bottom: 1.75rem; }
[class*="st-key-result-card"] h3 { text-align: center; background: #0B7A6B; padding: 0.55rem 1rem !important; border-radius: 0.5rem; }
[class*="st-key-result-card"] h3 * { color: white !important; }
[class*="st-key-result-card"] [data-testid="stHeading"] { margin-bottom: 0.9rem; }
[data-testid="stForm"] { background: #F3FAF8; border: 1px solid #9CCFC3 !important; }
.rec-note { text-align: center; color: #808495; font-size: 0.875rem; }
.check-bar { height: 0.7rem; background: #EEF0F4; border-radius: 0.35rem; overflow: hidden; margin-top: 0.3rem; }
.check-bar div { height: 100%; width: var(--to); animation: check-grow 0.6s ease-out; }
@keyframes check-grow { from { width: var(--from); } to { width: var(--to); } }
.check-num { font-size: var(--num); line-height: 1.25; }
.check-float { position: fixed; right: 1.25rem; top: 50%; transform: translateY(-50%); z-index: 20; width: max-content; min-width: 11rem; padding: 1.1rem 1.2rem; color: white; border: 3px solid white; border-radius: 1rem; box-shadow: 0 10px 28px rgba(0, 0, 0, 0.38); text-align: center; font-weight: 700; }
.check-float .check-bar { background: rgba(255, 255, 255, 0.3); }
.check-float .check-label { font-size: 0.9rem; color: white; }
.check-float .check-done.no-pop { animation: none; }
.check-float .check-done { font-size: 1.4rem; font-weight: 800; color: white; margin-top: 0.5rem; white-space: nowrap; animation: done-pop 0.7s ease-out; }
.check-float.is-done { animation: done-glow 1.2s ease-in-out 3; }
@keyframes done-pop { 0% { transform: scale(0.4); opacity: 0; } 60% { transform: scale(1.25); opacity: 1; } 100% { transform: scale(1); } }
@keyframes done-glow { 0%, 100% { box-shadow: 0 0 0 0 rgba(11, 122, 107, 0.7); } 50% { box-shadow: 0 0 0 14px rgba(11, 92, 69, 0); } }
@media (max-width: 640px) { .check-float { top: auto; bottom: 2.4rem; right: 0.5rem; left: 0.5rem; width: auto; transform: none; padding: 0.4rem 0.8rem; } .check-num { font-size: 1.4rem; } }
.caution-arrow { font-size: 1.3rem; font-weight: 700; margin-right: 0.5rem; }
.mark { background: linear-gradient(transparent 55%, #A8E0CF 55%); padding: 0 0.3rem; font-size: 1.35rem; }
.line-top { border-top: 2px solid #0B7A6B; padding-top: 0.8rem; margin-top: 0.5rem; }
[data-testid="stCheckbox"] label:has(input:checked) > span:first-of-type { background-color: #0B7A6B !important; border-color: #0B7A6B !important; }
[data-testid="stCheckbox"] label > span:first-of-type { box-shadow: none !important; }
/* 選中的分頁：淡綠底、深綠粗體字、底線加粗，一眼看出現在在哪一頁 */
.stTabs [aria-selected="true"] { background: #E0F1ED; border-radius: 0.6rem 0.6rem 0 0; }
.stTabs [aria-selected="true"], .stTabs [aria-selected="true"] p { color: #0B5C52; font-weight: 700 !important; }
.stTabs [data-baseweb="tab-highlight"] { background-color: #0B5C52; height: 3px; }
[data-testid^="stBaseButton-primary"] { background-color: #0B7A6B; border-color: #0B7A6B; }
[data-testid^="stBaseButton-primary"]:hover, [data-testid^="stBaseButton-primary"]:focus, [data-testid^="stBaseButton-primary"]:active { background-color: #09665A !important; border-color: #09665A !important; color: white !important; box-shadow: none !important; }
[data-testid="stAppDeployButton"], [data-testid="stMainMenu"] { display: none; }
.footer { margin-top: 3.5rem; padding: 1rem 1rem 0.5rem; border-top: 1px solid #D5E3DC; text-align: center; color: #808495; font-size: 0.78rem !important; }
/* 電腦版字體：只在寬畫面放大，手機維持原本大小 */
@media (min-width: 900px) {
  .stTabs [data-baseweb="tab"] p { font-size: 1.15rem !important; }
  [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li { font-size: 1.1rem; }
  [data-testid="stCaptionContainer"], [data-testid="stCaption"] { opacity: 1 !important; }
  [data-testid="stCaptionContainer"] p { font-size: 1rem !important; color: #5A6472 !important; }
  [data-testid="stWidgetLabel"] p { font-size: 1.05rem; }
  [data-baseweb="select"] div { font-size: 1.05rem; }
  [data-testid="stButtonGroup"] button p { font-size: 0.9rem; }
  [data-testid="stBaseButton-secondary"] p, [data-testid^="stBaseButton-primary"] p, [data-testid="stBaseButton-secondaryFormSubmit"] p { font-size: 1.05rem; }
  .answer { font-size: 1.2rem; }
  .caution { font-size: 1.08rem; }
  .sources { font-size: 0.92rem; }
  .center-note, .rec-note { font-size: 1rem; color: #5A6472; }
  .footer { font-size: 0.82rem !important; color: #5A6472; }
  .card-title small { font-size: 0.95rem; }
  .check-float .check-label { font-size: 1.2rem; }
}
</style>
""",
    unsafe_allow_html=True,
)

# %% 1. get_jade_db() 資料庫連線只建立一次就重複使用；不然每次重跑都要重新連線，網站會變慢

@st.cache_resource
def get_jade_db():
    return connect()

jade_db = get_jade_db()

# %% 2. 固定內容（新手入門、主題說明、避坑清單）

# 避坑清單：依知識卡 K003（證書）、K004（避免買到處理過的翡翠）整理，分四組
CHECKLIST = {
    "證書": [
        "有附鑑定證書，結論是「翡翠」，沒有「處理」字樣",
        "證書是第三方鑑定機構開的，不是店家自己印的",
        "證書編號能在鑑定機構網站查到",
        "證書上的照片、重量、尺寸和實物一致",
        "證書有寫明是否經過處理，不是只寫產地或品名",
        "賣家說的、商品標示和證書內容都一致",
    ],
    "看實物": [
        "在自然光下看過顏色，不只看店內燈光",
        "用手電筒照過，沒有明顯裂紋",
        "手鐲量過圈口、戒指量過戒圍，實際試戴過",
        "網購時，先拿到清楚的照片、影片、尺寸和重量",
    ],
    "價格與話術": [
        "價格沒有明顯低於行情",
        "沒有被「緬甸直送」「撿漏」「最後一件」這類話術催著下單",
        "沒有被帶去所謂「工廠直銷店」買低價品",
        "問清楚鑲嵌材質（S925 銀、K 金），以及價格是否含金屬",
    ],
    "付款與售後": [
        "網購或直播：先看到證書再付款，並確認有鑑賞期",
        "確認退換貨規定，保留購買憑證和對話紀錄",
        "確認賣家是店家還是個人（個人偶爾賣二手，通常不適用七天解約）",
        "刻字、訂做的商品，先問清楚能不能退；要退貨須在收到後 7 天內通知賣家",
    ],
}

TOPIC_DESC = {
    "認識翡翠": "翡翠是什麼、產地在哪裡？",
    "品質判斷": "翡翠五大關鍵：種、色、水、底、工",
    "真假處理": "何謂 A/B/C 貨？如何分辨處理貨？",
    "證書鑑定": "證書要看哪些地方、怎麼查證？",
    "選購價格": "預算怎麼抓、需要注意的地方？",
    "款式寓意": "題材的寓意，送禮怎麼挑？",
    "配戴保養": "怎麼保養、清潔與收納？",
}

# 新手入門：分 5 段，每一點都整理自知識卡（卡號記在註解）
JADE_TABLE = [
    {"比較": "屬於", "翡翠": "硬玉", "和田玉": "軟玉"},
    {"比較": "組成", "翡翠": "輝石類的細小晶體", "和田玉": "透閃石纖維交織"},
    {"比較": "光澤", "翡翠": "玻璃光澤，可以很透", "和田玉": "油脂光澤，韌性高"},
    {"比較": "硬度", "翡翠": "6.5–7", "和田玉": "6–6.5"},
    {"比較": "主要產地", "翡翠": "緬甸，其次是瓜地馬拉", "和田玉": "新疆和田"},
]
# 五個關鍵字：(字, 意思, 怎麼看, 判斷依據)；種 K010、水 K010／K021、色 K026、底 K018、工 K017
FIVE_KEYS = [
    ("種", "質地細不細", "顆粒越細、結構越緊密越好", "等級：玻璃種＞冰種＞糯種＞豆種"),
    ("水", "透不透光", "越透越好，「種好遮三醜」", "依據：透明＞半透明＞不透明"),
    ("色", "顏色好不好", "顏色鮮豔、均勻的價值高", "依據：正、濃、鮮、均"),
    ("底", "乾不乾淨", "瑕疵越少越好", "依據：黑花、白花、絲狀瑕疵"),
    ("工", "切工好不好", "有雕花的另外看雕刻工藝", "依據：以沒有雕花的光身成品評"),
]
# 常見迷思 vs 真相（K037、K034、K040、K044／K046），畫成 2×2 小卡
MYTHS = [
    {"常見迷思": "綠色的玉就是翡翠", "真相": "常見的仿品是綠玉髓，拿起來比較輕"},
    {"常見迷思": "用手電筒照一照就知道真假", "真相": "手電筒只能看瑕疵，不能判斷真假"},
    {"常見迷思": "越透越漂亮，一定是 A 貨", "真相": "灌膠的 B 貨反而更透，肉眼看不出來"},
    {"常見迷思": "店家說保證天然就放心", "真相": "買附鑑定證書的，並到鑑定機構網站查證"},
]
# 實用知識：建議這樣做（K065、K066、K068、K069）／要避免（K064、K067、K069）
CARE_DO = [
    "清潔用溫和的肥皂水最安全",
    "每件分開收納，避免互相碰撞摩擦",
    "長時間不戴，用冷水清洗、浸泡幾小時保持潤澤",
    "曬到太陽沒關係，翡翠對光很穩定",
]
CARE_AVOID = [
    "刮傷：硬度 6.5–7，還是可能被刮傷",
    "跌落：切得太薄的翡翠特別容易摔碎",
    "高溫：例如珠寶師傅用的焊槍",
    "溫熱的酸：可能會受影響",
]
# 挑選四步驟：(步驟, 重點)；K045、K057／K063、K050、K046
STEPS = [
    ("抓預算", "先學會判斷檔次，再依預算找合適的檔次"),
    ("挑款式", "吊墜分素身和雕花；手鐲特別注意裂紋"),
    ("看品質", "小件常「求色」，大件常「求水」"),
    ("要證書", "附鑑定證書，並到鑑定機構網站查證"),
]

# %% 3. 共用元件

# 知識卡配圖：images 資料夾裡的「圖片來源.csv」記錄每張卡用哪張圖、圖說和出處
IMAGE_DIR = Path(__file__).resolve().parent / "images"
IMAGES = {}
if (IMAGE_DIR / "圖片來源.csv").exists():
    with open(IMAGE_DIR / "圖片來源.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            image_path = IMAGE_DIR / row["檔名"]
            with open(image_path, "rb") as image_file:
                image_bytes = image_file.read()
            data = base64.b64encode(image_bytes).decode()
            IMAGES[row["編號"]] = (data, row["圖說"], row["來源"])

# 個別圖片的顯示寬度（px）；沒列的維持預設 620。
# 放大以不超過照片本身清晰度為準（照片夠大才放大），直式或比較糊的照片縮小
IMAGE_WIDTH = {
    "K007": 760, "K010": 900, "K011": 900, "K012": 700, "K015": 720,
    "K055": 700, "K063": 820,
    "K013": 300, "K014": 200,
    "K028": 420, "K029": 420, "K030": 420,
    "K054": 450,
    "K020": 300,
    "K022": 240,
    "K016": 480,
}

# 把某張卡的配圖變成網頁 HTML：圖片＋圖說＋出處；沒有配圖就回傳空字串
def image_html(card_id, width=0):
    if card_id not in IMAGES:
        return ""
    file_data, caption, credit = IMAGES[card_id]
    if width == 0:
        width = IMAGE_WIDTH.get(card_id, 620)
    return (f'<figure class="card-img" style="max-width: {width}px"><img src="data:image/jpeg;base64,{file_data}" alt="{caption}">'
            f'<figcaption>{caption}<br><span>{credit}</span></figcaption></figure>')


# %% 4. sources_html() 參考資料：放在卡片最底下，附來源等級

def sources_html(sources, number=""):
    lines = ""
    for source in sources:
        name = f'<a href="{source["url"]}" target="_blank">{source["name"]}</a>'
        if source.get("org"):
            name += f"｜{source['org']}"
        note = ""
        if source["level"] == "C":
            note = "（店家資料，僅供補充）"
        lines += f"<div>• {source['id']}｜{source['level']} 級{note}｜{name}<span class='src-date'>｜存取日期 {source['accessed']}</span></div>"
    return f'<div class="sources"><div class="sources-head"><span>參考資料</span><span>{number}</span></div>{lines}</div>'

# %% 5. 一張卡片的內容：答案 → 選購提醒 → 參考資料，回傳一段 HTML

def card_body(card, number=""):
    html = f'<div class="answer">{card["answer"]}</div>'
    html += image_html(card["id"])
    if card["caution"]:
        html += f'<div class="caution"><span class="caution-arrow">➜</span><b>選購提醒：</b>{card["caution"]}</div>'
    html += sources_html(card["sources"], number)
    return html

# %% 6. 知識搜尋的卡片：綠色標題列＋內容，外面有明顯的外框（key 讓 CSS 找得到這個方框）

def answer_card(card, num):
    title = f"{num}. {card['question']}"
    with st.container(border=True, key=f"strong-box-search-{card['id']}"):
        st.html(f'<div class="card-title"><span>{title}</span><small><span class="card-badge">{card["category"]}</span>{card["id"]}</small></div>')
        st.html(card_body(card))

# %% 7. 常見問題、主題瀏覽的一題：點問題才展開

def qa_item(card, group, is_open=False):
    open_attr = ""
    if is_open:
        open_attr = " open"
    return f'<details class="qa" name="{group}"{open_attr}><summary>{card["question"]}</summary><div class="qa-body">{card_body(card, card["id"])}</div></details>'

# %% 8. section() 每個區塊的小標題（下面有一條綠線）

def section(title):
    st.space("medium")
    number, name = title.split("、", 1)
    st.html(f'<div class="sec-head"><span class="sec-num">{number}</span>{name}</div>')

# %% 9. admin_panel() 查詢紀錄只給自己看：輸入管理密碼才顯示

def admin_panel():
    with st.sidebar.expander("查詢紀錄（管理者）"):
        try:
            password = st.secrets.get("ADMIN_PASSWORD", "")
        except Exception:
            password = ""
        if not password:
            st.caption("尚未設定 ADMIN_PASSWORD（.streamlit/secrets.toml）。")
            return
        typed = st.text_input("管理密碼", type="password")
        if typed != password:
            return
        log = pd.read_sql("SELECT ts AS 時間, query AS 問句, hits AS 命中筆數 FROM query_log ORDER BY id DESC", jade_db)
        no_result = int((log["命中筆數"] == 0).sum())
        st.caption(f"共 {len(log)} 筆；查無資料 {no_result} 筆")
        st.dataframe(log.head(50), hide_index=True)
        today = datetime.now().strftime("%Y%m%d")
        csv_data = log.to_csv(index=False).encode("utf-8-sig")
        st.download_button("下載 CSV", csv_data, file_name=f"query_log_{today}.csv", mime="text/csv")

# %% 10. 版面

# 網站標題：深綠色橫幅
st.html('<div class="site-head"><div class="site-name">一玉了然</div><div class="site-sub">翡翠選購指南｜可追溯來源的知識檢索系統</div></div>')

# 常見問題每次顯示幾題（標「熱門」的卡打亂順序後，一批一批輪流顯示）
HOT_SHOW = 5

# 五個分頁，照新手的順序排：先學基礎（新手入門）→ 找答案（知識搜尋、主題瀏覽）→ 要購買（選款建議、避坑清單）
TAB_NAMES = ["新手入門", "知識搜尋", "主題瀏覽", "選款建議", "避坑清單"]
# 「下一步」的連結會在網址加上 ?tab=分頁名稱，這裡讀出來，打開那個分頁
open_tab = st.query_params.get("tab")
if open_tab not in TAB_NAMES:
    open_tab = None
tab_basics, tab_search, tab_topics, tab_rec, tab_check = st.tabs(TAB_NAMES, default=open_tab)

# 1. 知識搜尋
with tab_search:
    st.space("medium")
    # 按「清除搜尋」時把搜尋框清空
    def clear_search():
        st.session_state["search_query"] = ""

    query = st.text_input("【搜尋】輸入問題或關鍵字：", placeholder="例：「B貨是什麼意思」 或 「B貨」", key="search_query")
    # 有輸入內容時，搜尋框右側顯示 X（用 CSS 把按鈕疊到搜尋框裡）
    if query.strip():
        st.button("✕", on_click=clear_search, key="search_clear", help="清除輸入內容")

    # 只打一個字通常找不到有意義的結果，先請使用者多打一點
    if len(query.strip()) == 1:
        st.info("請輸入兩字以上的關鍵字或問句。")
    elif query.strip():
        # 回傳狀態（ok／查無／範圍外）與知識卡
        result = search(query, jade_db=jade_db)
        # 切換其他選項時整頁會重跑，同一句只記一次
        if st.session_state.get("last_logged") != query:
            log_query(jade_db, query, len(result["results"]))
            st.session_state["last_logged"] = query
        if result["status"] == "ok":
            st.markdown(f'<div class="result-count">找到 {len(result["results"])} 筆相關知識</div>', unsafe_allow_html=True)
            for i, card in enumerate(result["results"], 1):
                answer_card(card, num=i)
        else:
            # 知識庫沒有的題目直接說查無資料，不拿不相關的卡硬湊答案
            if result["status"] == "NOT_JADE":
                st.info("查無資料：這個問題不在翡翠選購的範圍內。")
            else:
                st.info(f"目前還沒有「{query.strip()}」的相關內容。作者會參考大家搜尋的問題，持續補充知識庫。")

    # 還沒輸入時顯示常見問題，給不知道要搜什麼的人；開始打字就換成搜尋結果
    if not query.strip():
        # 搜尋框和常見問題之間，中間畫一條線分開
        st.space("small")
        st.divider()
        st.space("small")
        left, right = st.columns([5, 1], vertical_alignment="center")
        left.markdown('<div class="hot-tip">【FAQ】<span class="footer-full">或參考以下常見選購問題，點選題目即可查看完整說明與參考資料。</span><span class="footer-short">點選題目查看說明與參考資料</span></div>', unsafe_allow_html=True)
        refresh = right.button("換一批", icon=":material/refresh:", use_container_width=True)
        # session_state 記住打亂後的順序和目前看到第幾題，換一批才能依序看完全部、不重複
        if "hot_order" not in st.session_state:
            hot = hot_cards(jade_db)
            random.shuffle(hot)
            st.session_state.hot_order = hot
            st.session_state.hot_start = 0
        order = st.session_state.hot_order
        if refresh:
            # 超過最後一題就繞回開頭
            st.session_state.hot_start = (st.session_state.hot_start + HOT_SHOW) % len(order)
        hot_html = ""
        for k in range(min(HOT_SHOW, len(order))):
            card = order[(st.session_state.hot_start + k) % len(order)]
            hot_html += qa_item(card, "hot")
        st.html(hot_html)

# 2. 新手入門
with tab_basics:
    section("一、認識翡翠")
    st.write("「玉」是統稱，分成硬玉和軟玉：翡翠是硬玉，和田玉是軟玉。")
    st.space("small")
    # 以「比較」欄當索引，不顯示 0、1、2 列號
    st.table(pd.DataFrame(JADE_TABLE).set_index("比較"))
    if "K002" in IMAGES:
        st.html(image_html("K002"))
    st.space("small")

    section("二、種、色、水、底、工")
    st.write("決定翡翠好壞與價格的五個關鍵字：")
    st.space("small")
    # 分兩排：第一排種水色（3 格）；第二排底工（2 格），左右各留半格空白，放在正中間
    top = st.columns(3)
    bottom = st.columns([1, 2, 2, 1])
    boxes = [top[0], top[1], top[2], bottom[1], bottom[2]]
    for i in range(len(FIVE_KEYS)):
        word, short, how, basis = FIVE_KEYS[i]
        # 同一排的方框等高
        with boxes[i].container(border=True, height="stretch"):
            st.markdown(f"## :green[{word}]")
            st.markdown(f"**{short}**")
            st.caption(how)
            label, content = basis.split("：")
            st.markdown(f"**{label}**：{content}")
    st.space("small")
    # 顏色圖放寬一點，讓底下的圖說只佔一行
    if "K007" in IMAGES:
        st.columns([1, 12, 1])[1].html(image_html("K007", 2000))
    image_col = st.columns([1, 4, 1])[1]
    if "K010" in IMAGES:
        image_col.html(image_html("K010", 2000))

    section("三、分辨真假")
    st.write("肉眼很難分辨真假，先破除這幾個常見的迷思：")
    st.space("small")
    for start in (0, 2):
        columns = st.columns(2)
        for i in range(2):
            myth = MYTHS[start + i]
            with columns[i].container(border=True, height="stretch"):
                st.markdown(f"**「{myth['常見迷思']}」**")
                st.markdown(f":green[**其實**]　{myth['真相']}。")

    section("四、實用知識")
    st.write("翡翠韌性好、不容易斷，但日常還是要注意：")
    st.space("small")
    do_col, avoid_col = st.columns(2)
    with do_col.container(border=True, height="stretch"):
        st.html('<div class="box-title box-good">✓ 建議這樣做</div>')
        for text in CARE_DO:
            st.markdown(f"- {text}")
    with avoid_col.container(border=True, height="stretch"):
        st.html('<div class="box-title box-bad">✗ 要避免</div>')
        for text in CARE_AVOID:
            st.markdown(f"- {text}")

    section("五、如何挑選適合的翡翠")
    for start in (0, 2):
        columns = st.columns(2)
        for i in range(2):
            step, point = STEPS[start + i]
            with columns[i].container(border=True, height="stretch"):
                st.html(f'<div class="box-title">步驟 {start + i + 1}｜{step}</div>')
                st.caption(point)
    st.space("small")
    # 兩塊並排：想查資料／準備要買；連結做成按鈕，點了會打開那個分頁
    st.html(
        '<div class="next-grid">'
        '<div class="next-col"><div>還有問題想查</div>'
        '<a href="?tab=知識搜尋" target="_self">知識搜尋</a>'
        '<a href="?tab=主題瀏覽" target="_self">主題瀏覽</a></div>'
        '<div class="next-col"><div>準備要買了</div>'
        '<a href="?tab=選款建議" target="_self">選款建議</a>'
        '<a href="?tab=避坑清單" target="_self">避坑清單</a></div>'
        '</div>'
    )
    st.space("small")
    st.markdown('<div class="center-note">以上整理自本站知識卡；完整說明和參考資料，可以到「主題瀏覽」查看。</div>', unsafe_allow_html=True)

# 3. 主題瀏覽
with tab_topics:
    st.space("medium")
    # 主題瀏覽：選一個分類，列出該分類所有卡片
    topics = {}
    for category, count in categories(jade_db):
        topics[category] = count
    names = list(topics)

    # 標籤上顯示的文字，例如「認識翡翠（7）」
    def topic_label(category):
        return f"{category}（{topics[category]}）"
    st.markdown('<div class="topic-title">請點選以下主題選擇分類</div>', unsafe_allow_html=True)
    topic = st.pills("選擇分類", names, format_func=topic_label, key="topic_pill", label_visibility="collapsed")
    if topic:
        # 電腦版：被點選的那顆標籤顯示「【分類】說明」。標籤真正的文字不能改（改了 Streamlit 會當成新元件、選取狀態會不見），
        pill_text = f"【{topic}】{TOPIC_DESC.get(topic, '')}"
        st.markdown(f'''<style>
@media (min-width: 641px) {{
  [data-testid="stBaseButton-pillsActive"] p {{ font-size: 0 !important; }}
  [data-testid="stBaseButton-pillsActive"] p::after {{ content: "{pill_text}"; font-size: 0.92rem; }}
}}
</style>''', unsafe_allow_html=True)
        # 手機上標籤不變動，說明放在標籤下面（電腦版不顯示這行）
        st.html(f'<div class="topic-mobile">{TOPIC_DESC.get(topic, "")}</div>')
        st.space("small")
        topic_html = ""
        for card in cards_by_category(jade_db, topic):
            topic_html += qa_item(card, "topic")
        st.html(topic_html)

# 4. 選款建議
with tab_rec:
    section("一、選擇條件")
    # 用表單（form）包起來：選好後按「查看建議」才查詢；三個必選欄位都不預設，請使用者自己選
    def clear_rec():
        st.session_state["rec_budget"] = None
        st.session_state["rec_item"] = None
        st.session_state["rec_use"] = None
        st.session_state["rec_target"] = TARGETS[0]
        st.session_state["rec_age"] = AGES[0]

    with st.form("rec_form"):
        st.caption(":red[*]必選")
        budget_col, item_col, use_col = st.columns(3)
        budget = budget_col.selectbox("預算 :red[*]", BUDGETS, index=None, placeholder="請選擇", key="rec_budget")
        item = item_col.selectbox("品項 :red[*]", ITEMS, index=None, placeholder="請選擇", key="rec_item")
        use = use_col.selectbox("用途 :red[*]", USES, index=None, placeholder="請選擇", key="rec_use")
        st.caption("選填")
        target_col, age_col = st.columns(2)
        target = target_col.selectbox("對象", TARGETS, key="rec_target")
        age = age_col.selectbox("年齡", AGES, key="rec_age")
        submit_col, clear_col = st.columns([4, 1])
        submitted = submit_col.form_submit_button("查看建議", type="primary", use_container_width=True)
        clear_col.form_submit_button("清除選項", on_click=clear_rec, use_container_width=True)

    if submitted and (budget is None or item is None or use is None):
        st.warning("請先選擇預算、品項和用途。")
    elif submitted:
        # 品項＋用途決定款式（四層退回，任何組合都有建議）；預算、對象、年齡各自找提醒
        rule = find_rule(budget, item, use, jade_db)
        tips = find_tips(target, age, item, budget, jade_db)
        # 提醒分兩組：預算一組，對象和年齡一組
        budget_tips = []
        gift_tips = []
        for tip in tips:
            if tip["kind"] == "預算":
                budget_tips.append(tip)
            else:
                gift_tips.append(tip)

        section("二、建議結果")
        # 答案區整塊鋪淺綠底、裡面的卡片白底，和上面的點選區分開
        with st.container(key="result-panel"):
            # 有對象或年齡提醒時，提醒卡片放在預算建議右邊；沒有時預算建議佔滿整排
            if gift_tips:
                budget_area, gift_area = st.columns(2)
            else:
                budget_area = st

            # 第一區：預算建議（預算是必選，所以放最上面）
            with budget_area.container(border=True, height="stretch", key="result-card-budget"):
                st.subheader(f":green[預算建議（{budget}）]")
                for tip in budget_tips:
                    st.write(tip["tip"])

            # 第二區：送禮建議（有選對象或年齡才出現）
            if gift_tips:
                with gift_area.container(border=True, height="stretch", key="result-card-gift"):
                    # 自己戴或沒指定對象是「配戴建議」，買給別人才是「送禮建議」
                    gift_title = "送禮建議"
                    if target == "自己" or target == TARGETS[0]:
                        gift_title = "配戴建議"
                    st.subheader(f":green[{gift_title}]")
                    for tip in gift_tips:
                        st.html(f'<div class="sub-title">{tip["kind"]}｜{tip["option"]}</div>')
                        st.write(tip["tip"])

            # 第三區：適合的款式（改品項或用途，這一區會變）
            with st.container(border=True, key="result-card-style"):
                st.subheader(f":green[適合的款式（{item}｜{use}）]")
                if rule["match"] == "general":
                    st.caption("這個用途還沒有專屬建議，先提供這個品項的通用建議。")
                # 款式並排成卡片，一律照三欄的寬度排；不到三個就放中間（和新手入門「底、工」那排一樣的排法）
                count = len(rule["suggestions"])
                if count == 1:
                    columns = [st.columns(3)[1]]
                elif count == 2:
                    columns = st.columns([1, 2, 2, 1])[1:3]
                else:
                    columns = st.columns(count)
                for i, name in enumerate(rule["suggestions"]):
                    with columns[i].container(border=True, height="stretch", key=f"result-sug-{i}"):
                        st.markdown(f":green[**建議 {i + 1}**]")
                        st.markdown(f"**{name}**")
                        rule_key = rule["id"] + "｜" + name
                        if rule_key in IMAGES:
                            st.html(image_html(rule_key))
                        elif name in IMAGES:
                            st.html(image_html(name))
                st.html('<div class="sub-title line-top"><span class="mark">選購重點</span></div>')
                # 選購重點原本用「；」隔開，拆開後一條一條列出來
                for point in rule["caution"].split("；"):
                    # 每一條結尾都補上句號（最後一條本來就有，不重複加）
                    if not point.endswith("。"):
                        point = point + "。"
                    st.markdown(f"- {point}")

            # 選款建議＝作者依知識卡整理的建議（知識卡才列 A／B 級來源），所以這裡不列參考資料
            st.html('<div class="rec-note">以上為作者依本站知識卡整理的選購建議，僅供參考；想了解原因，可以到「知識搜尋」查詢相關知識。</div>')

# 5. 避坑清單
with tab_check:
    st.space("medium")
    st.caption("付款前，逐項確認：")
    done = 0
    total = 0
    group_no = 0
    for group, checks in CHECKLIST.items():
        group_no = group_no + 1
        with st.container(border=True, key=f"strong-box-check-{group_no}"):
            st.html(f'<div class="box-title box-good">{group}</div>')
            for i, text in enumerate(checks):
                checked = st.checkbox(text, key=f"check_{group}_{i}")
                if checked:
                    done = done + 1
                total = total + 1
    # 勾得越多，字越大、卡片底色越深
    ratio = done / total
    if ratio == 0:
        color = "#4F6B62"
    elif ratio < 0.5:
        color = "#1F9A7A"
    elif ratio < 1:
        color = "#0B7A6B"
    else:
        color = "#0B5C52"
    size = 2 + 1.4 * ratio
    bar_height = 0.7 + 0.6 * ratio
    done_note = ""
    float_class = "check-float"
    # 確認約 10 項就可以考慮購買；全部確認完才顯示「可以安心付款」
    if done == total:
        float_class = "check-float is-done"
        done_note = '<div class="check-done">✓ 可以安心付款</div>'
    elif done >= 10:
        # 只有第一次達到 10 項時跳出動畫，之後再勾選就靜靜顯示
        if st.session_state.get("check_ten_shown"):
            done_note = '<div class="check-done no-pop">✓ 可以考慮購買</div>'
        else:
            st.session_state["check_ten_shown"] = True
            done_note = '<div class="check-done">✓ 可以考慮購買</div>'
    # 記住上一次的百分比，進度條才能從舊的位置動畫長到新的位置
    percent = ratio * 100
    last_percent = st.session_state.get("check_last_percent", 0)
    st.session_state["check_last_percent"] = percent
    # 固定在畫面右側，捲到哪裡都看得到
    st.html(
        f'<div class="{float_class}" style="--from:{last_percent}%; --to:{percent}%; background:{color};">'
        f'<div class="check-label">已確認</div>'
        f'<div class="check-num" style="--num:{size}rem;">{done} / {total}</div>'
        f'<div class="check-bar" style="height:{bar_height}rem;"><div style="background:white;"></div></div>'
        f'{done_note}</div>'
    )
    st.caption("整理自知識卡 K038（證書要看哪些地方）、K046（怎麼避免買到處理過的翡翠）及一般選購常識；知識卡的參考資料見各卡片。")

# 頁尾與側邊欄
modified = DB.stat().st_mtime

updated = datetime.fromtimestamp(modified).strftime("%Y-%m-%d")
st.markdown(f'<div class="footer"><span class="footer-full">最後更新 {updated} &nbsp;｜&nbsp; 知識卡皆附參考資料，選款建議為作者整理 &nbsp;｜&nbsp; 僅供知識查詢與選購參考，實際以專業鑑定為準</span><span class="footer-short">最後更新 {updated} ｜ 僅供參考，實際以專業鑑定為準</span></div>', unsafe_allow_html=True)

# 查詢紀錄的入口藏起來：只有網址後面加 ?admin=1 才出現，要輸入管理密碼才看得到內容
if st.query_params.get("admin") == "1":
    admin_panel()
