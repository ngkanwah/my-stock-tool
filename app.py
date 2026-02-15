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

# --- 1. 基础配置 ---
st.set_page_config(page_title="A股量化全景-RPS全市场增强版", layout="wide")

def get_font_prop():
    font_paths = ['/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', 'C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf']
    for path in font_paths:
        if os.path.exists(path): return fm.FontProperties(fname=path)
    return None

# --- 2. 新增：全市场 RPS 排名计算引擎 ---
@st.cache_data(ttl=3600*12) # 12小时更新一次全市场分布
def get_market_rps_dist():
    """获取全市场股票的年度涨幅分布，用于计算相对强度排名"""
    try:
        # 获取全市场实时快照（包含年初至今等信息）
        df_spot = ak.stock_zh_a_spot_em()
        # 计算年度近似涨幅（以6个月或年初至今作为权重）
        df_spot['yearly_change'] = pd.to_numeric(df_spot['年初至今涨跌幅'], errors='coerce').fillna(0)
        return df_spot[['代码', 'yearly_change']].sort_values('yearly_change')
    except:
        return pd.DataFrame()

def calculate_stock_rps(stock_code, market_df):
    """计算个股在全市场的百分位排名"""
    if market_df.empty: return 50.0 # 默认中值
    try:
        # 找到个股的年度涨幅
        stock_change = market_df[market_df['代码'] == stock_code]['yearly_change'].values[0]
        # 计算百分比排名 (Percentile Rank)
        rank = (market_df['yearly_change'] < stock_change).mean() * 100
        return round(rank, 2)
    except:
        return 50.0

@st.cache_data(ttl=3600*24)
def get_smart_name_map():
    try:
        df_new = ak.stock_zh_a_spot_em()[['代码', '名称']]
        return dict(zip(df_new['代码'], df_new['名称']))
    except: return {}

# --- 3. 核心量化引擎 ---
def generate_analysis(code):
    f_prop = get_font_prop()
    name_map = get_smart_name_map()
    market_df = get_market_rps_dist() # 获取全市场分布
    
    stock_name = name_map.get(code, "未知股票")
    market_rps = calculate_stock_rps(code, market_df) # 计算全市场RPS
    
    try:
        df_d = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20240101", adjust="qfq")
        df_m = ak.stock_zh_a_hist_min_em(symbol=code, period='1', adjust="qfq")
        if df_d.empty: return None, None, None

        def clean_df(df, is_min=False):
            t_col = '时间' if is_min else '日期'
            df = df[[t_col, '开盘', '最高', '最低', '收盘', '成交量']]
            df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            return df.astype(float)

        df_daily = clean_df(df_d)
        df_min_raw = clean_df(df_m, is_min=True)
        df_min = df_min_raw[df_min_raw.index.date == df_min_raw.index.date[-1]]
        
        # 指标计算
        for length in [5, 10, 20, 60, 120]:
            df_daily[f'MA{length}'] = ta.sma(df_daily['Close'], length=length)
        df_daily = pd.concat([df_daily, ta.macd(df_daily['Close'])], axis=1)
        
        plot_d = df_daily.tail(120)
        p_high, p_low = float(plot_d['High'].max()), float(plot_d['Low'].min())
        
        # 绘图逻辑
        mc = mpf.make_marketcolors(up='red', down='green', edge='inherit', wick='inherit', volume='in')
        fig = mpf.figure(style=mpf.make_mpf_style(marketcolors=mc, gridstyle='--'), figsize=(14, 25))
        fig.subplots_adjust(top=0.92, bottom=0.05, left=0.15, right=0.85)
        
        # 标题加入全市场 RPS
        fig.suptitle(f"{stock_name} ({code}) | 全市场 RPS: {market_rps}", fontsize=24, fontweight='bold', fontproperties=f_prop)
        
        gs = gridspec.GridSpec(6, 1, height_ratios=[6, 2, 2, 2, 5, 2], hspace=0.35)
        axs = [fig.add_subplot(gs[i]) for i in range(6)]
        
        # MACD 列名
        m_c = [c for c in df_daily.columns if 'MACD_' in c and 's' not in c and 'h' not in c][0]
        s_c = [c for c in df_daily.columns if 'MACDs_' in c][0]
        h_c = [c for c in df_daily.columns if 'MACDh_' in c][0]

        ap = [
            mpf.make_addplot(plot_d[['MA5', 'MA10', 'MA20', 'MA60', 'MA120']], ax=axs[0]),
            mpf.make_addplot(plot_d[m_c], ax=axs[2], color='blue'),
            mpf.make_addplot(plot_d[s_c], ax=axs[2], color='orange'),
            mpf.make_addplot(plot_d[h_c], ax=axs[2], type='bar', color='gray', alpha=0.3)
        ]
        mpf.plot(plot_d, type='candle', ax=axs[0], volume=axs[1], addplot=ap)
        mpf.plot(df_min, type='line', ax=axs[4], volume=axs[5])

        # 视觉标注
        axs[0].text(1.02, 0.8, f"区间最高: {p_high:.2f}", transform=axs[0].transAxes, color='red', fontweight='bold', fontproperties=f_prop)
        axs[0].text(1.02, 0.6, f"区间最低: {p_low:.2f}", transform=axs[0].transAxes, color='green', fontweight='bold', fontproperties=f_prop)
        
        # 增加全市场 RPS 标注在图表显眼位置
        color_rps = 'red' if market_rps > 80 else 'black'
        axs[0].text(0.02, 0.9, f"全市场相对强度(RPS): {market_rps}", transform=axs[0].transAxes, fontsize=14, color=color_rps, fontweight='bold', fontproperties=f_prop)

        return fig, df_daily, stock_name, market_rps
    except Exception as e:
        st.error(f"分析出错: {e}")
        return None, None, None, None

# --- 4. 深度 API 接口 ---
params = st.query_params
if params.get("mode") == "api":
    target_code = params.get("code", "001228")
    fig, df_daily, stock_name, market_rps = generate_analysis(target_code)
    
    if df_daily is not None:
        latest = df_daily.iloc[-1]
        
        # 提取 30 日 MACD 序列
        macd_c = [c for c in df_daily.columns if 'MACD_' in c and 's' not in c and 'h' not in c][0]
        macds_c = [c for c in df_daily.columns if 'MACDs_' in c][0]
        macdh_c = [c for c in df_daily.columns if 'MACDh_' in c][0]
        
        trend_30d = [{"d": i.strftime('%m-%d'), "h": round(float(r[macdh_c]), 3)} for i, r in df_daily.tail(30).iterrows()]

        st.json({
            "stock_info": {"name": stock_name, "code": target_code},
            "market_rps": market_rps, # 新增全市场排名
            "price_action": {
                "current": float(latest['Close']),
                "range_120d_high": float(df_daily['High'].tail(120).max()),
                "range_120d_low": float(df_daily['Low'].tail(120).min())
            },
            "macd_trend": {"description": "30日历史序列", "history": trend_30d},
            "ma_values": {f"MA{l}": round(float(latest[f'MA{l}']), 2) for l in [5, 20, 120]}
        })
    st.stop()

# --- 5. UI 展示 ---
st.title("📈 A股量化查询系统 - 全市场 RPS 增强版")
with st.sidebar:
    input_code = st.text_input("代码", value="000630")
    if st.button("生成研报", type="primary"):
        fig, data, name, rps = generate_analysis(input_code)
        if fig: st.pyplot(fig)
