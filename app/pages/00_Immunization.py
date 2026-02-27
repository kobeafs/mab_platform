import streamlit as st
import pandas as pd
from datetime import datetime, date
import sys
from pathlib import Path

# --- 1. 基础配置与数据库连接 ---
root_path = Path(__file__).parent.parent
if str(root_path) not in sys.path:
    sys.path.append(str(root_path))

try:
    from db import pb
except ImportError:
    st.error("❌ 无法加载 db.py")
    st.stop()

st.set_page_config(page_title="兔单抗研发数字化平台", layout="wide", page_icon="🐇")
st.title("🐇 兔免疫全景排程数字化看板")


# --- 2. 增强型数据清洗器 (解决报错且保留所有字段) ---

def fetch_safe_data(collection_name):
    """
    白名单模式提取数据：只抓取业务需要的字段，确保类型全为基础类型
    """
    try:
        raw_records = pb.collection(collection_name).get_full_list()
        safe_list = []
        for r in raw_records:
            # 基础字段字典
            d = {"id": str(r.id)}

            # 定义不同集合需要提取的业务字段白名单
            if collection_name == 'animals':
                fields = ['animal_id', 'project_id', 'antigen_nam', 'strain', 'gender', 'status', 'start_date']
            else:  # immunization_logs
                fields = ['animal_id', 'day_point', 'action_type', 'weight_kg', 'titer_value', 'notes']

            for f in fields:
                val = getattr(r, f, "")
                # 处理 None 或 复杂类型
                if val is None:
                    d[f] = ""
                elif isinstance(val, (str, int, float, bool)):
                    d[f] = val
                else:
                    d[f] = str(val)

            # 术语统一映射
            if 'antigen_nam' in d: d['免疫原'] = d['antigen_nam']

            safe_list.append(d)
        return safe_list
    except Exception as e:
        st.error(f"数据抓取失败({collection_name}): {e}")
        return []


# --- 3. 核心业务逻辑：大表打平 ---

def build_full_master_df(animals, logs):
    """
    将一对多关系转换为一行一只兔子的排程大表
    """
    data = []
    from collections import defaultdict
    log_map = defaultdict(list)
    for l in logs:
        log_map[l['animal_id']].append(l)

    for a in animals:
        row = {
            "db_id": a['id'],
            "兔子编号": a['animal_id'],
            "项目ID": a['project_id'],
            "免疫原": a['免疫原'],
            "品系": a['strain'],
            "性别": a['gender'],
            "入舍日期": str(a['start_date'])[:10],
            "当前状态": a['status'],
        }

        # 排序日志
        a_logs = sorted(log_map[a['id']], key=lambda x: x['day_point'])

        # 定义阶段列
        milestones = ["首免", "二免", "三免", "四免", "五免"]
        for m in milestones:
            row[m] = "-"
            row[f"{m}采血?"] = False

        boost_count = 1
        for log in a_logs:
            d_p = log['day_point']
            a_t = log['action_type']
            t_v = log['titer_value']

            info = f"D{d_p}"
            if t_v > 0: info += f" (T:{t_v})"

            # 分配列逻辑
            if "Primary" in a_t:
                row["首免"] = info
                if any(x['action_type'] == "Bleed" and abs(x['day_point'] - d_p) <= 2 for x in a_logs):
                    row["首免采血?"] = True
            elif "Boost" in a_t:
                if boost_count < 5:
                    m_label = milestones[boost_count]
                    row[m_label] = info
                    if any(x['action_type'] == "Bleed" and abs(x['day_point'] - d_p) <= 2 for x in a_logs):
                        row[f"{m_label}采血?"] = True
                    boost_count += 1
        data.append(row)
    return pd.DataFrame(data)


# --- 4. 页面初始化 ---

animals_data = fetch_safe_data('animals')
logs_data = fetch_safe_data('immunization_logs')

t_master, t_reg, t_log = st.tabs(["📅 全景看板管理", "📝 档案管理", "💉 详细记录录入"])

