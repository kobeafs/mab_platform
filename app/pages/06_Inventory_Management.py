import streamlit as st

if "is_logged_in" not in st.session_state or not st.session_state.is_logged_in:
    st.warning("请先回到主页进行登录")
    st.stop()
import streamlit as st
import sys
from pathlib import Path
import pandas as pd
import plotly.express as px

# 1. 路径与数据库导入
root_path = Path(__file__).parent.parent
if str(root_path) not in sys.path:
    sys.path.append(str(root_path))

try:
    from db import pb
except ImportError:
    st.error("未能找到数据库连接对象 pb")

from utils.inventory_modules.inventory_logic import (
    get_96_well_struct, format_db_to_grid, generate_excel_template, process_excel_upload
)

st.set_page_config(layout="wide", page_title="企业级库存管理", page_icon="📦")


# --- 辅助函数：物理层级构建 ---
def fetch_all_inventory():
    try:
        return pb.collection('inventory').get_full_list()
    except:
        return []


@st.cache_data(ttl=10)
def fetch_box_grid(box_name):
    try:
        recs = pb.collection('inventory').get_full_list(query_params={"filter": f'box_name = "{box_name}"'})
        return format_db_to_grid(recs)
    except:
        return {}


# 加载全局数据
all_records = fetch_all_inventory()

# 构建 Rack -> Box 的映射关系
hierarchy = {}
for r in all_records:
    rid = getattr(r, 'rack_id', 'Unassigned')
    bid = r.box_name
    if rid not in hierarchy: hierarchy[rid] = set()
    hierarchy[rid].add(bid)
hierarchy = {k: sorted(list(v)) for k, v in sorted(hierarchy.items())}

st.title("📦 企业级样本库管理平台")
tab_view, tab_search, tab_stats = st.tabs(["📍 物理坐标视图", "🔍 全局搜索", "📊 库存统计"])

# ==========================================
# Tab 1: 物理坐标视图 (Rack -> Box -> Slot)
# ==========================================
with tab_view:
    with st.sidebar:
        st.header("🏢 位置定位")
        # 1. 选择架子
        rack_options = list(hierarchy.keys()) if hierarchy else ["Rack-01"]
        sel_rack = st.selectbox("1. 选择存放架 (Rack)", options=rack_options)

        # 2. 选择该架子下的盒子
        box_options = hierarchy.get(sel_rack, ["Box-001"])
        sel_box = st.selectbox("2. 选择冻存盒 (Box)", options=box_options)

        # 3. 快速跳转或创建
        st.divider()
        with st.expander("✨ 新增存储位置"):
            new_r = st.text_input("新架子号")
            new_b = st.text_input("新盒子号")

        target_rack = new_r if new_r else sel_rack
        target_box = new_b if new_b else sel_box

        st.divider()
        st.header("📤 批量导入")
        st.download_button("📥 下载模板", data=generate_excel_template(), file_name="Template.xlsx")
        up_file = st.file_uploader("上传 Excel", type=["xlsx"])
        if up_file and st.button("🚀 开始导入"):
            df, msg = process_excel_upload(up_file)
            if df is not None:
                prog = st.progress(0)

                # --- 1. 初始化差异追踪列表 ---
                import_history = []

                for i, row in df.iterrows():
                    payload = {
                        "rack_id": str(row.get('rack_id', target_rack)),
                        "box_name": str(row.get('box_name', target_box)),
                        "slot": row['slot'],
                        "sample_id": str(row['sample_id']),
                        "project_name": row.get('project_name', '未分类'),
                        "sample_type": row.get('sample_type', 'Purified mAb'),
                        "conc_mgml": float(row.get('conc_mgml', 0)),
                        "vol_ul": float(row.get('vol_ul', 0))
                    }
                    try:
                        # 检查孔位是否存在
                        exist = pb.collection('inventory').get_full_list(query_params={
                            "filter": f'box_name="{payload["box_name"]}" && slot="{payload["slot"]}"'
                        })

                        if exist:
                            # --- 记录更新前的快照 ---
                            old_record = exist[0]
                            import_history.append({
                                "slot": payload["slot"],
                                "action": "update",
                                "before": {"sample_id": old_record.sample_id, "conc": old_record.conc_mgml},
                                "after": {"sample_id": payload["sample_id"], "conc": payload["conc_mgml"]}
                            })
                            pb.collection('inventory').update(old_record.id, payload)
                        else:
                            # --- 记录新增快照 ---
                            import_history.append({
                                "slot": payload["slot"],
                                "action": "create",
                                "before": {},
                                "after": {"sample_id": payload["sample_id"], "slot": payload["slot"]}
                            })
                            pb.collection('inventory').create(payload)
                    except Exception as e:
                        print(f"行 {i} 处理失败: {e}")

                    prog.progress((i + 1) / len(df))

                # --- 2. 循环结束后，记录一次性详细审计日志 ---
                from utils.system_logic import add_log

                operator_name = st.session_state.user_info.email if "user_info" in st.session_state else "Admin"

                add_log(
                    pb,
                    operator=operator_name,
                    module="库存管理",
                    action="Excel批量导入",
                    details=f"从文件 {up_file.name} 导入了 {len(df)} 条记录",
                    old_data={"description": "批量操作前状态"},
                    new_data={"import_summary": import_history}  # 核心：这里存入了每一行的变动明细
                )
                # ------------------------------------------

                st.success(f"成功处理 {len(df)} 条记录！")
                st.cache_data.clear()
                st.rerun()
    # 渲染 96 孔板
    box_grid = fetch_box_grid(target_box)
    rows, cols = get_96_well_struct()
    st.subheader(f"📍 当前位置：{target_rack} / {target_box}")

    # 渲染矩阵
    h_cols = st.columns([0.5] + [1] * 12)
    for i, t in enumerate([""] + cols): h_cols[i].write(f"**{t}**")
    for r in rows:
        r_cols = st.columns([0.5] + [1] * 12)
        r_cols[0].write(f"**{r}**")
        for c_idx, c in enumerate(cols):
            slot_id = f"{r}{c}"
            smpl = box_grid.get(slot_id)
            b_type = "primary" if smpl else "secondary"
            b_label = f"{smpl['sample_id'][:5]}" if smpl else " "
            if r_cols[c_idx + 1].button(b_label, key=f"grid_{slot_id}", use_container_width=True, type=b_type):
                st.session_state.selected_slot = slot_id

    # 编辑面板
    if st.session_state.get('selected_slot'):
        slot = st.session_state.selected_slot
        curr = box_grid.get(slot, {})
        st.divider()
        st.subheader(f"🔍 孔位编辑: {slot}")
        with st.form("edit_form"):
            f1, f2, f3, f4, f5 ,f6 = st.columns(6)
            n_rack = f1.text_input("架子号", value=curr.get("rack_id", target_rack))
            n_prj = f2.text_input("项目名", value=curr.get("project_name", ""))
            n_sid = f3.text_input("样本ID", value=curr.get("sample_id", ""))
            n_typ = f4.selectbox("类型", ["Purified mAb", "Serum", "Plasmid"], index=0)
            n_con = f5.number_input("浓度", value=float(curr.get("conc_mgml", 0.0)))
            n_vol = f6.number_input("体积", value=float(curr.get("vol_ul", 0.0)))
            if st.form_submit_button("保存"):
                save_data = {
                    "rack_id": n_rack, "box_name": target_box, "slot": slot,
                    "project_name": n_prj, "sample_id": n_sid,
                    "sample_type": n_typ, "conc_mgml": n_con, "vol_ul": n_vol
                }
                try:
                    # --- 1. 准备快照数据 ---
                    if curr:
                        # 如果是更新，curr 变量里已经存了旧数据（来自之前的 fetch_box_grid）
                        # 我们把 save_data 中涉及的字段提取出来作为“旧值”
                        old_val = {k: curr.get(k) for k in save_data.keys()}

                        # 执行更新
                        pb.collection('inventory').update(curr['id'], save_data)
                        action_type = "更新孔位"
                        new_val = save_data
                    else:
                        # 如果是新增，旧值就是 None
                        old_val = None

                        # 执行创建
                        pb.collection('inventory').create(save_data)
                        action_type = "新增孔位"
                        new_val = save_data

                    # --- 2. 记录增强版日志 ---
                    from utils.system_logic import add_log

                    # 获取当前操作人邮箱（适配你 main.py 里的登录逻辑）
                    operator_name = "Admin"
                    if "user_info" in st.session_state:
                        operator_name = st.session_state.user_info.email

                    add_log(
                        pb,
                        operator=operator_name,
                        module="库存管理",
                        action=action_type,
                        details=f"在盒子 {target_box} 的 {slot} 孔位操作了样本 {n_sid}",
                        old_data=old_val,  # 传入旧数据
                        new_data=new_val  # 传入新数据
                    )
                    # -----------------------

                    st.success("已保存并记录审计快照")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"保存失败: {e}")
