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

# --- 1. 页面与字体配置 ---
st.set_page_config(page_title="A股量化深度全景-专业版", layout="wide")

def get_font_prop():
    font_paths = ['/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', 'C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf']
    for path in font_paths:
        if os.path.exists(path): return fm.FontProperties(fname=path)
    return None

@st.cache_data(ttl=3600*24)
def get_smart_name_map():
    try:
        df_new = ak.stock_zh_a_spot_em()[['代码', '名称']]
        return dict(zip(df_new['代码'], df_new['名称']))
    except: return {}

# --- 2. 核心量化引擎 ---
def generate_analysis(code):
    f_prop = get_font_prop()
    name_map = get_smart_name_map()
    stock_name = name_map.get(code, "未知股票")
    
    try:
        # 获取日线(起自2024年初确保RPS计算)与分时
        df_d = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20240101", adjust="qfq")
        df_m = ak.stock_zh_a_hist_min_em(symbol=code, period='1', adjust="qfq")
        if df_d.empty or df_m.empty: return None, None, None

        def clean_df(df, is_min=False):
            t_col = '时间' if is_min else '日期'
            df = df[[t_col, '开盘', '最高', '最低', '收盘', '成交量']]
            df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            return df.astype(float)

        df_daily, df_min_raw = clean_df(df_d), clean_df(df_m, is_min=True)
        df_min = df_min_raw[df_min_raw.index.date == df_min_raw.index.date[-1]]
        curr_date = df_min.index[-1].strftime('%Y-%m-%d')
        
        # 计算 6 条均线与 MACD
        for length in [5, 10, 20, 30, 60, 120]:
            df_daily[f'MA{length}'] = ta.sma(df_daily['Close'], length=length)
        df_daily = pd.concat([df_daily, ta.macd(df_daily['Close'])], axis=1)
        df_daily['RPS'] = (df_daily['Close'] / df_daily['Close'].shift(250)) * 100
        
        # 截取最近 120 交易日(约半年)作为图表红框范围
        plot_d = df_daily.tail(120)
        
        # 绘图逻辑
        mc = mpf.make_marketcolors(up='red', down='green', edge='inherit', wick='inherit', volume='in')
        fig = mpf.figure(style=mpf.make_mpf_style(marketcolors=mc, gridstyle='--'), figsize=(14, 25))
        fig.subplots_adjust(top=0.92, bottom=0.05, left=0.15, right=0.85)
        fig.suptitle(f"{stock_name} ({code}) 量化深度报告", fontsize=24, fontweight='bold', y=0.98, fontproperties=f_prop)
        
        gs = gridspec.GridSpec(6, 1, height_ratios=[6, 2, 2, 2, 5, 2], hspace=0.35)
        axs = [fig.add_subplot(gs[i]) for i in range(6)]
        
        # 指标列识别
        m_c = [c for c in df_daily.columns if 'MACD_' in c and 's' not in c and 'h' not in c][0]
        s_c = [c for c in df_daily.columns if 'MACDs_' in c][0]
        h_c = [c for c in df_daily.columns if 'MACDh_' in c][0]

        ap = [
            mpf.make_addplot(plot_d[['MA5', 'MA10', 'MA20', 'MA30', 'MA60', 'MA120']], ax=axs[0]),
            mpf.make_addplot(plot_d[m_c], ax=axs[2], color='blue'),
            mpf.make_addplot(plot_d[s_c], ax=axs[2], color='orange'),
            mpf.make_addplot(plot_d[h_c], ax=axs[2], type='bar', color='gray', alpha=0.3),
            mpf.make_addplot(plot_d['RPS'], ax=axs[3], color='purple')
        ]
        mpf.plot(plot_d, type='candle', ax=axs[0], volume=axs[1], addplot=ap)
        mpf.plot(df_min, type='line', ax=axs[4], volume=axs[5])

        # 视觉标注：图中 120 日区间最值
        p_high, p_low = float(plot_d['High'].max()), float(plot_d['Low'].min())
        axs[0].text(1.02, 0.8, f"区间最高: {p_high:.2f}", transform=axs[0].transAxes, color='red', fontweight='bold', fontproperties=f_prop)
        axs[0].text(1.02, 0.6, f"区间最低: {p_low:.2f}", transform=axs[0].transAxes, color='green', fontweight='bold', fontproperties=f_prop)

        # 均线与分时数值标注
        last_d = df_daily.iloc[-1]
        ma_txt = f"MA5:{last_d['MA5']:.2f} MA10:{last_d['MA10']:.2f} MA20:{last_d['MA20']:.2f} MA120:{last_d['MA120']:.2f}"
        axs[0].text(0, 1.02, ma_txt, transform=axs[0].transAxes, color='blue', fontproperties=f_prop)

        return fig, df_daily, stock_name
    except Exception as e:
        st.error(f"分析异常: {e}")
        return None, None, None

# --- 3. 深度 API 接口处理 ---
params = st.query_params
if params.get("mode") == "api":
    target_code = params.get("code", "001228")
    fig, df_daily, stock_name = generate_analysis(target_code)
    
    if df_daily is not None:
        latest = df_daily.iloc[-1]
        plot_120 = df_daily.tail(120)
        
        # 提取 30 日 MACD 趋势序列
        macd_c = [c for c in df_daily.columns if 'MACD_' in c and 's' not in c and 'h' not in c][0]
        macds_c = [c for c in df_daily.columns if 'MACDs_' in c][0]
        macdh_c = [c for c in df_daily.columns if 'MACDh_' in c][0]
        
        trend_30d = []
        for idx, row in df_daily.tail(30).iterrows():
            trend_30d.append({
                "date": idx.strftime('%m-%d'),
                "dif": round(float(row[macd_c]), 3),
                "dea": round(float(row[macds_c]), 3),
                "hist": round(float(row[macdh_c]), 3)
            })

        st.json({
            "stock_info": {"name": stock_name, "code": target_code, "query_time": datetime.datetime.now().isoformat()},
            "price_action": {
                "current": float(latest['Close']),
                "change_pct": round(float(((latest['Close']/df_daily['Close'].iloc[-2])-1)*100), 2),
                "range_120d_high": float(plot_120['High'].max()),
                "range_120d_low": float(plot_120['Low'].min())
            },
            "macd_trend_analysis": {
                "description": "最近30个交易日序列数据",
                "history": trend_30d
            },
            "technical_indicators": {
                "rps": round(float(latest['RPS']), 2),
                "ma_values": {f"MA{l}": round(float(latest[f'MA{l}']), 2) for l in [5, 10, 20, 30, 60, 120]}
            },
            "summary_signals": {
                "above_ma120": bool(latest['Close'] > latest['MA120']),
                "short_term_trend": "bullish" if latest['MA5'] > latest['MA20'] else "bearish"
            }
        })
    st.stop()

# --- 4. 网页端 UI ---
st.title("📈 A股量化深度查询系统 (API & 视觉全功能版)")
with st.sidebar:
    input_code = st.text_input("股票代码", value="000630")
    if st.button("开始深度分析", type="primary"):
        with st.spinner("正在获取实时数据并绘制量化图表..."):
            fig, data, name = generate_analysis(input_code)
            if fig:
                st.pyplot(fig)
                st.success(f"{name} 报告生成完毕")
