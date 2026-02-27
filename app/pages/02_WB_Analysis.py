import streamlit as st

if "is_logged_in" not in st.session_state or not st.session_state.is_logged_in:
    st.warning("请先回到主页进行登录")
    st.stop()
import streamlit as st
import sys
import os
import cv2
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
from scipy.signal import find_peaks
import matplotlib.pyplot as plt
from scipy.stats import linregress
import re
import io
import json  # <--- 新增：用于存取本地文件

# --- 数据库连接设置 ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import save_experiment_record

# ==========================================
# 0. 全局配置与持久化逻辑
# ==========================================
st.set_page_config(page_title="WB Tool Pro", layout="wide")
st.title("🧪 WB Tool Pro: 一体化定量分析")

# 定义本地存储文件名
TEMPLATE_FILE = "marker_templates.json"


# --- 核心函数：加载模板 ---
def load_templates_from_disk():
    # 默认模板
    default_templates = {
        "Thermo 26616 (10-180kDa)": [180, 130, 100, 70, 55, 40, 35, 25, 15, 10],
        "BioRad Precision (10-250kDa)": [250, 150, 100, 75, 50, 37, 25, 20, 15, 10],
        "Simple (70, 55, 40, 35, 25)": [70, 55, 40, 35, 25]
    }

    # 尝试从文件读取
    if os.path.exists(TEMPLATE_FILE):
        try:
            with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
                saved_templates = json.load(f)
            # 合并默认模板，防止文件里是空的
            return {**default_templates, **saved_templates}
        except Exception as e:
            st.error(f"读取模板文件失败，使用默认值: {e}")
            return default_templates
    else:
        return default_templates


# --- 核心函数：保存模板 ---
def save_templates_to_disk(templates):
    try:
        with open(TEMPLATE_FILE, "w", encoding="utf-8") as f:
            json.dump(templates, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"保存模板文件失败: {e}")


# 初始化 Marker 模板 (优先从硬盘加载)
if 'marker_templates' not in st.session_state:
    st.session_state['marker_templates'] = load_templates_from_disk()

# 初始化表格数据状态
if 'wb_table_data' not in st.session_state:
    st.session_state['wb_table_data'] = None

# ==========================================
# 1. 侧边栏：参数设置
# ==========================================
st.sidebar.header("📝 实验信息")
project_id = st.sidebar.text_input("项目编号", value="WB-2024-001")
researcher = st.sidebar.text_input("实验员", value="User")

st.sidebar.markdown("---")
st.sidebar.header("🎛️ 图像与 Marker")

# 1.1 泳道设置
st.sidebar.subheader("1. 泳道定义")
n_lanes = st.sidebar.number_input("泳道总数", min_value=1, value=10, step=1)
marker_idx = st.sidebar.number_input("Marker 泳道位置", min_value=1, max_value=n_lanes, value=1)

st.sidebar.markdown("**Marker 模板**")
marker_list = list(st.session_state['marker_templates'].keys())
# 默认选中第一个或上次选中的
marker_name = st.sidebar.selectbox("选择应用模板", marker_list)

# --- Marker 输入区 (含持久化保存) ---
with st.sidebar.expander("➕ 新建/保存 Marker 模板"):
    st.caption("ℹ️ **提示**：支持逗号、空格分隔。系统自动**从大到小**排序。保存后**永久生效**。")
    new_mk_name = st.text_input("模板名称", placeholder="例如: My Marker")
    new_mk_vals = st.text_area("分子量列表", placeholder="180, 130, 95、72 55", height=100)

    if st.button("💾 永久保存模板"):
        if new_mk_name and new_mk_vals:
            try:
                separators = r'[ ,，、;；\t\n]+'
                raw_list = re.split(separators, new_mk_vals.strip())
                val_list = sorted([float(x) for x in raw_list if x], reverse=True)

                if len(val_list) == 0:
                    st.error("未识别到有效数字。")
                else:
                    # 1. 更新内存状态
                    st.session_state['marker_templates'][new_mk_name] = val_list
                    # 2. 写入硬盘文件 (关键步骤！)
                    save_templates_to_disk(st.session_state['marker_templates'])

                    st.success(f"已保存: {new_mk_name}")
                    st.rerun()
            except ValueError:
                st.error("格式错误：请输入数字。")
        else:
            st.warning("请填写名称和数值。")

