# -*- coding: utf-8 -*-
"""
一玉了然｜翡翠選購指南（Streamlit 網站）

執行方式（在終端機）：
    1. 第一次使用先安裝：pip install -r ../requirements.txt
    2. 切換到這個資料夾，先建資料庫：python build_db.py
    3. 啟動：streamlit run app.py
    4. 手機與電腦連同一個 Wi-Fi 時，可以用終端機顯示的 Network URL 在手機上測試。

查詢紀錄（query_log）僅供管理者查看：網址加上 ?admin=1，在側邊欄輸入管理密碼後可查看與下載。
注意：雲端網站重啟後查詢紀錄會清空，需要保留請先下載。
"""

from datetime import datetime
from pathlib import Path
import pandas as pd
import base64
import csv
import random
import time

import streamlit as st
import streamlit.components.v1 as components
from streamlit import config

# 網站只負責畫面；搜尋、選款、翠小二的邏輯分別在 search.py、recommend.py、bot.py
from recommend import AGES, BUDGETS, ITEMS, TARGETS, USES, find_rule, find_tips
from bot import WELCOME, reply, start_options
from search import DB, cards_by_category, categories, connect, hot_cards, log_query, search

# %% 0. 頁面設定與樣式

# Streamlit 主題色由預設的紅色改為翡翠綠（.streamlit 設定資料夾不上傳，所以寫在程式裡）
config.set_option("theme.primaryColor", "#0B7A6B")
config.set_option("theme.greenColor", "#0B7A6B")
config.set_option("theme.greenTextColor", "#0B7A6B")

# 網頁標題與版面寬度（必須是第一個 Streamlit 指令）
st.set_page_config(page_title="一玉了然｜翡翠選購指南", layout="wide", initial_sidebar_state="collapsed")

# 全站樣式（CSS）：配色、字體、卡片、分頁、翠小二按鈕，以及手機版（640px 以下）的排版
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

