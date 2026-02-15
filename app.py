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

# --- 4. 核心分析函数 (加入 6 条均线) ---
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
        
        # --- 补全 6 条均线计算 ---
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
        
        # 将 6 条均线全部加入 addplot
        ap = [
            mpf.make_addplot(plot_d[['MA5', 'MA10', 'MA20', 'MA30', 'MA60', 'MA120']], ax=axs[0]),
            mpf.make_addplot(plot_d[m_c], ax=axs[2], color='blue'),
            mpf.make_addplot(plot_d[s_c], ax=axs[2], color='orange'),
            mpf.make_addplot(plot_d[h_c], ax=axs[2], type='bar', color='gray', alpha=0.3),
            mpf.make_addplot(plot_d['RPS'], ax=axs[3], color='purple')
        ]
        mpf.plot(plot_d, type='candle', ax=axs[0], volume=axs[1], addplot=ap)
        mpf.plot(df_min, type='line', ax=axs[4], volume=axs[5])

        # --- 加入均线数值标注 (axs[0] 左上方) ---
        last_ma = plot_d.iloc[-1]
        ma_label = (f"MA5:{last_ma['MA5']:.2f}  MA10:{last_ma['MA10']:.2f}  MA20:{last_ma['MA20']:.2f}  "
                    f"MA30:{last_ma['MA30']:.2f}  MA60:{last_ma['MA60']:.2f}  MA120:{last_ma['MA120']:.2f}")
        axs[0].text(0, 1.02, ma_label, transform=axs[0].transAxes, fontsize=10, color='blue', fontproperties=f_prop)

        # 右侧 5 行价格与下载逻辑保持原样
        d_last = plot_d.iloc[-1]
        axs[0].text(1.02, 0.8, f"最高: {d_last['High']:.2f}", transform=axs[0].transAxes, color='red', fontproperties=f_prop)
        axs[0].text(1.02, 0.6, f"最低: {d_last['Low']:.2f}", transform=axs[0].transAxes, color='green', fontproperties=f_prop)
        m_o, m_c, m_h, m_l, y_c = df_daily['Open'].iloc[-1], df_min['Close'].iloc[-1], df_min['High'].max(), df_min['Low'].min(), df_daily['Close'].iloc[-2]
        axs[4].text(1.02, 0.9, f"实时现价: {m_c:.2f}", transform=axs[4].transAxes, color='red', fontweight='bold', fontproperties=f_prop)
        axs[4].text(1.02, 0.7, f"今日开盘: {m_o:.2f}", transform=axs[4].transAxes, color='black', fontproperties=f_prop)
        axs[4].text(1.02, 0.5, f"昨收参考: {y_c:.2f}", transform=axs[4].transAxes, color='gray', fontproperties=f_prop)
        axs[4].text(1.02, 0.3, f"今日最高: {m_h:.2f}", transform=axs[4].transAxes, color='orange', fontproperties=f_prop)
        axs[4].text(1.02, 0.1, f"今日最低: {m_l:.2f}", transform=axs[4].transAxes, color='blue', fontproperties=f_prop)

        titles = ['【日K线均线】', '【日成交量】', '【MACD指标】', '【RPS强度】', f'【实时分时图 {curr_date}】', f'【分时成交量 {curr_date}】']
        for i, (t, c) in enumerate(zip(titles, ['red', 'darkgreen', 'blue', 'purple', 'red', 'darkgreen'])):
            axs[i].text(-0.14, 1.05, t, transform=axs[i].transAxes, color=c, fontsize=12, fontweight='bold', fontproperties=f_prop)
        return fig, df_daily, stock_name
    except Exception as e:
        st.error(f"分析出错: {e}")
        return None, None, None

# --- 5. 接口与网页展示 ---
params = st.query_params
if params.get("mode") == "api":
    f, d, n = generate_analysis(params.get("code", "001228"))
    if d is not None:
        st.json({"name": n, "price": float(d['Close'].iloc[-1]), "rps": float(d['RPS'].iloc[-1])})
    st.stop()

st.title("📈 A股量化查询系统 (云端专业版)")
with st.sidebar:
    query_code = st.text_input("代码", value="001228")
    btn = st.button("生成研报", type="primary")

if btn:
    with st.spinner("处理中..."):
        fig, data, name = generate_analysis(query_code)
        if fig:
            st.pyplot(fig)
            c1, c2 = st.columns(2)
            with c1:
                buf = BytesIO()
                fig.savefig(buf, format="png")
                st.download_button(f"💾 下载 {name} 图表", buf.getvalue(), f"{name}.png")
            with c2:
                st.download_button(f"📊 下载 {name} 数据", data.to_csv().encode('utf-8-sig'), f"{name}.csv")
