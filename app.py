import streamlit as st
import akshare as ak
import pandas as pd
import mplfinance as mpf
import pandas_ta as ta
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.font_manager as fm
import os
import datetime
from io import BytesIO

# --- 1. 页面配置 ---
st.set_page_config(page_title="A股量化深度全景-专业版", layout="wide")

# --- 2. 字体注入 ---
def get_font_prop():
    font_paths = ['/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', 'C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf']
    for path in font_paths:
        if os.path.exists(path): return fm.FontProperties(fname=path)
    return None

# --- 3. 股票名称映射 (30天缓存) ---
@st.cache_data(ttl=3600*24*30)
def get_smart_name_map():
    try:
        df_new = ak.stock_zh_a_spot_em()[['代码', '名称']]
        return dict(zip(df_new['代码'], df_new['名称']))
    except: return {}

# --- 4. 核心分析函数 ---
def generate_analysis(code):
    f_prop = get_font_prop()
    name_map = get_smart_name_map()
    stock_name = name_map.get(code, "未知股票")
    
    try:
        # 获取基础数据 (从2024开始以计算长线均线)
        df_d = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20240101", adjust="qfq")
        df_m = ak.stock_zh_a_hist_min_em(symbol=code, period='1', adjust="qfq")
        if df_d.empty or df_m.empty: return None, None, None

        # 清洗数据
        def clean(df, is_min=False):
            t_col = '时间' if is_min else '日期'
            df = df[[t_col, '开盘', '最高', '最低', '收盘', '成交量']]
            df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            return df.astype(float)

        df_daily, df_min_raw = clean(df_d), clean(df_m, is_min=True)
        df_min = df_min_raw[df_min_raw.index.date == df_min_raw.index.date[-1]]
        curr_date = df_min.index[-1].strftime('%Y-%m-%d')
        
        # 计算 6 条均线与指标
        for length in [5, 10, 20, 30, 60, 120]:
            df_daily[f'MA{length}'] = ta.sma(df_daily['Close'], length=length)
        
        df_daily = pd.concat([df_daily, ta.macd(df_daily['Close'])], axis=1)
        df_daily['RPS'] = (df_daily['Close'] / df_daily['Close'].shift(250)) * 100
        
        # 选取最近 120 交易日(约半年)进行展示
        plot_d = df_daily.tail(120)
        
        # --- [重点修改] 计算区间最值 ---
        period_high = plot_d['High'].max()
        period_low = plot_d['Low'].min()

        # 绘图配置
        m_c = [c for c in df_daily.columns if 'MACD_' in c and 's' not in c and 'h' not in c][0]
        s_c = [c for c in df_daily.columns if 'MAC