/* 翠小二：右下角浮動按鈕（機器人圖示＋上面一個會輕輕跳動的提示泡泡），對話視窗靠右下 */
.st-key-bot-fab { position: fixed; right: 1.5rem; bottom: 4.5rem; z-index: 1000; width: auto !important; }
.st-key-bot-fab::before { content: "翡翠問題問我～"; position: absolute; right: 0; bottom: 4.4rem; width: 11rem; box-sizing: border-box; text-align: center; white-space: nowrap; background: #FFF6D5; color: #0B5C52; font-size: 1.05rem; font-weight: 700; padding: 0.45rem 0.7rem; border-radius: 0.9rem; border: 2px solid #0B7A6B; box-shadow: 0 4px 12px rgba(11, 92, 82, 0.25); animation: bubble-bounce 2.4s ease-in-out infinite; }
.st-key-bot-fab::after { content: ""; position: absolute; right: 5rem; bottom: 3.7rem; border-left: 0.5rem solid transparent; border-right: 0.5rem solid transparent; border-top: 0.6rem solid #0B7A6B; border-bottom: 0; animation: bubble-bounce 2.4s ease-in-out infinite; }
@keyframes bubble-bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-0.3rem); } }
.st-key-bot-fab button { width: 11rem; justify-content: center; border-radius: 2rem; padding: 0.6rem 1rem; background: #0B7A6B; color: white; border: none; box-shadow: 0 4px 14px rgba(0, 0, 0, 0.2); }
.st-key-bot-fab button:hover, .st-key-bot-fab button:focus { background: #0B5C52; color: white; border: none; }
.st-key-bot-fab button p { font-size: 1.15rem; font-weight: 700; color: white; }
.st-key-bot-fab button [data-testid="stIconMaterial"] { font-size: 0; width: 1.9rem !important; height: 1.9rem !important; min-width: 1.9rem; margin-right: 0.45rem; background: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><line x1='16' y1='4' x2='16' y2='9' stroke='white' stroke-width='2' stroke-linecap='round'/><circle cx='16' cy='3.5' r='2' fill='white'/><rect x='5' y='9' width='22' height='18' rx='6' fill='white'/><circle cx='12' cy='17' r='2' fill='%230B5C52'/><circle cx='20' cy='17' r='2' fill='%230B5C52'/><line x1='13' y1='22' x2='19' y2='22' stroke='%230B5C52' stroke-width='1.6' stroke-linecap='round'/></svg>") no-repeat center / contain; }
@media (min-width: 641px) { div[role="dialog"]:has(.st-key-bot-box) { position: fixed; right: 1.5rem; bottom: 8rem; margin: 0; max-height: calc(100vh - 9rem); } }
/* 手機版：平常是右下角的小圓形（機器人圖示置中）；點第一下展開成膠囊「問答機器人」（.bot-open，由頁尾的 JS 切換），再點一下才打開對話 */
@media (max-width: 640px) {
  .st-key-bot-fab { right: 0.8rem; bottom: 5rem; }
  .st-key-bot-fab::before, .st-key-bot-fab::after { display: none; }
  .st-key-bot-fab button { width: auto; min-width: 2.8rem; height: 2.8rem; min-height: 2.8rem; padding: 0 0.6rem; border-radius: 1.4rem; transition: padding 0.3s ease; }
  .st-key-bot-fab button [data-testid="stMarkdownContainer"] { display: none; }
  .st-key-bot-fab button > div { gap: 0; width: auto !important; min-width: 0; flex: 0 0 auto; justify-content: center; }
  .st-key-bot-fab button > div > span, .st-key-bot-fab button > div > span > span { width: auto; min-width: 1.6rem; justify-content: center; }
  .st-key-bot-fab button [data-testid="stIconMaterial"] { margin-right: 0; width: 1.6rem !important; height: 1.6rem !important; min-width: 1.6rem; }
  .st-key-bot-fab button::after { content: "問答機器人"; display: inline-block; flex-shrink: 0; max-width: 0; overflow: hidden; white-space: nowrap; color: white; font-size: 0.95rem; font-weight: 700; margin-left: 0; transition: max-width 0.3s ease, margin-left 0.3s ease; }
  .st-key-bot-fab.bot-open button { padding: 0 0.9rem 0 0.7rem; }
  .st-key-bot-fab.bot-open button::after { max-width: 8rem; margin-left: 0.35rem; }
  .check-float { right: 4.4rem; }
}
.st-key-bot-js { position: absolute; width: 0; height: 0; overflow: hidden; }
/* 翠小二對話框：高度跟著螢幕高度縮放，輸入框才不會被擠到視窗外面；「重新開始對話」不換行、靠右 */
div[role="dialog"] div.stVerticalBlock.st-key-bot-box, div[role="dialog"] div:has(> div.stVerticalBlock.st-key-bot-box) { height: max(10rem, min(430px, calc(100vh - 25rem))) !important; max-height: max(10rem, min(430px, calc(100vh - 25rem))) !important; }
.st-key-bot-reset { width: auto !important; margin-left: auto; }
.st-key-bot-reset button, .st-key-bot-reset button p { white-space: nowrap; }
/* 對話裡的選項按鈕橫著排、排不下自動換行；文字和說明仍佔滿一整行 */
.st-key-bot-box [data-testid="stChatMessageContent"] [data-testid="stVerticalBlock"] { flex-direction: row; flex-wrap: wrap; gap: 0.4rem; }
.st-key-bot-box [data-testid="stChatMessageContent"] [data-testid="stVerticalBlock"] > div:not(:has(button)) { flex-basis: 100%; }
.st-key-bot-box [data-testid="stChatMessageContent"] [data-testid="stVerticalBlock"] > div:has(button) { width: auto !important; }
/* 翠小二「打字中…」：三個點輪流跳動 */
.typing { display: flex; gap: 0.3rem; padding: 0.6rem 0; }
.typing span { width: 0.5rem; height: 0.5rem; border-radius: 50%; background: #8FB5A9; animation: typing-dot 1s infinite ease-in-out; }
.typing span:nth-child(2) { animation-delay: 0.15s; }
.typing span:nth-child(3) { animation-delay: 0.3s; }
@keyframes typing-dot { 0%, 60%, 100% { transform: translateY(0); opacity: 0.4; } 30% { transform: translateY(-0.35rem); opacity: 1; } }
</style>
""",
    unsafe_allow_html=True,
)

# %% 1. get_jade_db() 資料庫連線只建立一次並重複使用（Streamlit 每次操作都會重跑整支程式）

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

# 避坑清單確認到這個數量，就提示「可以考慮購買」
CHECK_ENOUGH = 10

# 主題瀏覽：每個分類的一句說明
TOPIC_DESC = {
    "認識翡翠": "翡翠是什麼、產地在哪裡？",
    "品質判斷": "翡翠五大關鍵：種、色、水、底、工",
    "真假處理": "何謂 A/B/C 貨？如何分辨處理貨？",
    "證書鑑定": "證書要看哪些地方、怎麼查證？",
    "選購價格": "預算怎麼抓、需要注意的地方？",
    "款式寓意": "題材的寓意，送禮怎麼挑？",
    "配戴保養": "怎麼保養、清潔與收納？",
}

# 新手入門：分 5 段，內容皆整理自知識卡（卡號標在各段註解）
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

# 常見迷思與真相（K037、K034、K040、K044／K046），排成 2×2
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

# %% 3. 知識卡配圖

IMAGE_DIR = Path(__file__).resolve().parent / "images"

# 個別圖片的顯示寬度（px），未列出的使用預設 620
# 照片解析度足夠才放大；直式或解析度較低的照片縮小，避免模糊
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
DEFAULT_WIDTH = 620

# load_images() 讀「圖片來源.csv」，回傳 {編號: (圖片的 base64 文字, 圖說, 出處)}
# 圖片轉成 base64 文字後可以直接放進網頁 HTML
def load_images():
    images = {}
    index_file = IMAGE_DIR / "圖片來源.csv"
    if not index_file.exists():
        return images
    with open(index_file, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            with open(IMAGE_DIR / row["檔名"], "rb") as image_file:
                data = base64.b64encode(image_file.read()).decode()
            images[row["編號"]] = (data, row["圖說"], row["來源"])
    return images

IMAGES = load_images()

# %% 4. image_html() 某張卡的配圖 HTML：圖片＋圖說＋出處；沒有配圖就回傳空字串

def image_html(card_id, width=0):
    if card_id not in IMAGES:
        return ""
    file_data, caption, credit = IMAGES[card_id]
    if width == 0:
        width = IMAGE_WIDTH.get(card_id, DEFAULT_WIDTH)
    return (f'<figure class="card-img" style="max-width: {width}px"><img src="data:image/jpeg;base64,{file_data}" alt="{caption}">'
            f'<figcaption>{caption}<br><span>{credit}</span></figcaption></figure>')

# %% 5. sources_html() 卡片最下方的參考資料，標示來源等級

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

# %% 6. card_body() 一張卡片的內容 HTML：答案 → 配圖 → 選購提醒 → 參考資料

def card_body(card, number=""):
    html = f'<div class="answer">{card["answer"]}</div>'
    html += image_html(card["id"])
    if card["caution"]:
        html += f'<div class="caution"><span class="caution-arrow">➜</span><b>選購提醒：</b>{card["caution"]}</div>'
    html += sources_html(card["sources"], number)
    return html

# %% 7. answer_card() 知識搜尋的結果卡片：綠色標題列＋內容（key 讓 CSS 能找到這個外框）

def answer_card(card, num):
    title = f"{num}. {card['question']}"
    with st.container(border=True, key=f"strong-box-search-{card['id']}"):
        st.html(f'<div class="card-title"><span>{title}</span><small><span class="card-badge">{card["category"]}</span>{card["id"]}</small></div>')
        st.html(card_body(card))

# %% 8. qa_item() 常見問題、主題瀏覽的一題：點選題目才展開

def qa_item(card, group, is_open=False):
    open_attr = ""
    if is_open:
        open_attr = " open"
    return f'<details class="qa" name="{group}"{open_attr}><summary>{card["question"]}</summary><div class="qa-body">{card_body(card, card["id"])}</div></details>'

# %% 9. section() 區塊小標題（圓形編號＋下方綠線）

def section(title):
    st.space("medium")
    number, name = title.split("、", 1)
    st.html(f'<div class="sec-head"><span class="sec-num">{number}</span>{name}</div>')

# %% 10. admin_panel() 查詢紀錄（僅供管理者）：輸入管理密碼才顯示

def admin_panel():
    with st.sidebar.expander("查詢紀錄（管理者）"):
        try:
            password = st.secrets.get("ADMIN_PASSWORD", "")
        except Exception:
            password = ""                       # 本機沒有 secrets.toml 時
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

# %% 11. 分頁「知識搜尋」

# 常見問題每次顯示幾題（熱門卡片打亂順序後，分批輪流顯示）
HOT_SHOW = 5

# clear_search() 按「✕」時清空搜尋框
def clear_search():
    st.session_state["search_query"] = ""

# show_search_result() 顯示搜尋結果；知識庫沒有的題目直接說明查無資料，不以不相關的卡片湊數
def show_search_result(query):
    result = search(query, jade_db=jade_db)

    # 每次操作都會重跑整頁，同一句只記錄一次
    if st.session_state.get("last_logged") != query:
        log_query(jade_db, query, len(result["results"]))
        st.session_state["last_logged"] = query

    if result["status"] == "ok":
        st.markdown(f'<div class="result-count">找到 {len(result["results"])} 筆相關知識</div>', unsafe_allow_html=True)
        for i, card in enumerate(result["results"], 1):
            answer_card(card, num=i)
    elif result["status"] == "NOT_JADE":
        st.info("查無資料：這個問題不在翡翠選購的範圍內。")
    else:
        st.info(f"目前還沒有「{query.strip()}」的相關內容。作者會參考大家搜尋的問題，持續補充知識庫。")

# show_hot_questions() 尚未輸入時顯示常見問題；session_state 記住打亂後的順序與目前位置，「換一批」才能依序看完、不重複
def show_hot_questions():
    st.space("small")
    st.divider()
    st.space("small")
    left, right = st.columns([5, 1], vertical_alignment="center")
    left.markdown('<div class="hot-tip">【FAQ】<span class="footer-full">或參考以下常見選購問題，點選題目即可查看完整說明與參考資料。</span><span class="footer-short">點選題目查看說明與參考資料</span></div>', unsafe_allow_html=True)
    refresh = right.button("換一批", icon=":material/refresh:", use_container_width=True)

    if "hot_order" not in st.session_state:
        hot = hot_cards(jade_db)
        random.shuffle(hot)
        st.session_state.hot_order = hot
        st.session_state.hot_start = 0
    order = st.session_state.hot_order
    if refresh:
        st.session_state.hot_start = (st.session_state.hot_start + HOT_SHOW) % len(order)     # 超過最後一題就從頭開始

    hot_html = ""
    for k in range(min(HOT_SHOW, len(order))):
        card = order[(st.session_state.hot_start + k) % len(order)]
        hot_html += qa_item(card, "hot")
    st.html(hot_html)

def search_tab():
    st.space("medium")
    query = st.text_input("【搜尋】輸入問題或關鍵字：", placeholder="例：「B貨是什麼意思」 或 「B貨」", key="search_query")
    if query.strip():
        st.button("✕", on_click=clear_search, key="search_clear", help="清除輸入內容")     # CSS 會把這個按鈕疊到搜尋框右側

    # 單一個字通常找不到有意義的結果
    if len(query.strip()) == 1:
        st.info("請輸入兩字以上的關鍵字或問句。")
    elif query.strip():
        show_search_result(query)

    if not query.strip():
        show_hot_questions()

# %% 12. 分頁「新手入門」

def basics_tab():
    section("一、認識翡翠")
    st.write("「玉」是統稱，分成硬玉和軟玉：翡翠是硬玉，和田玉是軟玉。")
    st.space("small")
    st.table(pd.DataFrame(JADE_TABLE).set_index("比較"))      # 以「比較」欄當索引，不顯示列號
    if "K002" in IMAGES:
        st.html(image_html("K002"))
    st.space("small")

    section("二、種、色、水、底、工")
    st.write("決定翡翠好壞與價格的五個關鍵字：")
    st.space("small")
    # 第一排「種、水、色」3 格；第二排「底、工」2 格，左右各留空白讓它置中
    top = st.columns(3)
    bottom = st.columns([1, 2, 2, 1])
    boxes = [top[0], top[1], top[2], bottom[1], bottom[2]]
    for i in range(len(FIVE_KEYS)):
        word, short, how, basis = FIVE_KEYS[i]
        with boxes[i].container(border=True, height="stretch"):      # height="stretch"：同一排的方框等高
            st.markdown(f"## :green[{word}]")
            st.markdown(f"**{short}**")
            st.caption(how)
            label, content = basis.split("：")
            st.markdown(f"**{label}**：{content}")
    st.space("small")

    # 配圖與「底、工」那排同寬（左右各留 1 份、中間占 4 份）
    if "K007" in IMAGES:
        st.columns([1, 4, 1])[1].html(image_html("K007", 2000))
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

    # 下一步：連結帶 ?tab=分頁名稱，點了會打開那個分頁
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

# %% 13. 分頁「主題瀏覽」

def topics_tab():
    st.space("medium")
    topics = {}
    for category, count in categories(jade_db):
        topics[category] = count

    # 標籤文字顯示張數，例如「認識翡翠（7）」
    def topic_label(category):
        return f"{category}（{topics[category]}）"

    st.markdown('<div class="topic-title">請點選以下主題選擇分類</div>', unsafe_allow_html=True)
    topic = st.pills("選擇分類", list(topics), format_func=topic_label, key="topic_pill", label_visibility="collapsed")
    if not topic:
        return

    # 電腦版：選中的標籤改顯示「【分類】說明」。標籤本身的文字不能改（Streamlit 會視為新元件、選取狀態會消失），
    # 所以用 CSS 把原文字隱藏，再用 ::after 顯示說明
    pill_text = f"【{topic}】{TOPIC_DESC.get(topic, '')}"
    st.markdown(f'''<style>
@media (min-width: 641px) {{
  [data-testid="stBaseButton-pillsActive"] p {{ font-size: 0 !important; }}
  [data-testid="stBaseButton-pillsActive"] p::after {{ content: "{pill_text}"; font-size: 0.92rem; }}
}}
</style>''', unsafe_allow_html=True)

    # 手機版：標籤不變，說明顯示在標籤下方（電腦版不顯示）
    st.html(f'<div class="topic-mobile">{TOPIC_DESC.get(topic, "")}</div>')
    st.space("small")

    topic_html = ""
    for card in cards_by_category(jade_db, topic):
        topic_html += qa_item(card, "topic")
    st.html(topic_html)

# %% 14. 分頁「選款建議」

# clear_rec() 「清除選項」：必選欄位清空，選填欄位回到「不指定」
def clear_rec():
    st.session_state["rec_budget"] = None
    st.session_state["rec_item"] = None
    st.session_state["rec_use"] = None
    st.session_state["rec_target"] = TARGETS[0]
    st.session_state["rec_age"] = AGES[0]

# style_columns() 款式卡片一律以三欄寬度排列；不足三個時置中（與新手入門「底、工」相同排法）
def style_columns(count):
    if count == 1:
        return [st.columns(3)[1]]
    if count == 2:
        return st.columns([1, 2, 2, 1])[1:3]
    return st.columns(count)

# show_rec_result() 顯示建議：預算建議、送禮（配戴）建議、適合的款式
def show_rec_result(budget, item, use, target, age):

    # 品項＋用途決定款式（四層退回，任何組合都有建議）；預算、對象、年齡各自找提醒
    rule = find_rule(budget, item, use, jade_db)
    tips = find_tips(target, age, item, budget, jade_db)

    # 提醒分兩組：預算一組，對象與年齡一組
    budget_tips = []
    gift_tips = []
    for tip in tips:
        if tip["kind"] == "預算":
            budget_tips.append(tip)
        else:
            gift_tips.append(tip)

    section("二、建議結果")
    with st.container(key="result-panel"):         # 結果區整塊淺綠底，卡片白底，與上方選擇區區隔
        # 有對象或年齡提醒時與預算建議左右並排；沒有時預算建議占滿整排
        if gift_tips:
            budget_area, gift_area = st.columns(2)
        else:
            budget_area = st

        with budget_area.container(border=True, height="stretch", key="result-card-budget"):
            st.subheader(f":green[預算建議（{budget}）]")
            for tip in budget_tips:
                st.write(tip["tip"])

        if gift_tips:
            with gift_area.container(border=True, height="stretch", key="result-card-gift"):
                # 自己戴或未指定對象是「配戴建議」，買給別人才是「送禮建議」
                gift_title = "送禮建議"
                if target == "自己" or target == TARGETS[0]:
                    gift_title = "配戴建議"
                st.subheader(f":green[{gift_title}]")
                for tip in gift_tips:
                    st.html(f'<div class="sub-title">{tip["kind"]}｜{tip["option"]}</div>')
                    st.write(tip["tip"])

        with st.container(border=True, key="result-card-style"):
            st.subheader(f":green[適合的款式（{item}｜{use}）]")
            if rule["match"] == "general":
                st.caption("這個用途還沒有專屬建議，先提供這個品項的通用建議。")

            columns = style_columns(len(rule["suggestions"]))
            for i, name in enumerate(rule["suggestions"]):
                with columns[i].container(border=True, height="stretch", key=f"result-sug-{i}"):
                    st.markdown(f":green[**建議 {i + 1}**]")
                    st.markdown(f"**{name}**")
                    # 款式圖片：先找「規則編號｜款式」專用的圖，沒有再用款式名稱的通用圖
                    rule_key = rule["id"] + "｜" + name
                    if rule_key in IMAGES:
                        st.html(image_html(rule_key))
                    elif name in IMAGES:
                        st.html(image_html(name))

            # 選購重點以「；」分隔，拆開後逐條列出，每條結尾補上句號
            st.html('<div class="sub-title line-top"><span class="mark">選購重點</span></div>')
            for point in rule["caution"].split("；"):
                if not point.endswith("。"):
                    point = point + "。"
                st.markdown(f"- {point}")

        # 選款建議是作者依知識卡整理的內容（來源列在知識卡上），所以這裡不列參考資料
        st.html('<div class="rec-note">以上為作者依本站知識卡整理的選購建議，僅供參考；想了解原因，可以到「知識搜尋」查詢相關知識。</div>')

def rec_tab():
    section("一、選擇條件")
    # 用表單包起來：選好後按「查看建議」才查詢；三個必選欄位不預設，由使用者自己選
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

    if not submitted:
        return
    if budget is None or item is None or use is None:
        st.warning("請先選擇預算、品項和用途。")
        return
    show_rec_result(budget, item, use, target, age)

# %% 15. 分頁「避坑清單」

# check_color() 勾得越多，卡片底色越深
def check_color(ratio):
    if ratio == 0:
        return "#4F6B62"
    if ratio < 0.5:
        return "#1F9A7A"
    if ratio < 1:
        return "#0B7A6B"
    return "#0B5C52"

# check_note() 進度卡片下方的提示：全部確認完「可以安心付款」；確認達 CHECK_ENOUGH 項「可以考慮購買」
def check_note(done, total):
    if done == total:
        return "check-float is-done", '<div class="check-done">✓ 可以安心付款</div>'
    if done < CHECK_ENOUGH:
        return "check-float", ""
    # 只有第一次達到時播放動畫，之後再勾選就不再播放
    if st.session_state.get("check_ten_shown"):
        return "check-float", '<div class="check-done no-pop">✓ 可以考慮購買</div>'
    st.session_state["check_ten_shown"] = True
    return "check-float", '<div class="check-done">✓ 可以考慮購買</div>'

def check_tab():
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
                if st.checkbox(text, key=f"check_{group}_{i}"):
                    done = done + 1
                total = total + 1

    # 進度卡片：勾得越多，數字越大、進度條越粗
    ratio = done / total
    color = check_color(ratio)
    size = 2 + 1.4 * ratio
    bar_height = 0.7 + 0.6 * ratio
    float_class, done_note = check_note(done, total)

    # 記住上一次的百分比，進度條才能從原本的位置以動畫延伸到新的位置
    percent = ratio * 100
    last_percent = st.session_state.get("check_last_percent", 0)
    st.session_state["check_last_percent"] = percent

    # 卡片固定在畫面右側，捲動時也看得到
    st.html(
        f'<div class="{float_class}" style="--from:{last_percent}%; --to:{percent}%; background:{color};">'
        f'<div class="check-label">已確認</div>'
        f'<div class="check-num" style="--num:{size}rem;">{done} / {total}</div>'
        f'<div class="check-bar" style="height:{bar_height}rem;"><div style="background:white;"></div></div>'
        f'{done_note}</div>'
    )
    st.caption("整理自知識卡 K038（證書要看哪些地方）、K046（怎麼避免買到處理過的翡翠）及一般選購常識；知識卡的參考資料見各卡片。")

# %% 16. 翠小二（翡翠問答機器人）：右下角浮動按鈕，點了開啟對話視窗
# 判斷與回答都在 bot.py；這裡只負責對話視窗的畫面

# bot_click() 點了對話中的選項按鈕：先記下來，視窗重跑時當成使用者輸入的句子
def bot_click(option):
    st.session_state["bot_pending"] = option

# goto_click() 點了「➜ 前往…」按鈕：先記下目的分頁，視窗重跑時第一時間切換（與自動帶路同一個時間點）
def goto_click(goto):
    st.session_state["bot_goto"] = goto

# type_out() 打字效果：先顯示跳動的「…」，再每次多顯示 3 個字
def type_out(text):
    area = st.empty()
    area.html('<div class="typing"><span></span><span></span><span></span></div>')     # 樣式見 CSS 的 .typing
    time.sleep(0.8)

    # 整段約 1.5 秒顯示完，長的答案也不會等太久
    wait = min(0.03, 1.5 / max(len(text) / 3, 1))
    for end in range(3, len(text) + 3, 3):
        area.markdown(text[:end])
        time.sleep(wait)

# go_to() 帶路：切換到指定分頁，有 fill 就預先選好那一頁的選項，再重跑整頁（同時關閉對話視窗）
def go_to(goto):
    st.session_state["tab_target"] = goto["tab"]
    st.session_state["tab_round"] = st.session_state.get("tab_round", 0) + 1     # 換一組新的分頁元件，見 %% 17
    for key, value in goto.get("fill", {}).items():
        st.session_state[key] = value
    st.rerun()

# show_history() 依序顯示對話；只有最後一則回答的按鈕可以點
def show_history(box):
    history = st.session_state["bot_history"]
    with box:
        for i, message in enumerate(history):
            with st.chat_message(message["role"]):
                if message.get("new"):
                    type_out(message["text"])
                    message["new"] = False
                else:
                    st.markdown(message["text"])
                if message.get("note"):
                    st.caption(message["note"])
                if i != len(history) - 1:
                    continue
                for j, option in enumerate(message.get("options", [])):
                    st.button(option, key=f"bot-opt-{i}-{j}", on_click=bot_click, args=(option,))
                goto = message.get("goto")
                if goto:
                    st.button("➜ " + goto["label"], key=f"bot-goto-{i}", type="primary",
                              on_click=goto_click, args=(goto,))

@st.dialog("翠小二｜翡翠問答", width="medium")
def bot_window():

    # 第一次開啟時放開場白
    if "bot_history" not in st.session_state:
        st.session_state["bot_history"] = [{"role": "assistant", "text": WELCOME, "options": start_options()}]

    # 右上角「重新開始對話」：先確認，按「確定」才清除對話
    reset_area = st.columns([2, 1])[1]
    with reset_area.popover("重新開始對話", icon=":material/refresh:", key="bot-reset"):
        st.write("確定要清除目前的對話嗎？")
        yes_area, no_area = st.columns(2)
        if yes_area.button("確定", type="primary", key="bot-reset-yes"):
            del st.session_state["bot_history"]
            st.rerun(scope="fragment")
        if no_area.button("取消", key="bot-reset-no"):
            st.rerun(scope="fragment")

    # 對話框在上、輸入框在下；這句話處理完才把內容放進對話框
    box = st.container(height=430, border=False, key="bot-box")
    typed = st.chat_input("輸入您的翡翠問題…", key="bot_input")

    # 剛才點了「➜ 前往…」→ 先切換分頁（必須在畫出對話內容之前，分頁才會真的切換）
    goto_now = st.session_state.pop("bot_goto", None)
    if goto_now:
        go_to(goto_now)

    # 這次的句子：點選的按鈕優先，否則是輸入框的文字
    pending = st.session_state.pop("bot_pending", None)
    user_text = typed
    if pending:
        user_text = pending

    if user_text:
        st.session_state["bot_history"].append({"role": "user", "text": user_text})
        answer = reply(user_text, jade_db)
        answer["role"] = "assistant"
        answer["new"] = True                    # 新回答用打字效果顯示
        st.session_state["bot_history"].append(answer)
        if answer.get("auto"):
            go_to(answer["goto"])

    show_history(box)

# %% 17. 版面

# 網站標題：明體字，上下細線
st.html('<div class="site-head"><div class="site-name">一玉了然</div><div class="site-sub">翡翠選購指南｜可追溯來源的知識檢索系統</div></div>')

# 五個分頁依新手順序排列：先學基礎（新手入門）→ 找答案（知識搜尋、主題瀏覽）→ 準備購買（選款建議、避坑清單）
TAB_NAMES = ["新手入門", "知識搜尋", "主題瀏覽", "選款建議", "避坑清單"]

# 要打開哪個分頁：
#   1. 「下一步」連結會在網址加上 ?tab=分頁名稱
#   2. 翠小二帶路（go_to）時記在 tab_target，並遞增 tab_round 換一組新的分頁元件
#      只改 session_state 不夠：之後按「查看建議」等按鈕時，瀏覽器會送回舊的分頁狀態，又跳回原本那頁
open_tab = st.query_params.get("tab")
if open_tab not in TAB_NAMES:
    open_tab = None
if st.session_state.get("tab_target"):
    open_tab = st.session_state["tab_target"]
tab_basics, tab_search, tab_topics, tab_rec, tab_check = st.tabs(
    TAB_NAMES, default=open_tab, key=f"main_tabs_{st.session_state.get('tab_round', 0)}", on_change="rerun")

with tab_search:
    search_tab()
with tab_basics:
    basics_tab()
with tab_topics:
    topics_tab()
with tab_rec:
    rec_tab()
with tab_check:
    check_tab()

# 右下角浮動按鈕（位置、顏色、提示泡泡見 CSS 的 .st-key-bot-fab）
if st.button("問翠小二", icon=":material/smart_toy:", key="bot-fab"):
    bot_window()

# 手機版：第一下只把圖示展開成「問答機器人」，第二下才開啟對話；4 秒沒點就收回。
# Streamlit 按鈕沒有「第一下不動作」的設定，所以用一小段 JavaScript 攔截手機上的第一下點擊（電腦版不攔截）。
with st.container(key="bot-js"):
    components.html("""
<script>
const w = window.parent, doc = w.document;
if (!w.__botFabReady) {
  w.__botFabReady = true;
  doc.addEventListener("click", (e) => {
    const fab = e.target.closest && e.target.closest(".st-key-bot-fab");
    if (!fab || !w.matchMedia("(max-width: 640px)").matches) return;
    clearTimeout(w.__botFabTimer);
    if (!fab.classList.contains("bot-open")) {
      e.preventDefault();
      e.stopPropagation();                      // 第一下：不打開對話，只展開膠囊
      fab.classList.add("bot-open");
      w.__botFabTimer = setTimeout(() => fab.classList.remove("bot-open"), 4000);
    } else {
      setTimeout(() => fab.classList.remove("bot-open"), 400);   // 第二下：照常打開對話，膠囊縮回去
    }
  }, true);
}
</script>""", height=0)

# 頁尾：最後更新日期取自資料庫檔案的修改時間
updated = datetime.fromtimestamp(DB.stat().st_mtime).strftime("%Y-%m-%d")
st.markdown(f'<div class="footer"><span class="footer-full">最後更新 {updated} &nbsp;｜&nbsp; 知識卡皆附參考資料，選款建議為作者整理 &nbsp;｜&nbsp; 僅供知識查詢與選購參考，實際以專業鑑定為準</span><span class="footer-short">最後更新 {updated} ｜ 僅供參考，實際以專業鑑定為準</span></div>', unsafe_allow_html=True)

# 查詢紀錄入口預設隱藏：網址加上 ?admin=1 才出現，並需輸入管理密碼
if st.query_params.get("admin") == "1":
    admin_panel()
