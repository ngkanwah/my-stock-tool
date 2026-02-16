import streamlit as st
import akshare as ak
import datetime
import pandas as pd

# --- [模块 1：业务逻辑] ---
# <BEGIN: get_base_info_fast>
def get_base_info_fast(code):
    """
    使用更轻量的接口获取基础信息，增加错误处理
    """
    try:
        # 改用单个股票的历史快照接口，速度比全市场扫描快得多
        # 只需要抓取最近 1 天的数据来获取名称
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20250101", adjust="qfq")
        
        # 获取名称通常需要从 spot 接口，如果全扫描太慢，我们尝试备用逻辑
        # 这里先尝试获取一次
        try:
            name_data = ak.stock_individual_info_em(symbol=code)
            stock_name = name_data[name_data['item'] == '股票名称']['value'].values[0]
        except:
            stock_name = "未知名称 (获取超时)"

        return {
            "status": "success",
            "name": str(stock_name),
            "code": str(code),
            "query_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
# <END: get_base_info_fast>


# --- [模块 2：逻辑控制与可视化调试] ---
st.write("### 🔍 诊断面板")
params = st.query_params
st.write("当前收到参数:", params.to_dict())

mode = params.get("mode")
code = params.get("code")

if mode == "api" and code:
    with st.spinner('正在调取实时数据...'):
        res = get_base_info_fast(code)
        # 重点：先打印出来，再渲染 JSON，确保我们能看到数据
        st.write("API 返回结果预览:", res)
        st.json(res)
    # 暂时注释掉 st.stop()，以便你能看到诊断面板
    # st.stop() 
else:
    st.warning("⚠️ 检测到未带参数或参数错误。")
    st.info("请尝试访问：`?mode=api&code=000630` (请手动点击浏览器地址栏并在末尾粘贴)")

# 网页端手动测试
st.divider()
input_code = st.text_input("手动测试输入代码", value="000630")
if st.button("立即抓取"):
    data = get_base_info_fast(input_code)
    st.write(data)
