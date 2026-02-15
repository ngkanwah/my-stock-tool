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
st.set_page_config(page_title="A股量化API系统", layout="wide")

# --- 2. 核心机制：30天硬盘缓存 ---
@st.cache_data
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

# --- 3. 数据分析函数 ---
def get_stock_data(code):
    try:
        name_map = get_smart_name_map()
        stock_name = name_map.get(code, "未知")
        df_d = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20240101", adjust="qfq")
        if df_d.empty: return None, None
        
        # 指标计算
        df_d.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'Turnover', 'Amplitude', 'Chg%', 'ChgVal', 'TurnoverRate']
        df_d['MA5'] = ta.sma(df_d['Close'], length=5)
        df_d['MA20'] = ta.sma(df_d['Close'], length=20)
        macd = ta.macd(df_d['Close'])
        df_d = pd.concat([df_d, macd], axis=1)
        return df_d, stock_name
    except:
        return None, None

# --- 4. 【新增】AI 专用 API 模式判断 ---
# 检查网址是否包含 mode=api 参数
params = st.query_params
if params.get("mode") == "api":
    target_code = params.get("code", "001228")
    data, name = get_stock_data(target_code)
    if data is not None:
        # 只取最近 10 天的数据给 AI 分析，减少字符消耗
        result = {
            "stock_name": name,
            "stock_code": target_code,
            "latest_data": data.tail(10).to_dict(orient='records'),
            "analysis_time": str(datetime.datetime.now())
        }
        st.json(result) # 输出纯 JSON 数据
    else:
        st.write({"error": "Data not found"})
    st.stop() # 强制停止，不加载下方的网页 UI

# --- 5. 原有的网页 UI 逻辑 (generate_analysis 等绘图逻辑放在这里) ---
# ... (此处保留你之前满意的绘图代码) ...
st.title("📈 A股量化查询系统 (云端版)")
# ... 侧边栏和按钮逻辑 ...