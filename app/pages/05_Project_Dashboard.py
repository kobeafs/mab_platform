import streamlit as st

if "is_logged_in" not in st.session_state or not st.session_state.is_logged_in:
    st.warning("请先回到主页进行登录")
    st.stop()
import streamlit as st
import pandas as pd
import json
import sys
import os

# --- 路径设置 ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import fetch_all_experiments

st.set_page_config(page_title="Project Dashboard", layout="wide", page_icon="🕵️‍♂️")
st.title("🕵️‍♂️ 全景看板 (Debug Mode)")


# ==========================================
# 1. 数据加载与诊断
# ==========================================
# 去掉缓存，确保每次都读最新的
def load_data():
    return fetch_all_experiments()


try:
    all_records = load_data()
except Exception as e:
    st.error(f"严重错误：无法连接数据库。请检查 db.py 或 PocketBase 是否运行。\n错误信息: {e}")
    st.stop()

# --- 🔍 调试区域 (上线后可以折叠或删除) ---
with st.expander("🛠️ 数据库连接诊断 (读不到数据点这里)", expanded=False):
    st.write(f"**数据库连接状态**: 成功")
    st.write(f"**总记录数**: {len(all_records)} 条")

    if len(all_records) > 0:
        st.write("👇 最近一条数据的原始样貌 (Raw JSON):")
        st.json(all_records[0])  # 显示第一条数据，看看长什么样
    else:
        st.warning("数据库是空的！请先去 ELISA/SPR 页面上传并保存一条数据。")

# ==========================================
# 2. 搜索逻辑 (暴力全文搜索版)
# ==========================================
search_term = st.text_input("🔍 输入关键词 (克隆号/项目号/日期)", placeholder="例如: Sample").strip()

if search_term:
    found_records = []

    # --- 暴力搜索核心 ---
    # 不管 Key 是什么，把整个 JSON 转成字符串查
    for record in all_records:
        # 把整条记录转成字符串
        record_str = str(record).lower()

        # 只要包含了关键词，就认为命中
        if search_term.lower() in record_str:
            found_records.append(record)

    # ==========================================
    # 3. 结果展示
    # ==========================================
    if found_records:
        st.success(f"🎉 找到 {len(found_records)} 条相关记录")

        for rec in found_records:
            r_id = rec.get('id', 'Unknown')
            proj = rec.get('project_id', 'No Project')
            user = rec.get('researcher', 'No User')
            date = rec.get('created', '')[:10]
            data = rec.get('result_json', {})

            if isinstance(data, str):
                try:
                    import json

                    data = json.loads(data)
                except:
                    pass

            with st.container():
                st.markdown(f"### 📂 项目: {proj}")
                st.caption(f"ID: {r_id} | User: {user} | Date: {date}")

                if isinstance(data, dict):
                    found_table = False

                    # 1. 自动探测：遍历所有字段，只要值是“列表”且包含“字典”，就转为表格
                    for key, value in data.items():
                        if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                            st.info(f"📊 数据表: {key}")
                            st.dataframe(pd.DataFrame(value), use_container_width=True)
                            found_table = True

                    # 2. 特殊逻辑：针对没有嵌套在 Key 里的纯列表数据
                    if not found_table and isinstance(data, list):
                        st.dataframe(pd.DataFrame(data), use_container_width=True)
                        found_table = True

                    # 3. 特殊逻辑：BCA 或其他非列表结构
                    if not found_table:
                        if 'conc_matrix' in data or 'r2' in data:
                            st.warning("🧪 定量/曲线数据")
                            col1, col2 = st.columns(2)
                            if 'r2' in data: col1.metric("R²", data['r2'])
                            if 'equation' in data: st.code(f"方程: {data['equation']}")
                        else:
                            st.caption("详细数据 (JSON):")
                            st.json(data)
                else:
                    st.write(data)

                st.divider()