# ==========================================
# Tab 2: 全局搜索 (多维度过滤)
# ==========================================
with tab_search:
    st.subheader("🔍 全局追溯搜索")
    s_col1, s_col2 = st.columns([2, 1])
    kw = s_col1.text_input("关键词 (样本 ID)", placeholder="输入 ID...")
    prjs = s_col2.multiselect("项目过滤",
                              options=sorted(list(set([getattr(r, 'project_name', '未分类') for r in all_records]))))

    filtered = all_records
    if kw: filtered = [r for r in filtered if kw.lower() in r.sample_id.lower()]
    if prjs: filtered = [r for r in filtered if getattr(r, 'project_name', '') in prjs]

    if filtered:
        df_search = pd.DataFrame([{
            "项目": getattr(r, 'project_name', '未分类'),
            "样本 ID": r.sample_id,
            "架子 (Rack)": getattr(r, 'rack_id', 'N/A'),
            "盒子 (Box)": r.box_name,
            "孔位": r.slot,
            "类型": r.sample_type,
            "时间": str(r.created)[:10]
        } for r in filtered])
        st.dataframe(df_search, use_container_width=True)
        st.download_button("📥 导出结果", df_search.to_csv(index=False).encode('utf-8-sig'), "search.csv", "text/csv")

# ==========================================
# Tab 3: 库存统计 (可视化)
# ==========================================
with tab_stats:
    if all_records:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("总样本", len(all_records))
        m2.metric("总架子", len(hierarchy.keys()))
        m3.metric("总盒子", len(set([r.box_name for r in all_records])))
        m4.metric("项目数", len(set([getattr(r, 'project_name', '') for r in all_records])))

        st.divider()
        gr1, gr2 = st.columns(2)
        with gr1:
            st.write("**架子占用分布 (Rack Usage)**")
            r_counts = pd.Series([getattr(r, 'rack_id', '未归档') for r in all_records]).value_counts()
            st.bar_chart(r_counts)
        with gr2:
            st.write("**样本类型占比**")
            t_counts = pd.Series([r.sample_type for r in all_records]).value_counts()
            fig = px.pie(values=t_counts.values, names=t_counts.index, hole=0.4)
            fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("暂无库存数据")