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
import numpy as np

# --- 1. 页面配置与字体 ---
st.set_page_config(page_title="A股量化全景-资金与筹码终极版", layout="wide")

def get_font_prop():
    font_paths = ['/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', 'C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf']
    for path in font_paths:
        if os.path.exists(path): return fm.FontProperties(fname=path)
    return None

# --- 2. 核心量化引擎：筹码、RPS与逐笔分布 ---

def calculate_chips_logic(df_daily, alpha=1.0):
    """筹码衰减模型：计算驻留时间与权重"""
    try:
        history = df_daily.tail(120).copy()
        price_bins = {}
        for _, row in history.iterrows():
            price = round(row['Close'], 2)
            turnover = 0.03 # 模拟日均换手
            for p in list(price_bins.keys()):
                price_bins[p][0] *= (1 - turnover * alpha)
                price_bins[p][1] += 1
            if price not in price_bins: price_bins[price] = [turnover, 1]
            else: price_bins[price][0] += turnover
        return price_bins
    except: return {}

def get_transaction_distribution(code):
    """逐笔数据分析：单笔成交金额分布"""
    try:
        # 获取当日成交明细 (腾讯接口)
        df_tick = ak.stock_zh_a_tick_tx_js(symbol=code)
        if df_tick.empty: return None
        # 计算单笔成交金额 = 价格 * 成交量(手) * 100
        df_tick['amount'] = df_tick['成交价格'] * df_tick['成交量'] * 100
        # 定义分类标准 (单位: 元)
        bins = [0, 40000, 200000, 1000000, float('inf')]
        labels = ['散户', '中单', '大单', '特大单']
        df_tick['level'] = pd.cut(df_tick['amount'], bins=bins, labels=labels)
        dist = df_tick.groupby('level')['amount'].sum()
        total = dist.sum()
        return {label: round((dist[label] / total) * 100, 2) for label in labels}
    except: return None

@st.cache_data(ttl=3600*12)
def get_market_rank_data():
    try:
        df = ak.stock_zh_a_spot_em()
        df['chg'] = pd.to_numeric(df['年初至今涨跌幅'], errors='coerce').fillna(0)
        return df[['代码', '名称', 'chg']].sort_values('chg')
    except: return pd.DataFrame()

# --- 3. 核心分析主函数 ---
def generate_analysis(code):
    f_prop = get_font_prop()
    market_df = get_market_rank_data()
    
    try:
        df_d = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20240101", adjust="qfq")
        df_m = ak.stock_zh_a_hist_min_em(symbol=code, period='1', adjust="qfq")
        if df_d.empty: return None

        df_daily = df_d[['日期','开盘','最高','最低','收盘','成交量']]
        df_daily.columns = ['Date','Open','High','Low','Close','Volume']
        df_daily['Date'] = pd.to_datetime(df_daily['Date']); df_daily.set_index('Date', inplace=True)
        df_daily = df_daily.astype(float)
        
        # 指标计算 (MA + MACD)
        for l in [5, 20, 120]: df_daily[f'MA{l}'] = ta.sma(df_daily['Close'], length=l)
        df_daily = pd.concat([df_daily, ta.macd(df_daily['Close'])], axis=1)
        
        # 结果汇总
        stock_chg = market_df[market_df['代码']==code]['chg'].values[0] if not market_df.empty else 0
        rps_score = round((market_df['chg'] < stock_chg).mean() * 100, 2) if not market_df.empty else 50.0
        chips = calculate_chips_logic(df_daily)
        order_flow = get_transaction_distribution(code)
        
        # 绘图 (K线 + 筹码视觉条)
        plot_d = df_daily.tail(120)
        fig = plt.figure(figsize=(14, 25))
        gs = gridspec.GridSpec(6, 1, height_ratios=[6, 2, 2, 2, 5, 2], hspace=0.35)
        axs = [fig.add_subplot(gs[i]) for i in range(6)]
        
        mc = mpf.make_marketcolors(up='red', down='green', edge='inherit', wick='inherit', volume='in')
        mpf.plot(plot_d, type='candle', ax=axs[0], volume=axs[1], 
                 addplot=[mpf.make_addplot(plot_d[['MA5','MA20','MA120']], ax=axs[0])],
                 style=mpf.make_mpf_style(marketcolors=mc))
        
        # 筹码视觉覆盖
        if chips:
            max_w = max([v[0] for v in chips.values()])
            for p, v in chips.items():
                if plot_d['Low'].min() <= p <= plot_d['High'].max():
                    axs[0].barh(p, (v[0]/max_w)*15, color='orange', alpha=min(v[1]/100, 0.6), height=0.06)

        fig.suptitle(f"({code}) 深度报告 | RPS: {rps_score}", fontsize=22, fontproperties=f_prop)
        axs[0].text(1.02, 0.8, f"区间高: {plot_d['High'].max():.2f}", transform=axs[0].transAxes, color='red', fontproperties=f_prop)
        axs[0].text(1.02, 0.6, f"区间低: {plot_d['Low'].min():.2f}", transform=axs[0].transAxes, color='green', fontproperties=f_prop)

        return fig, df_daily, rps_score, chips, order_flow
    except Exception as e:
        st.error(f"分析失败: {e}"); return None

# --- 4. 深度 API 接口 ---
params = st.query_params
if params.get("mode") == "api":
    code = params.get("code", "000630")
    res = generate_analysis(code)
    if res:
        fig, df_daily, rps, chips, flow = res
        latest = df_daily.iloc[-1]
        macdh_c = [c for c in df_daily.columns if 'MACDh_' in c][0]
        
        st.json({
            "market_rps": rps,
            "order_flow_analysis": {
                "distribution_pct": flow,
                "classification_criteria": {
                    "散户": "<4万", "中单": "4万-20万", "大单": "20万-100万", "特大单": ">100万"
                }
            },
            "chip_structure": {
                "decay_coefficient": 1.0,
                "top_zones": sorted([{"price": k, "stay_days": v[1], "weight": round(v[0], 4)} for k, v in chips.items()], key=lambda x: x['weight'], reverse=True)[:5]
            },
            "price_action": {"current": float(latest['Close']), "range_120d_high": float(df_daily['High'].tail(120).max()), "range_120d_low": float(df_daily['Low'].tail(120).min())},
            "macd_trend_30d": [{"d": i.strftime('%m-%d'), "h": round(float(r[macdh_c]), 3)} for i, r in df_daily.tail(30).iterrows()]
        })
    st.stop()

# --- 5. UI 界面 ---
st.title("📈 A股量化终极版 (逐笔资金+筹码驻留)")
input_code = st.text_input("股票代码", value="000630")
if st.button("全景诊断", type="primary"):
    res = generate_analysis(input_code)
    if res: st.pyplot(res[0])
