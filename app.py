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
st.set_page_config(page_title="A股量化深度分析-专业版", layout="wide")

# --- 2. 核心改进：全平台字体注入 (解决云端/本地乱码) ---
def get_font_prop():
    """自动适配 Linux(云端) 和 Windows(本地) 字体"""
    font_paths = [
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', # Linux 云端文泉驿
        'C:/Windows/Fonts/msyh.ttc',                   # Windows 微软雅黑
        'C:/Windows/Fonts/simhei.ttf'                   # Windows 黑体
    ]
    for path in font_paths:
        if os.path.exists(path):
            return fm.FontProperties(fname=path)
    return None

# --- 3. 30天硬盘缓存机制 ---
@st.cache_data(ttl=3600*24*30)
def get_smart_name_map():
    cache_file = "stock_list_cache.csv"
    if os.path.exists(cache_file):
        try:
            mtime = os.path.getmtime(cache_file)
            if (datetime.datetime.now() - datetime.datetime.fromtimestamp(mtime)).days < 30:
                df_local = pd.read_csv(cache_file, dtype={'代码': str})
                return dict(zip(df_local['代码'], df_local['名称']))
        except: pass
    try:
        df_new = ak.stock_zh_a_spot_em()[['代码', '名称']]
        df_new.to_csv(cache_file, index=False)
        return dict(zip(df_new['代码'], df_new['名称']))
    except: return {}

# --- 4. 专业量化分析函数 ---
def generate_analysis(code):
    f_prop = get_font_prop()
    name_map = get_smart_name_map()
    stock_name = name_map.get(code, "未知股票")
    
    try:
        # 抓取日线与分时
        df_d = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20240101", adjust="qfq")
        df_m = ak.stock_zh_a_hist_min_em(symbol=code, period='1', adjust="qfq")
        if df_d.empty or df_m.empty: return None, None, None

        # 清洗逻辑
        def clean(df, is_min=False):
            t_col = '时间' if is_min else '日期'
            df = df[[t_col, '开盘', '最高', '最低', '收盘', '成交量']]
            df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            return df.astype(float)

        df_daily = clean(df_d)
        df_min = clean(df_m, is_min=True)
        
        # 指标计算：MA, MACD, RPS
        df_daily['MA5'] = ta.sma(df_daily['Close'], length=5)
        df_daily['MA20'] = ta.sma(df_daily['Close'], length=20)
        df_daily['MA60'] = ta.sma(df_daily['Close'], length=60)
        macd = ta.macd(df_daily['Close'])
        df_daily = pd.concat([df_daily, macd], axis=1)
        # 你的 RPS 计算逻辑
        df_daily['RPS'] = (df_daily['Close'] / df_daily['Close'].shift(250)) * 100
        
        # 绘图布局 (居中标题 + 左侧标注)
        plot_d = df_daily.tail(120)
        m_c = [c for c in df_daily.columns if 'MACD_' in c and 's' not in c and 'h' not in c][0]
        s_c = [c for c in df_daily.columns if 'MACDs_' in c][0]
        h_c = [c for c in df_daily.columns if 'MACDh_' in c][0]

        mc = mpf.make_marketcolors(up='red', down='green', edge='inherit', wick='inherit', volume='in')
        s_style = mpf.make_mpf_style(marketcolors=mc, gridstyle='--')
        fig = mpf.figure(style=s_style, figsize=(14, 25))
        fig.subplots_adjust(top=0.92, bottom=0.05, left=0.15, right=0.95)
        
        # 正上方标题
        fig.suptitle(f"{stock_name} ({code}) 综合量化分析报告", 
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

# --- 5. AI API 模式 (数据必须准确) ---
params = st.query_params
if params.get("mode") == "api":
    code = params.get("code", "001228")
    fig, data, name = generate_analysis(code)
    if data is not None:
        # 强制在 JSON 中包含名称，防止 AI 幻觉
        st.json({
            "status": "success",
            "stock_name": name, 
            "stock_code": code,
            "latest_price": float(data['Close'].iloc[-1]),
            "rps_value": float(data['RPS'].iloc[-1]),
            "data_window": data.tail(10).to_dict(orient='records'),
            "server_time": str(datetime.datetime.now())
        })
    else:
        st.json({"status": "error", "message": "Code not found"})
    st.stop()

# --- 6. 网页展示模式 ---
st.title("📈 A股量化查询系统 (云端稳定版)")
with st.sidebar:
    st.header("控制中心")
    query_code = st.text_input("请输入股票代码", value="001228")
    btn = st.button("生成深度量化分析", type="primary")

if btn:
    with st.spinner("系统正在调取最新实时数据..."):
        fig, data, name = generate_analysis(query_code)
        if fig:
            st.pyplot(fig)
            csv = data.to_csv().encode('utf-8-sig')
            st.download_button(f"📊 下载 {name} 数据", csv, f"{name}_{query_code}_data.csv")
        else:
            st.error("分析失败，请检查代码输入或网络状态。")
