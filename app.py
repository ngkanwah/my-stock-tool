import streamlit as st
import akshare as ak
import datetime

# <BEGIN: 1. 基础识别信息获取函数>
# [修改区]
def get_base_info(code):
    """
    根据股票代码获取基础名称和当前查询时间
    """
    try:
        # 获取 A 股实时行情快照（包含名称映射）
        spot_df = ak.stock_zh_a_spot_em()
        # 匹配对应代码的行
        target_row = spot_df[spot_df['代码'] == code]
        
        if not target_row.empty:
            stock_name = target_row.iloc[0]['名称']
            return {
                "name": str(stock_name),
                "code": str(code),
                "query_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        else:
            return {"error": "未找到匹配的股票代码"}
    except Exception as e:
        return {"error": f"基础信息抓取失败: {str(e)}"}
# <END: 1. 基础识别信息获取函数>

# <BEGIN: API 输出测试逻辑>
# 模拟 API 调用的逻辑片段
params = st.query_params
if params.get("mode") == "api":
    target_code = params.get("code", "000630")
    base_data = get_base_info(target_code)
    
    # 按照你协议中的 [元数据节点] 进行映射输出
    st.json({
        "metadata": base_data
    })
# <END: API 输出测试逻辑>
