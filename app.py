import streamlit as st
import akshare as ak
import datetime
import pandas as pd

# <BEGIN: 1. 全市场名称映射引擎>
# [修改区] ttl 设置为 2592000 秒（即 30 天）
@st.cache_data(ttl=3600*24*30)
def get_full_market_map():
    """
    一次性抓取全 A 股名单并缓存 30 天
    """
    try:
        # 抓取全市场实时快照数据
        df = ak.stock_zh_a_spot_em()
        # 建立 代码 -> 名称 的字典映射，方便极速查询
        return dict(zip(df['代码'], df['名称']))
    except Exception as e:
        # 如果抓取失败，返回空字典，防止程序崩溃
        return {}
# <END: 1. 全市场名称映射引擎>

# <BEGIN: 2. 基础信息解析逻辑>
def get_metadata(code, name_map):
    """
    1. 股票名称
    2. 股票代码
    3. 查询时间
    """
    code_str = str(code).zfill(6) # 自动补齐 6 位代码
    stock_name = name_map.get(code_str, "未知股票")
    
    return {
        "股票名称": stock_name,
        "股票代码": code_str,
        "查询时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
# <END: 2. 基础信息解析逻辑>

# --- API 逻辑处理 ---
params = st.query_params
mode = params.get("mode")
target_code = params.get("code")

# 预加载名称库
name_map = get_full_market_map()

if mode == "api" and target_code:
    # 获取基础三项数据
    metadata = get_metadata(target_code, name_map)
    
    # 纯 JSON 输出，供 Gemini 采集
    st.json({
        "metadata": metadata
    })
    st.stop()

# --- 网页调试 UI ---
st.title("🛡️ 稳定版 API 终端")
if name_map:
    st.success(f"✅ 全市场名单已就绪（缓存有效期：30天），共计 {len(name_map)} 只个股。")
else:
    st.error("❌ 名单抓取失败，请检查网络或重新发布。")

test_code = st.text_input("测试代码", value="000630")
if st.button("查看基础信息"):
    st.write(get_metadata(test_code, name_map))

