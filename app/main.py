import streamlit as st
import sys
import pandas as pd
from pathlib import Path

# --- 1. 确保能找到 db.py ---
root_path = Path(__file__).parent
if str(root_path) not in sys.path:
    sys.path.append(str(root_path))

try:
    # 导入 db 里的 pb 对象和登录工具
    from db import pb, login_auth, logout
except ImportError:
    st.error("无法加载 db.py，请检查文件路径")
    st.stop()

# --- 2. 页面基本配置 ---
st.set_page_config(
    page_title="兔单抗数字化研发平台",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 3. 注入自定义 CSS (让卡片和布局更高级) ---
st.markdown("""
    <style>
    .stApp { background-color: #fcfcfc; }
    .module-card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #e6e9ef;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
        min-height: 200px;
        transition: transform 0.3s;
    }
    .module-card:hover {
        transform: translateY(-5px);
        border-color: #007BFF;
    }
    .module-header {
        color: #1f77b4;
        font-weight: bold;
        margin-bottom: 10px;
        font-size: 1.1rem;
    }
    /* 搜索结果高亮 */
    .search-highlight {
        border: 2px solid #ff4b4b;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 20px;
        background-color: #fff5f5;
    }
    header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 4. 登录逻辑拦截 ---
if "is_logged_in" not in st.session_state:
    st.session_state.is_logged_in = False

if not st.session_state.is_logged_in:
    st.container()
    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        st.markdown("<h2 style='text-align: center;'>🧬 数字化研发平台登录</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>请输入您的实验账号以继续</p>", unsafe_allow_html=True)

        with st.form("login_form"):
            email = st.text_input("邮箱 (Email)")
            password = st.text_input("密码 (Password)", type="password")
            submitted = st.form_submit_button("立即登录", use_container_width=True)

            if submitted:
                if email and password:
                    success, msg = login_auth(email, password)
                    if success:
                        st.success("登录成功，正在进入系统...")
                        st.rerun()
                    else:
                        st.error(f"登录失败: {msg}")
                else:
                    st.warning("请完整填写账号信息")
    st.stop()

# --- 5. 侧边栏 (已登录状态) & 全局搜索功能 ---
user_info = st.session_state.user_info
with st.sidebar:
    st.markdown("## 🧬 mAb Platform")
    st.caption("v2.6 | 数字化实验室系统") # 版本号升级

    # [新增] 全局搜索框
    st.divider()
    search_term = st.text_input("🔍 全局搜索 (Sample ID)", placeholder="输入 RAB 编号...")

    st.divider()
    # 动态显示用户信息
    st.success(f"🟢 **在线**: {user_info.email}")
    st.info(f"👤 **角色**: {getattr(user_info, 'role', 'Researcher').upper()}")

    if st.button("退出系统", use_container_width=True):
        logout()

    st.divider()
    st.info("💡 **提示**: 选择左侧功能进入具体实验分析或样本库管理。")

# --- 6. 主界面头部 ---
st.title("🧬 兔单抗数据处理与样本库管理平台")
st.markdown("##### 驱动研发提效，打通从“抗原”到“交付”的每一行数据")

# --- [V4.0 全局搜索逻辑] ---
if search_term:
    st.markdown('<div class="search-highlight">', unsafe_allow_html=True)
    st.subheader(f"🔍 全局搜索结果: '{search_term}'")

    # 存储找到的库存 ID，用于后续联查实验
    found_sample_ids = []

    # ==========================================
    # 1. 搜库存 (Inventory)
    # ==========================================
    try:
        inv_res = pb.collection('inventory').get_list(
            page=1, per_page=20,
            query_params={"filter": f'sample_id~"{search_term}"', "sort": "-created"}
        )

        if inv_res.items:
            st.markdown(f"**📦 库存记录 ({inv_res.total_items})**")
            found_sample_ids = [item.id for item in inv_res.items]

            data_list = []
            for item in inv_res.items:
                data_list.append({
                    "架号": getattr(item, "rack_id", "-"),
                    "项目号": getattr(item, "project_name", getattr(item, "project_id", "-")),
                    "样本 ID": item.sample_id,
                    "类型": getattr(item, "sample_type", "-"),
                    "浓度": getattr(item, "conc_mgml", 0),
                    "体积": getattr(item, "vol_ul", 0),
                    "位置": f"{item.box_name}-{item.slot}"
                })

            df_inv = pd.DataFrame(data_list)
            cols_order = ["架号", "项目号", "样本 ID", "类型", "浓度", "体积", "位置"]
            final_cols = [c for c in cols_order if c in df_inv.columns]

            st.dataframe(df_inv[final_cols], use_container_width=True, hide_index=True)
        else:
            st.caption(f"📦 库存中未找到包含 '{search_term}' 的样本")

    except Exception as e:
        st.error(f"库存搜索出错: {e}")

    st.divider()

    # ==========================================
    # 2. 搜实验 (Experiments)
    # ==========================================
    try:
        filter_parts = []
        filter_parts.append(f'project_id~"{search_term}"')

        if found_sample_ids:
            for sid in found_sample_ids:
                filter_parts.append(f'sample_relation="{sid}"')

        final_filter = " || ".join(filter_parts)

        exp_res = pb.collection('experiments').get_list(
            page=1, per_page=20,
            query_params={
                "filter": final_filter,
                "sort": "-created",
                "expand": "sample_relation"
            }
        )

        if exp_res.items:
            st.markdown(f"**🧪 相关实验数据 ({exp_res.total_items})**")

            for exp in exp_res.items:
                proj = getattr(exp, "project_id", "No Project")
                date_str = str(exp.created)[:10]

                display_names = []
                if hasattr(exp, "expand") and "sample_relation" in exp.expand:
                    raw_expand = exp.expand["sample_relation"]
                    expand_list = raw_expand if isinstance(raw_expand, list) else [raw_expand]
                    for record in expand_list:
                        name = getattr(record, "sample_id", record.id)
                        display_names.append(name)

                if not display_names:
                    raw_ids = getattr(exp, "sample_relation", [])
                    if raw_ids:
                        count = len(raw_ids) if isinstance(raw_ids, list) else 1
                        display_names = [f"关联了 {count} 个样本"]

                sample_text = ", ".join(display_names) if display_names else "未关联样本"
                card_title = f"📁 {proj} | {sample_text} | {date_str}"

                with st.expander(card_title):
                    st.caption(f"系统记录 ID: {exp.id}")
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        if hasattr(exp, "result_json") and exp.result_json:
                            st.json(exp.result_json, expanded=False)
                        else:
                            st.info("无结果数据")
                    with c2:
                        if getattr(exp, "raw_data_file", None):
                            file_url = pb.get_file_url(exp, exp.raw_data_file)
                            st.markdown(f"[:paperclip: 下载原始数据]({file_url})")
                        else:
                            st.caption("无附件")

        else:
            st.info("🧪 未找到相关实验记录")
            if found_sample_ids:
                st.caption("提示: 已找到库存样本，但 experiments 表中似乎没有关联这些 ID。")

    except Exception as e:
        st.error(f"实验搜索模块出错: {e}")
        # st.code(f"Debug Filter: {final_filter}") # 暂时注释掉调试信息

    st.markdown('</div>', unsafe_allow_html=True)
    st.divider()

# --- 7. 核心指标统计 ---
st.divider()
try:
    inv_meta = pb.collection('inventory').get_list(1, 1)
    total_samples = inv_meta.total_items

    all_recs_light = pb.collection('inventory').get_full_list(
        query_params={"fields": "project_name,box_name"}
    )
    total_projects = len(set([getattr(r, 'project_name', 'Default') for r in all_recs_light]))
    total_boxes = len(set([getattr(r, 'box_name', 'Default') for r in all_recs_light]))

except Exception as e:
    total_samples, total_projects, total_boxes = 0, 0, 0
    if not search_term:
        st.sidebar.warning(f"Dashboard 数据加载受限: {e}")

m1, m2, m3, m4 = st.columns(4)
m1.metric("📦 在库样本总数", f"{total_samples} pcs")
m2.metric("📁 关联项目总数", f"{total_projects}")
m3.metric("🧊 存储冻存盒", f"{total_boxes}")
m4.metric("📈 系统运行状态", "Stable")

st.divider()

# --- 8. 快捷功能入口 (修改点：3列变4列，加入免疫模块) ---
st.subheader("🚀 快速功能入口")

c1, c2, c3, c4 = st.columns(4)

# [新增模块]
with c1:
    st.markdown("""
        <div class="module-card">
            <div class="module-header">🐇 免疫与动物档案</div>
            <p style='font-size: 0.9rem; color: #666;'>
                管理动物入舍、免疫日程提醒及血清效价(Titer)趋势监测。
            </p>
        </div>
    """, unsafe_allow_html=True)
    # 请确保 pages/00_Immunization.py 文件存在，否则这里会找不到页面
    if st.button("进入免疫管理", use_container_width=True):
        st.switch_page("pages/00_Immunization.py") # 建议文件名叫这个

# [原有模块顺延]
with c2:
    st.markdown("""
        <div class="module-card">
            <div class="module-header">🧪 实验数据分析</div>
            <p style='font-size: 0.9rem; color: #666;'>
                支持 ELISA 4PL 拟合、WB 自动灰度分析及 SPR 亲和力常数录入。
            </p>
        </div>
    """, unsafe_allow_html=True)
    if st.button("进入实验分析中心", use_container_width=True):
        st.switch_page("pages/01_ELISA_Analysis.py")

with c3:
    st.markdown("""
        <div class="module-card">
            <div class="module-header">🧬 序列与克隆档案</div>
            <p style='font-size: 0.9rem; color: #666;'>
                管理抗体序列、查看 Germline 比对结果，以及克隆的历史检测表现。
            </p>
        </div>
    """, unsafe_allow_html=True)
    if st.button("进入序列管理", use_container_width=True):
        st.switch_page("pages/03_Seq_Analysis.py")

with c4:
    st.markdown("""
        <div class="module-card">
            <div class="module-header">📦 智慧样本库</div>
            <p style='font-size: 0.9rem; color: #666;'>
                基于物理坐标(Rack/Box/Slot)的库存追踪。支持可视化与批量导入导出。
            </p>
        </div>
    """, unsafe_allow_html=True)
    if st.button("进入库存系统", use_container_width=True):
        st.switch_page("pages/06_Inventory_Management.py")

# --- 9. 最近更新/动态 ---
st.divider()
col_news, col_info = st.columns([2, 1])

with col_news:
    st.subheader("📝 最近审计日志 (Audit Trail)")
    try:
        logs_res = pb.collection('logs').get_list(
            page=1,
            per_page=5,
            query_params={"sort": "-created", "expand": "operator"}
        )

        if logs_res.items:
            for log in logs_res.items:
                op_name = "Unknown"
                if hasattr(log, "expand") and log.expand and "operator" in log.expand:
                    op_name = log.expand["operator"].email
                else:
                    op_name = getattr(log, "operator", "System")

                raw_time = str(log.created)
                time_str = raw_time.replace("T", " ")[:16]

                st.markdown(f"""
                <div style='font-size: 0.85rem; border-bottom: 1px solid #f0f0f0; padding: 6px 0;'>
                    <span style='color: #999;'>⏱ {time_str}</span> 
                    <b>{op_name}</b>: {log.action}
                    <div style='color: #555; margin-left: 10px; font-size: 0.8rem;'>↳ {log.details}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("暂无日志记录")

    except Exception as e:
        st.error(f"日志显示出错: {e}")

with col_info:
    st.subheader("ℹ️ 平台状态")
    st.success("✅ 数据库同步完成")
    if getattr(user_info, 'role', '') == 'admin':
        st.warning("🔧 管理员模式: 具备删除权限")
    else:
        st.info("👤 研究员模式: 仅具备读写权限")

# --- 页脚 ---
st.divider()
st.caption("© 2026 CRO Rabbit mAb Platform | Built with Streamlit & PocketBase")