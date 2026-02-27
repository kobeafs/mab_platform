import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import io
import sys
import os

# --- 路径与导入 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from db import save_experiment_record
from utils.math_models import fit_4pl


# ==========================================
# 辅助函数：Matplotlib 静态图
# ==========================================
def create_matplotlib_image(fit_curves, blank_val, unit):
    fig, ax = plt.subplots(figsize=(8, 6))
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

    for idx, (name, data) in enumerate(fit_curves.items()):
        color = colors[idx % len(colors)]
        ax.errorbar(data['x'], data['y'], yerr=data['y_err'], fmt='o', label=name, color=color, capsize=4, markersize=5)
        if data['func']:
            x_smooth = np.geomspace(min(data['x']), max(data['x']), 100)
            y_smooth = data['func'](x_smooth)
            ax.plot(x_smooth, y_smooth, '-', color=color)
        elif data['type'] == "NC":
            ax.plot(data['x'], data['y'], '--', color=color, alpha=0.5)

    ax.set_xscale('log')
    ax.set_xlabel(f"Concentration ({unit})")
    ax.set_ylabel("Net OD")
    ax.set_title(f"Dose-Response Curves (Blank: {blank_val:.4f})")
    ax.grid(True, which="both", ls="-", alpha=0.2)
    ax.legend()

    img_buf = io.BytesIO()
    fig.savefig(img_buf, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    return img_buf.getvalue()


# ==========================================
# 辅助函数：生成 Excel
# ==========================================
def generate_report_excel(df_summary, df_details, fig_bytes, blank_val):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book

        # Sheet 1: 汇总
        df_summary.to_excel(writer, sheet_name='Summary', index=False)
        ws_sum = writer.sheets['Summary']
        ws_sum.set_column('A:H', 12)
        ws_sum.write(len(df_summary) + 2, 0, f"Background (Blank) OD: {blank_val:.4f}")

        # Sheet 2: 详情
        df_details.to_excel(writer, sheet_name='Detailed_Data', index=False)

        # Sheet 3: 图片
        ws_plot = workbook.add_worksheet('Plot')
        ws_plot.write(0, 0, f"Curves (Blank Subtracted: {blank_val:.4f})")
        if fig_bytes:
            ws_plot.insert_image('A3', 'curve.png', {'image_data': io.BytesIO(fig_bytes)})

    return output.getvalue()


# ==========================================
# 辅助函数：布局预览样式
# ==========================================
def apply_plate_style(val):
    if pd.isna(val) or str(val).strip() == "": return ""
    val_str = str(val).upper()
    if "BLANK" in val_str:
        return 'background-color: #e2e3e5; color: #666666'
    elif "NC" in val_str:
        return 'background-color: #fff3cd; color: #856404'
    elif "PC" in val_str:
        return 'background-color: #f8d7da; color: #721c24'
    elif "SAMPLE" in val_str:
        return 'background-color: #d1e7dd; color: #0f5132'
    return ""


# ==========================================
# 主界面逻辑
# ==========================================
def show():
    st.header("📉 效价检测 (EC50) - Ultimate版")
    st.info("💡 流程：上传 -> 数据预览 -> 定义布局 -> 计算 -> 导出报告")

    # --- 1. 元数据 ---
    with st.container():
        c1, c2 = st.columns(2)
        project_id = c1.text_input("项目编号", value="Potency-2024-001", key="tit_p")
        researcher = c2.text_input("实验员", value="User", key="tit_u")

    # --- 2. 设置 ---
    with st.expander("🧪 浓度梯度与 QC 设置", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        start_conc = c1.number_input("起始浓度", value=1000.0, step=100.0)
        dil_factor = c2.number_input("稀释倍数", value=3.0, min_value=1.1)
        conc_unit = c3.text_input("浓度单位", value="ng/mL")
        cv_threshold = c4.number_input("CV% 警戒线", value=15.0)

        concs = []
        curr = start_conc
        for _ in range(8):
            concs.append(curr)
            curr /= dil_factor

    st.markdown("---")

    # --- 3. 上传 ---
    uploaded_file = st.file_uploader("📂 上传酶标仪 Excel (8x12 矩阵)", type=["xlsx", "xls"], key="tit_up")

    if 'titer_calc_done' not in st.session_state:
        st.session_state['titer_calc_done'] = False

    if uploaded_file:
        try:
            df_raw = pd.read_excel(uploaded_file, header=None)
            df_plate = df_raw.iloc[0:8, 0:12].copy()
            df_plate.index = list('ABCDEFGH')
            df_plate.columns = list(range(1, 13))

            # --- 🔥 恢复的功能：原始数据预览 (热力图) ---
            st.subheader("1. 原始数据预览 (Raw OD Heatmap)")
            st.dataframe(
                df_plate.style.format("{:.3f}").background_gradient(cmap="Blues"),
                use_container_width=True
            )
            # ----------------------------------------

        except:
            st.error("数据读取失败，请检查 Excel 格式")
            return

        st.markdown("---")

        # --- 4. 布局定义 ---
        st.subheader("2. 布局定义 & 排版预览")

        layout_rows = []
        presets = {1: ("PC", "Ref_Std"), 2: ("PC", "Ref_Std"), 11: ("NC", "Neg"), 12: ("Blank", "Buffer")}
        for i in range(1, 13):
            t, n = presets.get(i, ("Sample", f"Sample {i}" if i <= 4 else ""))
            layout_rows.append({"Column": i, "Type": t, "Sample Name": n})

        c_edit, c_view = st.columns([1, 1])

        # 左：编辑
        with c_edit:
            st.markdown("**A. 编辑列属性**")
            edited_layout = st.data_editor(
                pd.DataFrame(layout_rows),
                column_config={
                    "Column": st.column_config.NumberColumn(disabled=True),
                    "Type": st.column_config.SelectboxColumn("类型", options=["Sample", "PC", "NC", "Blank"],
                                                             required=True),
                    "Sample Name": st.column_config.TextColumn("样品名称 (同名合并复孔)")
                },
                hide_index=True, use_container_width=True, height=460
            )

        # 右：预览 (彩色板)
        with c_view:
            st.markdown("**B. 排版可视化 (Layout Map)**")
            preview = pd.DataFrame(index=list('ABCDEFGH'), columns=range(1, 13))
            for _, r in edited_layout.iterrows():
                txt = ""
                if r['Type'] == "Blank":
                    txt = "Blank"
                elif r['Sample Name']:
                    txt = f"{r['Type']}\n{r['Sample Name']}"
                preview[r['Column']] = txt

            st.dataframe(
                preview.style.applymap(apply_plate_style),
                use_container_width=True, height=460
            )
            st.caption("图例: 🟩 Sample | 🟥 PC | 🟨 NC | ⬜ Blank")

        # --- 5. 计算逻辑 ---
        if st.button("🚀 计算 EC50 & 生成报告", type="primary"):
            # 分组
            groups = {}
            blanks = []
            for _, r in edited_layout.iterrows():
                if r['Type'] == "Blank":
                    blanks.append(r['Column'])
                elif r['Sample Name']:
                    if r['Sample Name'] not in groups:
                        groups[r['Sample Name']] = {'cols': [], 'type': r['Type']}
                    groups[r['Sample Name']]['cols'].append(r['Column'])

            # 扣 Blank
            blank_val = 0.0
            if blanks:
                blank_val = np.nanmean(df_plate[blanks].values)
                st.success(f"✅ Blank OD: {blank_val:.4f}")
            else:
                st.warning("⚠️ 未定义 Blank，使用 0.0")

            summary = []
            details = []
            fit_curves = {}

            # 遍历计算
            for name, info in groups.items():
                cols = info['cols']
                sub_raw = df_plate[cols]
                sub_net = sub_raw - blank_val

                means = sub_net.mean(axis=1).values
                stds = sub_net.std(axis=1).values

                # CV 计算 (Raw)
                raw_means = sub_raw.mean(axis=1).values
                raw_stds = sub_raw.std(axis=1).values
                with np.errstate(divide='ignore'):
                    cvs = np.nan_to_num((raw_stds / raw_means) * 100)
                max_cv = np.max(cvs)

                for r in range(8):
                    details.append({
                        "Sample": name, "Type": info['type'], "Conc": concs[r],
                        "Net OD": means[r], "Raw OD": raw_means[r], "CV%": cvs[r]
                    })

                # 拟合
                if info['type'] == "NC":
                    summary.append(
                        {"Sample": name, "Type": "NC", "EC50": None, "R²": None, "Max CV%": max_cv, "Note": "Neg Ctrl"})
                    fit_curves[name] = {"x": concs, "y": means, "y_err": stds, "type": "NC", "func": None}
                else:
                    popt, r2, func = fit_4pl(concs, means)
                    note = "Pass"
                    if max_cv > cv_threshold: note = f"CV>{cv_threshold}%"
                    if r2 < 0.95: note += "; Low R2"

                    if popt is not None:
                        summary.append({
                            "Sample": name, "Type": info['type'], "EC50": popt[2], "R²": r2,
                            "Max CV%": max_cv, "Top": popt[3], "Bottom": popt[0], "Note": note
                        })
                        fit_curves[name] = {"x": concs, "y": means, "y_err": stds, "type": info['type'], "func": func}
                    else:
                        summary.append({"Sample": name, "Type": info['type'], "EC50": None, "R²": 0, "Max CV%": max_cv,
                                        "Note": "Fit Failed"})

            # 保存状态
            st.session_state['titer_calc_done'] = True
            st.session_state['titer_sum'] = pd.DataFrame(summary)
            st.session_state['titer_det'] = pd.DataFrame(details)
            st.session_state['titer_blank'] = blank_val
            st.session_state['titer_curves'] = fit_curves
            st.session_state['titer_img_bytes'] = create_matplotlib_image(fit_curves, blank_val, conc_unit)

    # --- 6. 结果与下载 ---
    if st.session_state.get('titer_calc_done'):
        st.markdown("---")
        st.subheader("3. 结果分析")

        # --- 显示 Blank 值 (你要的新功能) ---
        col_res1, col_res2 = st.columns([1, 3])
        with col_res1:
            st.metric("Background (Blank) OD", f"{st.session_state['titer_blank']:.4f}")

        # 结果表
        st.dataframe(
            st.session_state['titer_sum'].style.format({"EC50": "{:.4f}", "R²": "{:.4f}", "Max CV%": "{:.1f}"})
            .applymap(lambda x: "color: red" if isinstance(x, (int, float)) and x > cv_threshold else "",
                      subset=["Max CV%"]),
            use_container_width=True
        )

        # 交互图
        fig = go.Figure()
        curves = st.session_state['titer_curves']
        pal = px.colors.qualitative.G10
        for i, (name, d) in enumerate(curves.items()):
            c = pal[i % len(pal)]
            fig.add_traces(
                go.Scatter(x=d['x'], y=d['y'], error_y=dict(type='data', array=d['y_err']), mode='markers', name=name,
                           marker=dict(color=c)))
            if d['func']:
                xs = np.geomspace(min(d['x']), max(d['x']), 100)
                fig.add_traces(go.Scatter(x=xs, y=d['func'](xs), mode='lines', line=dict(color=c), showlegend=False))
            elif d['type'] == "NC":
                fig.add_traces(
                    go.Scatter(x=d['x'], y=d['y'], mode='lines', line=dict(color=c, dash='dot'), showlegend=False))

        fig.update_layout(xaxis_type="log", title="Curves (Net OD)", height=500)
        st.plotly_chart(fig, use_container_width=True)

        # 下载区
        c1, c2 = st.columns(2)
        with c1:
            excel_data = generate_report_excel(
                st.session_state['titer_sum'],
                st.session_state['titer_det'],
                st.session_state['titer_img_bytes'],
                st.session_state['titer_blank']
            )
            st.download_button("📥 导出完整报告 (Excel+图)", excel_data, f"Titer_{project_id}.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="secondary",
                               use_container_width=True)

        with c2:
            if st.button("☁️ 保存至 PocketBase", type="primary", use_container_width=True):
                uploaded_file.seek(0)
                res_json = {"summary": st.session_state['titer_sum'].fillna("").to_dict(orient="records")}
                save_experiment_record(project_id, researcher, uploaded_file, res_json)
                st.success("已保存!")