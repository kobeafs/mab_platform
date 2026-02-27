import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import io
import sys
import os

# --- 核心：确保能找到 db.py (根据文件层级自动定位) ---
# utils/elisa_modules/bca.py -> utils/elisa_modules -> utils -> app (根目录)
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# 引入数据库保存函数和算法库
from db import save_experiment_record
from utils.math_models import linear_fit, poly_fit


# ==========================================
# 辅助函数
# ==========================================
def plate_to_long_format(df_plate):
    """把 8x12 矩阵转为长列表"""
    rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    cols = range(1, 13)
    data = []
    for r_idx, row_label in enumerate(rows):
        for c_idx, col_label in enumerate(cols):
            val = df_plate.iloc[r_idx, c_idx]
            try:
                val = float(val)
            except:
                val = np.nan
            data.append({"Well": f"{row_label}{col_label}", "Row": row_label, "Col": col_label, "OD": val})
    return pd.DataFrame(data)


def df_to_excel_download(df_conc_matrix, df_raw, r2_info):
    """生成包含多个 Sheet 的 Excel 二进制流"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_conc_matrix.to_excel(writer, sheet_name='Results_Conc')
        df_raw.to_excel(writer, sheet_name='Raw_OD')
        pd.DataFrame([{"Info": r2_info}]).to_excel(writer, sheet_name='Stats', index=False)
    return output.getvalue()


# ==========================================
# 主界面
# ==========================================
def show():
    st.header("🥩 BCA 蛋白定量 (Pro Version)")

    # --- 1. 项目元数据 (新增：为了存数据库) ---
    with st.container():
        c_meta1, c_meta2 = st.columns(2)
        project_id = c_meta1.text_input("项目编号 (Project ID)", value="BCA-2024-001", key="bca_proj")
        researcher = c_meta2.text_input("实验员 (Researcher)", value="User", key="bca_user")

    # --- 2. 参数设置 ---
    with st.expander("⚙️ 参数设置 (拟合模型 & 标曲生成)", expanded=True):
        col_conf1, col_conf2 = st.columns(2)
        with col_conf1:
            st.markdown("#### 1. 拟合模型")
            fit_model = st.radio("选择算法", ["Linear (线性)", "Quadratic (二次多项式)"], horizontal=True,
                                 key="bca_model")
            st.caption("提示：高浓度(>1000)建议使用 Quadratic，低浓度使用 Linear。")

        with col_conf2:
            st.markdown("#### 2. 标曲浓度生成器")
            c1, c2, c3 = st.columns(3)
            start_conc = c1.number_input("起始浓度", value=2000.0, step=100.0, key="bca_start")
            dilution_factor = c2.number_input("稀释倍数", value=2.0, step=0.5, key="bca_dil")
            points_count = c3.number_input("标曲点数", value=8, min_value=3, max_value=8, key="bca_pts")

            # 自动生成浓度列表
            gen_concs = []
            current = start_conc
            for _ in range(points_count):
                gen_concs.append(current)
                current = current / dilution_factor

            use_zero_blank = st.checkbox("强制最后一个点为 0 (Blank)?", value=True, key="bca_zero")
            if use_zero_blank:
                gen_concs[-1] = 0.0

    st.markdown("---")

    # --- 3. 数据上传 ---
    uploaded_file = st.file_uploader("📂 上传酶标仪 Excel 数据 (需包含 8x12 矩阵)", type=["xlsx", "xls"], key="bca_up")

    # 初始化变量，防止报错
    calc_success = False
    results_json = {}

    if uploaded_file:
        try:
            df_raw_input = pd.read_excel(uploaded_file, header=None)
            df_plate = df_raw_input.iloc[0:8, 0:12].copy()
            df_plate.index = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
            df_plate.columns = list(range(1, 13))
            df_long = plate_to_long_format(df_plate)
        except Exception as e:
            st.error(f"数据读取失败，请检查格式。{e}")
            return

        # --- 4. 布局定义 ---
        st.subheader("📊 标曲布局定义")
        col_layout1, col_layout2 = st.columns([1, 2])

        with col_layout1:
            st.markdown("**选择标曲所在列**")
            std_cols = st.multiselect("Standard Columns", list(range(1, 13)), default=[1, 2], key="bca_std_cols")
            st.info(f"选中的列 ({len(std_cols)}列) 将取均值用于拟合。")

        with col_layout2:
            st.markdown("**核对标曲浓度 (Row A -> H)**")
            full_concs = gen_concs + [None] * (8 - len(gen_concs))
            df_std_def = pd.DataFrame({
                "Row": ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'],
                "Concentration": full_concs
            })
            edited_std = st.data_editor(
                df_std_def,
                height=300,
                use_container_width=True,
                column_config={"Concentration": st.column_config.NumberColumn("Conc (ug/mL)", required=True)},
                key="bca_std_edit"
            )

        # --- 5. 计算按钮 ---
        if st.button("🚀 开始拟合与回算", type="primary", key="bca_calc_btn"):
            # A. 准备标曲
            std_conc_map = dict(zip(edited_std['Row'], edited_std['Concentration']))
            df_std = df_long[df_long['Col'].isin(std_cols)].copy()
            df_std['Conc_Def'] = df_std['Row'].map(std_conc_map)
            df_std = df_std.dropna(subset=['Conc_Def'])

            # B. 扣除 Blank
            blank_rows = df_std[df_std['Conc_Def'] == 0]
            if not blank_rows.empty:
                blank_val = blank_rows['OD'].mean()
            else:
                blank_val = 0
                st.toast("⚠️ 未找到 0 浓度点，未扣除 Blank", icon="⚠️")

            df_long['Net_OD'] = df_long['OD'] - blank_val
            df_std['Net_OD'] = df_std['OD'] - blank_val

            # C. 拟合
            std_mean = df_std.groupby('Conc_Def')['Net_OD'].mean().reset_index()
            x_fit = std_mean['Conc_Def']
            y_fit = std_mean['Net_OD']

            if fit_model == "Linear (线性)":
                model_func, r2, eq_str = linear_fit(x_fit, y_fit)
            else:
                model_func, r2, eq_str = poly_fit(x_fit, y_fit)

            # D. 展示结果
            st.markdown("---")
            st.subheader("📈 拟合结果")

            c_res1, c_res2 = st.columns([1, 2])
            with c_res1:
                st.metric("R² (拟合优度)", f"{r2:.4f}")
                st.info(f"Blank OD: {blank_val:.4f}")
                st.caption(f"Equation: {eq_str}")
                if r2 < 0.98:
                    st.error("拟合不佳，请检查数据。")

            with c_res2:
                fig = px.scatter(std_mean, x="Conc_Def", y="Net_OD", title=f"BCA Standard Curve ({fit_model})")
                x_range = np.linspace(min(x_fit), max(x_fit), 100)
                if fit_model == "Linear (线性)":
                    # 简单估算画线
                    z = np.polyfit(x_fit, y_fit, 1)
                    p = np.poly1d(z)
                    y_pred = p(x_range)
                else:
                    z = np.polyfit(x_fit, y_fit, 2)
                    p = np.poly1d(z)
                    y_pred = p(x_range)

                fig.add_traces(go.Scatter(x=x_range, y=y_pred, mode='lines', name='Fit Line', line=dict(color='red')))
                st.plotly_chart(fig, use_container_width=True)

            # E. 回算矩阵
            st.subheader("🔢 浓度回算矩阵 (ug/mL)")
            df_long['Calc_Conc'] = model_func(df_long['Net_OD'])
            df_long.loc[df_long['Calc_Conc'] < 0, 'Calc_Conc'] = 0
            df_result_matrix = df_long.pivot(index='Row', columns='Col', values='Calc_Conc')

            st.dataframe(
                df_result_matrix.style.format("{:.1f}").background_gradient(cmap="Greens"),
                use_container_width=True
            )

            # 标记计算成功，准备保存数据
            st.session_state['bca_calc_done'] = True
            st.session_state['bca_res_matrix'] = df_result_matrix
            st.session_state['bca_raw_plate'] = df_plate
            st.session_state['bca_r2_info'] = f"Model: {fit_model}, R2: {r2:.4f}, Blank: {blank_val:.4f}"
            st.session_state['bca_json_data'] = {
                "r2": r2,
                "fit_model": fit_model,
                "blank_od": blank_val,
                "equation": eq_str,
                "conc_matrix": df_result_matrix.to_dict()  # 简单存结果
            }

    # --- 6. 底部操作栏：保存与下载 ---
    if st.session_state.get('bca_calc_done', False):
        st.markdown("---")
        st.subheader("💾 数据归档")

        col_btn1, col_btn2 = st.columns([1, 1])

        # 按钮 A: 下载 Excel
        with col_btn1:
            excel_data = df_to_excel_download(
                st.session_state['bca_res_matrix'],
                st.session_state['bca_raw_plate'],
                st.session_state['bca_r2_info']
            )
            st.download_button(
                label="📥 下载结果 (96孔矩阵 Excel)",
                data=excel_data,
                file_name=f"BCA_Results_{project_id}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="secondary",
                use_container_width=True
            )

        # 按钮 B: 保存到 PocketBase (新增核心功能)
        with col_btn2:
            if st.button("☁️ 保存至 PocketBase", type="primary", use_container_width=True):
                # 必须重置文件指针，否则传给数据库的是空文件
                uploaded_file.seek(0)

                success, msg = save_experiment_record(
                    project=project_id,
                    name=researcher,
                    file_obj=uploaded_file,
                    results=st.session_state['bca_json_data']
                )

                if success:
                    st.success("✅ 数据已成功保存到数据库！")
                else:
                    st.error(f"❌ 保存失败: {msg}")