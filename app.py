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
st.set_page_config(page_title="A股量化全景系统-云端版", layout="wide")

# --- 2. 字体与缓存机制 ---
def get_font_prop():
    # 云端服务器通常是 Linux，不一定有微软雅黑，这里做个保护
    font_paths = ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/msyh.ttc']
    for path in font_paths:
        if os.path.exists(path):
            return fm.FontProperties(fname=path)
    return None

@st.cache_data(ttl=3600*24*30) # 30天超长缓存
def get_smart_name_map():
    cache_file = "stock_list_cache.csv"
    try:
        if os.path.exists(cache_file):
            mtime = os.path.getmtime(cache_file)
            if (datetime.datetime.now() - datetime.datetime.fromtimestamp(mtime)).days < 30:
                df_local = pd.read_csv(cache_file, dtype={'代码': str})
                return dict(zip(df_local['代码'], df_local['名称']))
        df_new = ak.stock_zh_a_spot_em()[['代码', '名称']]
        df_new.to_csv(cache_file, index=False)
        return dict(zip(df_new['代码'], df_new['名称']))
    except: return {}

# --- 3. 核心分析函数 ---
def generate_analysis(code):
    f_prop = get_font_prop()
    name_map = get_smart_name_map()
    stock_name = name_map.get(code, "未知股票")
    
    try:
        # 数据抓取
        df_d = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20240101", adjust="qfq")
        df_m = ak.stock_zh_a_hist_min_em(symbol=code, period='1', adjust="qfq")
        if df_d.empty or df_m.empty: return None, None, None

        # 数据清洗与计算
        def clean(df, is_min=False):
            t_col = '时间' if is_min else '日期'
            df = df[[t_col, '开盘', '最高', '最低', '收盘', '成交量']]
            df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            return df.astype(float)

        df_daily = clean(df_d)
        df_min = clean(df_m, is_min=True)
        df_daily['MA5'] = ta.sma(df_daily['Close'], length=5)
        df_daily['MA20'] = ta.sma(df_daily['Close'], length=20)
        df_daily['MA60'] = ta.sma(df_daily['Close'], length=60)
        macd = ta.macd(df_daily['Close'])
        df_daily = pd.concat([df_daily, macd], axis=1)
        df_daily['RPS'] = (df_daily['Close'] / df_daily['Close'].shift(250)) * 100
        
        # 绘图逻辑 (专业布局)
        plot_d = df_daily.tail(120)
        m_c = [c for c in df_daily.columns if 'MACD_' in c and 's' not in c and 'h' not in c][0]
        s_c = [c for c in df_daily.columns if 'MACDs_' in c][0]
        h_c = [c for c in df_daily.columns if 'MACDh_' in c][0]

        mc = mpf.make_marketcolors(up='red', down='green', edge='inherit', wick='inherit', volume='in')
        s_style = mpf.make_mpf_style(marketcolors=mc, gridstyle='--')
        fig = mpf.figure(style=s_style, figsize=(14, 25))
        fig.subplots_adjust(top=0.92, bottom=0.05, left=0.15, right=0.95)
        
        # 居中大标题
        fig.suptitle(f"{stock_name} ({code}) 综合全景分析报告", 
                     fontsize=24, fontweight='bold', y=0.98, fontproperties=f_prop)
        
        gs = gridspec.GridSpec(6, 1, height_ratios=[6, 2, 2, 2, 5, 2], hspace=0.35)
        axs = [fig.add_subplot(gs[i]) for i in range(6)]
        
        ap = [
            mpf.make_addplot(plot_d[['MA5', 'MA20', 'MA60']], ax=axs[0]),
            mpf.make_addplot(plot_d[m_c], ax=axs[2], color='blue'),
            mpf.make_addplot(plot_d[s_c], ax=axs[2], color='orange'),
            mpf.make_addplot(plot_d[h_c], ax=axs[2], type='bar', color='gray', alpha=0.3),
            mpf.make_addplot(plot_d['RPS'], ax=axs[3], color='purple')
        ]
        mpf.plot(plot_d, type='candle', ax=axs[0], volume=axs[1], addplot=ap)
        mpf.plot(df_min, type='line', ax=axs[4], volume=axs[5])

        # 侧边小标题
        titles = ['【日K线均线】', '【日成交量】', '【MACD指标】', '【RPS强度】', '【实时分时图】', '【分时成交量】']
        colors = ['red', 'darkgreen', 'blue', 'purple', 'red', 'darkgreen']
        for i, (t, c) in enumerate(zip(titles, colors)):
            axs[i].text(-0.14, 1.05, t, transform=axs[i].transAxes, color=c, 
                        fontsize=12, fontweight='bold', fontproperties=f_prop)
        
        return fig, df_daily, stock_name
    except: return None, None, None

# --- 4. AI 专用 API 模式 ---
params = st.query_params
if params.get("mode") == "api":
    code = params.get("code", "001228")
    fig, data, name = generate_analysis(code)
    if data is not None:
        st.json({
            "name": name, 
            "latest_price": data['Close'].iloc[-1],
            "data": data.tail(10).to_dict(orient='records')
        })
    st.stop()

# --- 5. 网页 UI 模式 ---
st.title("📈 A股量化查询系统 (云端版)")
with st.sidebar:
    st.header("控制中心")
    query_code = st.text_input("请输入股票代码", value="001228")
    btn = st.button("开始生成深度报告", type="primary")

if btn:
    with st.spinner("数据调取中..."):
        fig, data, name = generate_analysis(query_code)
        if fig:
            st.pyplot(fig)
            csv = data.to_csv().encode('utf-8-sig')
            st.download_button(f"📊 下载 {name} 数据", csv, f"{name}_data.csv")
        else:
            st.error("分析失败，请检查代码。")