# =========================================================
# TAB 1: 全景看板 (核心功能)
# =========================================================
with t_master:
    # A. 顶部搜索框
    search_q = st.text_input("🔍 搜索看板", placeholder="输入兔子编号、项目ID或免疫原进行筛选...")

    # B. 构造数据
    df_full = build_full_master_df(animals_data, logs_data)

    # 执行过滤
    if search_q:
        mask = (df_full["兔子编号"].str.contains(search_q, case=False) |
                df_full["项目ID"].str.contains(search_q, case=False) |
                df_full["免疫原"].str.contains(search_q, case=False))
        df_display = df_full[mask].reset_index(drop=True)
    else:
        df_display = df_full.reset_index(drop=True)

    # C. 在线编辑器配置
    col_config = {
        "db_id": None,
        "当前状态": st.column_config.SelectboxColumn("状态", options=["Active", "Immunizing", "Terminated"],
                                                     width="small"),
        "兔子编号": st.column_config.TextColumn(disabled=True),
        "项目ID": st.column_config.TextColumn(disabled=True),
    }
    # 开放阶段列的修改权限（用户可以直接改 D21 等内容）
    for m in ["首免", "二免", "三免", "四免", "五免"]:
        col_config[m] = st.column_config.TextColumn(width="medium")
        col_config[f"{m}采血?"] = st.column_config.CheckboxColumn("采血?")

    edited_df = st.data_editor(
        df_display,
        column_config=col_config,
        use_container_width=True,
        hide_index=True,
        key="master_editor_final"
    )

    # D. 保存逻辑 (加固版)
    if st.button("💾 确认并保存全景看板修改"):
        with st.spinner("同步数据库中..."):
            try:
                # 1. 遍历编辑后的每一行
                for _, row in edited_df.iterrows():
                    # 2. 通过 db_id 在原始 display_df 中找到对应的那一行 (防止搜索导致的索引错位)
                    original_row_list = df_display[df_display['db_id'] == row['db_id']]
                    if original_row_list.empty:
                        continue
                    orig = original_row_list.iloc[0]

                    # 3. 检查状态变更
                    if row["当前状态"] != orig["当前状态"]:
                        pb.collection('animals').update(row["db_id"], {"status": row["当前状态"]})

                    # 4. 检查采血复选框同步 (重点逻辑)
                    milestones = ["首免", "二免", "三免", "四免", "五免"]
                    for m in milestones:
                        check_col = f"{m}采血?"

                        # 判断：只有当勾选状态从 False 变为 True 时才触发创建
                        if row[check_col] == True and orig[check_col] == False:
                            imm_info = str(row[m])  # 获取该列内容，如 "D21 (T:128000)"

                            if "D" in imm_info:
                                try:
                                    # 提取数字：从 "D21 (T:xxx)" 中提取出 21
                                    # 先按空格切分取第一段 "D21"，再去掉 "D"
                                    d_str = imm_info.split(" ")[0].replace("D", "")
                                    d_val = int(d_str)

                                    # 向 PocketBase 写入采血记录
                                    pb.collection('immunization_logs').create({
                                        "animal_id": row["db_id"],  # 关联兔子
                                        "action_type": "Bleed",  # 类型设为采血
                                        "day_point": d_val,  # 对应天数
                                        "titer_value": 0,  # 初始效价为0
                                        "notes": f"全景看板一键登记: {m}后采血"
                                    })
                                    st.toast(f"✅ 已为 {row['兔子编号']} 生成 {m} 采血记录")
                                except Exception as parse_err:
                                    st.error(f"解析 {m} 天数失败: {imm_info}")

                st.success("✅ 所有修改已同步至后台！")
                # 强制刷新，使新生成的日志反映到表格中
                st.rerun()

            except Exception as e:
                st.error(f"同步过程中发生错误: {e}")

# =========================================================
# TAB 2: 档案管理 (包含性别、品系)
# =========================================================
with t_reg:
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("📋 详细档案清单")
        if animals_data:
            df_reg = pd.DataFrame(animals_data)[
                ['animal_id', 'project_id', '免疫原', 'strain', 'gender', 'status', 'start_date']]
            st.dataframe(df_reg, use_container_width=True, hide_index=True)
    with c2:
        st.subheader("➕ 录入新动物")
        with st.form("new_rabbit_form"):
            f_id = st.text_input("兔子编号*")
            f_pj = st.text_input("项目ID")
            f_im = st.text_input("免疫原名称")
            cs1, cs2 = st.columns(2)
            f_st = cs1.selectbox("品系", ["NZW 新西兰白兔", "日本大耳兔"])
            f_ge = cs2.selectbox("性别", ["M", "F"])
            f_dt = st.date_input("首免/入舍日期", value=date.today())
            if st.form_submit_button("立即入库"):
                if f_id:
                    pb.collection('animals').create({
                        "animal_id": f_id, "project_id": f_pj, "antigen_nam": f_im,
                        "strain": f_st, "gender": f_ge, "start_date": str(f_dt), "status": "Active"
                    })
                    st.rerun()

# =========================================================
# TAB 3: 详细记录录入 (包含体重、备注、效价)
# =========================================================
with t_log:
    if animals_data:
        sel_label = st.selectbox("🎯 选择操作对象:", [f"{a['animal_id']} | {a['免疫原']}" for a in animals_data])
        sel_id = next(a['id'] for a in animals_data if f"{a['animal_id']} | {a['免疫原']}" == sel_label)

        ca, cb = st.columns([1, 2])
        with ca:
            with st.form("action_log_form"):
                st.markdown("##### ✍️ 录入实验数据")
                i_day = st.number_input("Day Point", value=14, step=1)
                i_act = st.selectbox("操作类型", ["Primary", "Boost", "Bleed", "Titer Check", "Final Boost"])
                cw1, cw2 = st.columns(2)
                i_wei = cw1.number_input("体重 (kg)", 3.0, step=0.1)
                i_tit = cw2.number_input("效价 (Titer)", 0, step=1000)
                i_not = st.text_area("备注", height=100)
                if st.form_submit_button("保存实验记录"):
                    pb.collection('immunization_logs').create({
                        "animal_id": sel_id, "day_point": i_day, "action_type": i_act,
                        "weight_kg": i_wei, "titer_value": i_tit, "notes": i_not
                    })
                    st.rerun()
        with cb:
            st.markdown("##### 📜 历史明细")
            my_logs = sorted([l for l in logs_data if l['animal_id'] == sel_id], key=lambda x: x['day_point'])
            if my_logs:
                df_logs = pd.DataFrame(my_logs)[['day_point', 'action_type', 'weight_kg', 'titer_value', 'notes']]
                st.dataframe(df_logs, use_container_width=True, hide_index=True)