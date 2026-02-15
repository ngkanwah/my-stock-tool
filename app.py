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
import json
from io import BytesIO

# --- 1. 页面配置 ---
st.set_page_config(page_title="A股量化深度全景-专业版", layout="wide")

# --- 2. 字体注入 ---
def get_font_prop():
    font_paths = ['/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', 'C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf']
    for path in font_paths:
        if os.path.exists(path): return fm.FontProperties(fname=path)
    return None

# --- 3. 30天缓存 ---
@st.cache_data(ttl=3600*24*30)
def get_smart_name_map():
    cache_file = "stock_list_cache.csv"
    try:
        if os.path.exists(cache_file):
            df_local = pd.read_csv(cache_file, dtype={'代码': str})
            return dict(zip(df_local['代码'], df_local['名称']))
        df_new = ak.stock_zh_a_spot_em()[['代码', '名称']]
        df_new.to_csv(cache_file, index=False)
        return dict(zip(df_new['代码'], df_new['名称']))
    except: return {}

# --- 4. 核心分析函数 ---
def generate_analysis(code):
    f_prop = get_font_prop()
    name_map = get_smart_name_map()
    stock_name = name_map.get(code, "未知股票")
    
    try:
        df_d = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20240101", adjust="qfq")
        df_m = ak.stock_zh_a_hist_min_em(symbol=code, period='1', adjust="qfq")
        if df_d.empty or df_m.empty: return None, None, None

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
        
        # 补全 6 条均线计算
        for length in [5, 10, 20, 30, 60, 120]:
            df_daily[f'MA{length}'] = ta.sma(df_daily['Close'], length=length)
        
        df_daily = pd.concat([df_daily, ta.macd(df_daily['Close'])], axis=1)
        df_daily['RPS'] = (df_daily['Close'] / df_daily['Close'].shift(250)) * 100
        
        plot_d = df_daily.tail(120)
        m_c, s_c, h_c = [c for c in df_daily.columns if 'MACD_' in c and 's' not in c and 'h' not in c][0], [c for c in df_daily.columns if 'MACDs_' in c][0], [c for c in df_daily.columns if 'MACDh_' in c][0]

        mc = mpf.make_marketcolors(up='red', down='green', edge='inherit', wick='inherit', volume='in')
        fig = mpf.figure(style=mpf.make_mpf_style(marketcolors=mc, gridstyle='--'), figsize=(14, 25))
        fig.subplots_adjust(top=0.92, bottom=0.05, left=0.15, right=0.85)
        fig.suptitle(f"{stock_name} ({code}) 量化报告", fontsize=24, fontweight='bold', y=0.98, fontproperties=f_prop)
        
        gs = gridspec.GridSpec(6, 1, height_ratios=[6, 2, 2, 2, 5, 2], hspace=0.35)
        axs = [fig.add_subplot(gs[i]) for i in range(6)]
        
        ap = [
            mpf.make_addplot(plot_d[['MA5', 'MA10', 'MA20', 'MA30', 'MA60', 'MA120']], ax=axs[0]),
            mpf.make_addplot(plot_d[m_c], ax=axs[2], color='blue'),
            mpf.make_addplot(plot_d[s_c], ax=axs[2], color='orange'),
            mpf.make_addplot(plot_d[h_c], ax=axs[2], type='bar', color='gray', alpha=0.3),
            mpf.make_addplot(plot_d['RPS'], ax=axs[3], color='purple')
        ]
        mpf.plot(plot_d, type='candle', ax=axs[0], volume=axs[1], addplot=ap)
        mpf.plot(df_min, type='line', ax=axs[4], volume=axs[5])

        # --- MA数值显示 ---
        last_ma = plot_d.iloc[-1]
        ma_label = (f"MA5:{last_ma['MA5']:.2f}  MA10:{last_ma['MA10']:.2f}  MA20:{last_ma['MA20']:.2f}  "
                    f"MA30:{last_ma['MA30']:.2f}  MA60:{last_ma['MA60']:.2f}  MA120:{last_ma['MA120']:.2f}")
        axs[0].text(0, 1.02, ma_label, transform=axs[0].transAxes, fontsize=10, color='blue', fontproperties=f_prop)

        # --- 核心修改：日K线右侧改为区间最高/最低 (120天内) ---
        period_high = plot_d['High'].max()  # 区间内最高
        period_low = plot_d['Low'].min()    # 区间内