# 1.2 信号处理
st.sidebar.subheader("2. 信号处理")
init_width_ratio = st.sidebar.slider("初始生成宽度 (%)", 50, 100, 80) / 100.0
subtract_bg = st.sidebar.checkbox("自动扣除背景", value=True)
prominence = st.sidebar.slider("峰值灵敏度", 1, 100, 10)
rel_height = st.sidebar.slider("积分宽度判定", 0.1, 1.0, 0.6)

# ==========================================
# 2. 图像上传与处理
# ==========================================
uploaded_file = st.file_uploader("📂 上传 WB 图像", type=["jpg", "png", "tif"])

if uploaded_file:
    # --- 图片预处理 ---
    raw_image = Image.open(uploaded_file)
    max_width = 800
    if raw_image.width > max_width:
        ratio = max_width / raw_image.width
        new_height = int(raw_image.height * ratio)
        image = raw_image.resize((max_width, new_height))
    else:
        image = raw_image

    img_array = np.array(image)
    if len(img_array.shape) == 3:
        img_gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        img_gray = img_array
    img_inverted = 255 - img_gray

    st.markdown("---")

    # ==========================================
    # 3. 核心交互区
    # ==========================================
    col_step1, col_step2 = st.columns(2)

    with col_step1:
        st.info("👇 **步骤 1：定位区域**")
        canvas_locator = st_canvas(
            fill_color="rgba(0, 0, 255, 0.1)",
            stroke_width=2, stroke_color="#0000FF",
            background_image=image, update_streamlit=True,
            height=image.height, width=image.width,
            drawing_mode="rect", key="canvas_locator", display_toolbar=True
        )

    initial_objects = []
    if canvas_locator.json_data and len(canvas_locator.json_data["objects"]) > 0:
        obj = canvas_locator.json_data["objects"][-1]
        base_x, base_y, base_w, base_h = int(obj["left"]), int(obj["top"]), int(obj["width"]), int(obj["height"])
        slot_w = base_w / n_lanes
        sample_w = slot_w * init_width_ratio
        padding = (slot_w - sample_w) / 2
        for i in range(n_lanes):
            initial_objects.append({
                "type": "rect",
                "left": base_x + i * slot_w + padding,
                "top": base_y, "width": sample_w, "height": base_h,
                "fill": "rgba(255, 0, 0, 0.2)", "stroke": "#FF0000", "strokeWidth": 2
            })

    with col_step2:
        st.info("👇 **步骤 2：精细调节**")
        canvas_finetune = st_canvas(
            fill_color="rgba(255, 0, 0, 0.2)",
            stroke_width=2, stroke_color="#FF0000",
            background_image=image, update_streamlit=True,
            height=image.height, width=image.width,
            initial_drawing={"version": "4.4.0", "objects": initial_objects} if initial_objects else None,
            drawing_mode="transform", key=f"canvas_finetune_{len(initial_objects)}", display_toolbar=True
        )

    # ==========================================
    # 4. 数据计算 (后端)
    # ==========================================
    final_objects = []
    if canvas_finetune.json_data:
        final_objects = sorted(canvas_finetune.json_data["objects"], key=lambda x: x["left"])

    if final_objects and len(final_objects) > 0:
        all_lanes_data = []

        for idx, obj in enumerate(final_objects):
            lane_num = idx + 1
            is_marker_lane = (lane_num == marker_idx)
            x, y, w, h = int(obj["left"]), int(obj["top"]), int(obj["width"]), int(obj["height"])

            if w <= 0 or h <= 0: continue
            roi = img_inverted[y:y + h, x:x + w]
            if roi.size == 0: continue

            profile = np.mean(roi, axis=1)
            bg_val = np.percentile(profile, 10)
            clean_profile = np.maximum(profile - bg_val, 0) if subtract_bg else profile
            peaks, properties = find_peaks(clean_profile, prominence=prominence, width=5)

            peak_data = []
            for j, p_idx in enumerate(peaks):
                width_prop = properties["widths"][j] * rel_height
                p_start, p_end = int(max(0, p_idx - width_prop)), int(min(len(clean_profile), p_idx + width_prop))
                iod = np.sum(clean_profile[p_start:p_end])
                peak_data.append({"y_pos": p_idx, "iod": iod, "height": clean_profile[p_idx]})

            total_peaks_iod = sum(p['iod'] for p in peak_data)
            main_peak = max(peak_data, key=lambda x: x['iod']) if peak_data else None
            purity = (main_peak['iod'] / total_peaks_iod * 100) if (main_peak and total_peaks_iod > 0) else 0

            all_lanes_data.append({
                "lane_id": lane_num,
                "is_marker": is_marker_lane,
                "profile": clean_profile,
                "raw_profile": profile,
                "peaks": peak_data,
                "main_peak": main_peak,
                "purity": purity,
                "total_peaks_iod": total_peaks_iod
            })

        mw_model = None
        r_squared = 0
        marker_data = next((d for d in all_lanes_data if d['is_marker']), None)
        if marker_data and marker_data['peaks']:
            template_mw = st.session_state['marker_templates'][marker_name]
            detected_peaks_y = sorted([p['y_pos'] for p in marker_data['peaks']])
            min_len = min(len(template_mw), len(detected_peaks_y))
            if min_len >= 3:
                y_vals = detected_peaks_y[:min_len]
                mw_vals = template_mw[:min_len]
                slope, intercept, r_value, p_value, std_err = linregress(y_vals, np.log10(mw_vals))
                mw_model = (slope, intercept)
                r_squared = r_value ** 2

        # 构建 Session 数据
        current_layout_fingerprint = f"{len(final_objects)}_{final_objects[0]['left']}"
        if 'layout_fingerprint' not in st.session_state or st.session_state[
            'layout_fingerprint'] != current_layout_fingerprint:
            rows = []
            for d in all_lanes_data:
                calc_mw = 0
                if mw_model and d['main_peak']:
                    calc_mw = 10 ** (mw_model[0] * d['main_peak']['y_pos'] + mw_model[1])

                default_name = "Marker" if d['is_marker'] else f"Sample {d['lane_id']}"
                iod_val = d['main_peak']['iod'] if d['main_peak'] else 0

                rows.append({
                    "Lane": d['lane_id'],
                    "Type": "Marker" if d['is_marker'] else "Sample",
                    "Sample Name": default_name,
                    "Size (kDa)": round(calc_mw, 1) if calc_mw > 0 else 0,
                    "Purity (%)": round(d['purity'], 1),
                    "IOD": int(iod_val),
                    "Ref?": False,
                    "Conc.": 0.0
                })
            st.session_state['wb_table_data'] = pd.DataFrame(rows)
            st.session_state['layout_fingerprint'] = current_layout_fingerprint
            st.rerun()

        # ==========================================
        # 5. 结果展示
        # ==========================================
        st.markdown("---")
        tab1, tab2 = st.tabs(["📊 一体化分析表", "📈 峰形图详情"])

        with tab1:
            col_in1, col_in2, col_info = st.columns([1, 1, 2])
            with col_in1:
                ref_conc_input = st.number_input("标品浓度 (Ref Conc.)", value=1.0, min_value=0.0, step=0.1)
            with col_in2:
                conc_unit = st.text_input("单位", value="mg/mL")
            with col_info:
                if mw_model:
                    st.caption(f"✅ 分子量拟合 R² = {r_squared:.4f}")
                else:
                    st.caption("⚠️ 分子量未计算 (Marker 条带不足)")

            df_to_edit = st.session_state['wb_table_data']

            edited_df = st.data_editor(
                df_to_edit,
                column_config={
                    "Ref?": st.column_config.CheckboxColumn("设为标品?", default=False),
                    "IOD": st.column_config.NumberColumn("光密度 (IOD)", format="%d"),
                    "Purity (%)": st.column_config.ProgressColumn("纯度", format="%.1f%%", min_value=0, max_value=100),
                    "Size (kDa)": st.column_config.NumberColumn("大小 (kDa)"),
                    "Conc.": st.column_config.NumberColumn("浓度 (结果)", format="%.3f"),
                },
                disabled=["Lane", "Type", "IOD", "Size (kDa)", "Purity (%)", "Conc."],
                hide_index=True,
                use_container_width=True,
                key="wb_main_editor"
            )

            # --- 实时计算 ---
            calc_df = edited_df.copy()
            ref_rows = calc_df[calc_df["Ref?"] == True]

            if len(ref_rows) == 1:
                ref_iod = ref_rows.iloc[0]["IOD"]
                if ref_iod > 0:
                    mask = (calc_df["Type"] == "Sample") & (calc_df["IOD"] > 0)
                    calc_df.loc[mask, "Conc."] = (calc_df.loc[mask, "IOD"] / ref_iod) * ref_conc_input
                    calc_df.loc[~mask, "Conc."] = 0.0
                else:
                    calc_df["Conc."] = 0.0
            else:
                calc_df["Conc."] = 0.0

            if not calc_df["Conc."].equals(st.session_state['wb_table_data']["Conc."]) or \
                    not calc_df["Ref?"].equals(st.session_state['wb_table_data']["Ref?"]) or \
                    not calc_df["Sample Name"].equals(st.session_state['wb_table_data']["Sample Name"]):
                st.session_state['wb_table_data'] = calc_df
                st.rerun()

            if len(ref_rows) > 1:
                st.error("⚠️ 错误：只能勾选 1 个标品！")

        with tab2:
            st.markdown("### 峰形图详情")
            view_lane = st.selectbox("查看泳道:", [d['lane_id'] for d in all_lanes_data])
            lane_d = next(d for d in all_lanes_data if d['lane_id'] == view_lane)

            fig, ax = plt.subplots(figsize=(10, 3))
            ax.plot(lane_d['raw_profile'], color='#cccccc', linestyle='--', label='Raw')
            ax.plot(lane_d['profile'], color='black', label='Net Signal')
            for p in lane_d['peaks']:
                is_main = (p == lane_d['main_peak'])
                color = 'red' if is_main else 'blue'
                ax.plot(p['y_pos'], p['height'], "x", color=color, markersize=8 if is_main else 5)
            ax.set_title(f"Lane {view_lane} Profile")
            ax.legend()
            st.pyplot(fig)

        # ==========================================
        # 6. 保存与导出
        # ==========================================
        st.markdown("---")

        col_space, col_save, col_export = st.columns([6, 2, 2])

        # A. 保存到数据库
        with col_save:
            if st.button("💾 保存至 Database", type="primary", use_container_width=True):
                results_json = {
                    "summary_table": st.session_state['wb_table_data'].to_dict(orient="records"),
                    "marker_fit_r2": r_squared,
                    "unit": conc_unit,
                    "settings": {"prominence": prominence, "subtract_bg": subtract_bg}
                }
                uploaded_file.seek(0)
                success, msg = save_experiment_record(project_id, researcher, uploaded_file, results_json)
                if success:
                    st.success("保存成功！")
                else:
                    st.error(msg)

        # B. 导出 Excel
        with col_export:
            output = io.BytesIO()
            try:
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_export = st.session_state['wb_table_data']
                    df_export.to_excel(writer, index=False, sheet_name='WB_Analysis')

                xlsx_data = output.getvalue()

                st.download_button(
                    label="📥 导出结果 Excel",
                    data=xlsx_data,
                    file_name=f"WB_Results_{project_id}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"导出失败: {e}")
                st.caption("请确保安装了 openpyxl: pip install openpyxl")

else:
    st.info("👋 请先上传 WB 图片。")