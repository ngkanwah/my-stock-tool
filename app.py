import streamlit as st
import akshare as ak
import datetime

# --- [模块 1：基础识别信息逻辑] ---
# <BEGIN: get_base_info>
def get_base_info(code):
    """
    根据股票代码获取基础名称和当前查询时间
    """
    try:
        # 获取 A 股实时行情快照
        spot_df = ak.stock_zh_a_spot_em()
        # 匹配对应代码
        target_row = spot_df[spot_df['代码'] == code]
        
        if not target_row.empty:
            return {
                "name": str(target_row.iloc[0]['名称']),
                "code": str(code),
                "query_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        else:
            return {"error": f"未找到股票代码: {code}"}
    except Exception as e:
        return {"error": f"API 抓取失败: {str(e)}"}
# <END: get_base_info>


# --- [模块 2：API 逻辑控制] ---
# 获取 URL 里的参数
params = st.query_params
mode = params.get("mode")
code = params.get("code")

# 如果满足 API 调用条件，直接输出 JSON 并停止运行
if mode == "api" and code:
    res = get_base_info(code)
    st.json(res)
    st.stop()  # 关键：停止后续 UI 渲染，只给 Gemini 返回纯数据


# --- [模块 3：兜底显示 UI] ---
# 如果不是 API 模式，显示一个简单的界面，防止页面空白
st.title("🤖 股票分析智能体接口终端")
st.write("当前状态：**运行正常**")

st.divider()

st.subheader("💡 使用说明")
st.write("请在浏览器地址栏末尾加上以下参数进行测试：")
# 动态显示当前应用的 URL 示例
st.code(f"/?mode=api&code=000630")

st.info("Gemini 接入时，请务必使用上述 ?mode=api 的格式。")

# 网页端的小功能：输入代码手动预览
input_code = st.text_input("手动输入代码预览（例如 600519）", value="000630")
if st.button("查看基础信息"):
    data = get_base_info(input_code)
    st.write(data)
