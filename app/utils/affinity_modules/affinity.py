import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import io
import sys
import os

# --- 路径与导入 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from db import save_experiment_record


# ==========================================
# 辅助函数：模拟动力学曲线
# ==========================================
def simulate_sensorgram(kon, koff, t_assoc=180, t_dissoc=600, rmax=100, conc_nM=10):
    try:
        kon = float(kon)
        koff = float(koff)
        conc_M = float(conc_nM) * 1e-9

        # 结合阶段
        t1 = np.linspace(0, t_assoc, 100)
        denominator = (kon * conc_M + koff)

        # 防止除以0
        if denominator == 0:
            return np.array([]), np.array([])

        req = (conc_M * rmax * kon) / denominator
        k_obs = denominator
        r_assoc = req * (1 - np.exp(-k_obs * t1))

        # 解离阶段
        t2 = np.linspace(0, t_dissoc, 200)
        r0 = r_assoc[-1] if len(r_assoc) > 0 else 0
        r_dissoc = r0 * np.exp(-koff * t2)

        # 拼接
        full_time = np.concatenate([t1, t2 + t_assoc])
        full_resp = np.concatenate([r_assoc, r_dissoc])
        return full_time, full_resp
    except:
        return np.array([]), np.array([])


# ==========================================
# 主显示函数
# ==========================================
def show():
    st.header("🧲 亲和力分析 (SPR/BLI) - Pro")

    # --- 1. 设置 ---
    with st.expander("📝 实验信息 & 阳性对照", expanded=True):
        c1, c2, c3 = st.columns([1, 1, 2])
        project_id = c1.text_input("项目编号", value="SPR-2024", key="spr_p")
        researcher = c2.text_input("实验员", value="User", key="spr_u")

        sc1, sc2, sc3 = c3.columns(3)
        # 这里的 Benchmark 输入应该是标准单位 (M)
        ref_kon = sc1.number_input("Benchmark kon (1/Ms)", value=1e5, format="%.1e")
        ref_koff = sc2.number_input("Benchmark koff (1/s)", value=1e-4, format="%.1e")
        ref_kd = ref_koff / ref_kon if ref_kon > 0 else 0
        sc3.metric("Benchmark KD (M)", f"{ref_kd:.2e}")

    # --- 2. 上传 ---
    uploaded_file = st.file_uploader("上传 Results Table", type=["xlsx", "csv", "xls"], key="spr_up")

    if uploaded_file:
        try:
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

            # --- 智能列名识别 ---
            cols = df.columns.str.lower()
            name_col = next((c for c in df.columns if any(x in c.lower() for x in ['sample', 'clone', 'id', 'ligand'])),
                            None)
            kon_col = next((c for c in df.columns if 'on' in c.lower() or 'ka' in c.lower()), None)
            koff_col = next((c for c in df.columns if
                             'off' in c.lower() or 'kd' in c.lower() and 'k' in c.lower() and 'd' not in c.lower()),
                            None)
            kd_col = next(
                (c for c in df.columns if 'kd' in c.lower() and ('(m)' in c.lower() or 'affinity' in c.lower())), None)

            if not all([name_col, kon_col, koff_col, kd_col]):
                st.warning("列名识别不全，请手动指定：")
                c1, c2, c3, c4 = st.columns(4)
                name_col = c1.selectbox("ID", df.columns, 0)
                kon_col = c2.selectbox("kon", df.columns, 1)
                koff_col = c3.selectbox("koff", df.columns, 2)
                kd_col = c4.selectbox("KD", df.columns, 3)

            # --- 单位修正 ---
            st.markdown("##### 📏 单位修正 (Unit Correction)")
            u1, u2 = st.columns(2)
            kon_mult_opt = u1.selectbox("kon 数据倍率", ["标准 (1/Ms)", "x 10^4", "x 10^5"], index=0)
            koff_mult_opt = u2.selectbox("koff 数据倍率", ["标准 (1/s)", "x 10^-3", "x 10^-4", "x 10^-5"], index=0)

            # 计算倍数因子
            kon_factor = 1.0
            if "10^4" in kon_mult_opt:
                kon_factor = 1e4
            elif "10^5" in kon_mult_opt:
                kon_factor = 1e5

            koff_factor = 1.0
            if "10^-3" in koff_mult_opt:
                koff_factor = 1e-3
            elif "10^-4" in koff_mult_opt:
                koff_factor = 1e-4
            elif "10^-5" in koff_mult_opt:
                koff_factor = 1e-5

            # --- 数据处理 ---
            # 1. 转数字
            for col in [kon_col, koff_col, kd_col]:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df = df.dropna(subset=[kon_col, koff_col])

            # 2. 修正数值
            df[kon_col] = df[kon_col] * kon_factor
            df[koff_col] = df[koff_col] * koff_factor

            # 3. 重算 KD (确保一致性)
            df[kd_col] = df[koff_col] / df[kon_col]

            # 4. 判定优劣
            df['Status'] = df.apply(lambda x: 'Better' if x[kd_col] < ref_kd else 'Worse', axis=1)

            # --- 3. 散点图 ---
            st.markdown("### 1. 亲和力分布")
            col_chart, col_table = st.columns([2, 1])

            with col_chart:
                fig = px.scatter(
                    df, x=kon_col, y=koff_col, hover_name=name_col, color='Status',
                    log_x=True, log_y=True,
                    color_discrete_map={'Better': '#2ca02c', 'Worse': '#d62728'},
                    labels={kon_col: "kon (1/Ms)", koff_col: "koff (1/s)"},
                    title=f"Iso-Affinity Map (Ref KD={ref_kd:.1e})"
                )
                fig.add_trace(go.Scatter(x=[ref_kon], y=[ref_koff], mode='markers', name='Benchmark',
                                         marker=dict(symbol='star', size=15, color='gold',
                                                     line=dict(width=1, color='black'))))
                st.plotly_chart(fig, use_container_width=True)

            with col_table:
                st.markdown("**Top Candidates**")
                # 排序
                df_display = df[[name_col, kd_col, 'Status']].sort_values(by=kd_col).reset_index(drop=True)
                styler = df_display.style.format({kd_col: "{:.2e}"}).background_gradient(subset=[kd_col], cmap="Greens")

                selection = st.dataframe(
                    styler, use_container_width=True, height=450,
                    on_select="rerun", selection_mode="single-row", key="spr_sel"
                )

            # --- 4. 模拟曲线 ---
            st.markdown("### 2. 动力学曲线模拟")
            sim_conc = st.slider("模拟分析物浓度 (nM)", 1, 1000, 10)

            # 获取选中行
            target_index = 0
            if selection.selection['rows']: target_index = selection.selection['rows'][0]

            if not df_display.empty:
                sel_row = df_display.iloc[target_index]
                t_name = sel_row[name_col]
                orig_rec = df[df[name_col] == t_name].iloc[0]

                t_kon = orig_rec[kon_col]
                t_koff = orig_rec[koff_col]
                t_kd = orig_rec[kd_col]

                # 模拟
                t_sim, r_sim = simulate_sensorgram(t_kon, t_koff, conc_nM=sim_conc)
                t_ref, r_ref = simulate_sensorgram(ref_kon, ref_koff, conc_nM=sim_conc)

                sim_fig = go.Figure()
                sim_fig.add_trace(
                    go.Scatter(x=t_sim, y=r_sim, mode='lines', name=f"{t_name}", line=dict(color='#2ca02c', width=3)))
                sim_fig.add_trace(go.Scatter(x=t_ref, y=r_ref, mode='lines', name='Benchmark',
                                             line=dict(color='gold', dash='dash', width=2)))
                sim_fig.update_layout(title=f"Simulation ({sim_conc} nM): {t_name} vs Benchmark", height=400,
                                      hovermode="x unified")

                c_s1, c_s2 = st.columns([3, 1])
                with c_s1:
                    st.plotly_chart(sim_fig, use_container_width=True)
                with c_s2:
                    st.markdown(f"**{t_name}**")
                    st.metric("KD (M)", f"{t_kd:.2e}")
                    st.metric("kon (1/Ms)", f"{t_kon:.2e}")
                    st.metric("koff (1/s)", f"{t_koff:.2e}")

                    if t_kd > 0 and ref_kd > 0:
                        fold = ref_kd / t_kd
                        if fold >= 1:
                            st.success(f"比对照强 {fold:.1f} 倍")
                        else:
                            st.error(f"比对照弱 {1 / fold:.1f} 倍")

            # --- 5. 导出与保存 (新增下载按钮) ---
            st.markdown("---")
            st.subheader("3. 导出与保存")

            c_dl, c_sv = st.columns([1, 1])

            # --- 按钮 A: 下载 Excel (包含修正后的数据) ---
            with c_dl:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    # Sheet 1: 完整修正数据
                    df.to_excel(writer, index=False, sheet_name='Affinity_Data')

                    # Sheet 2: 参数记录 (Audit Trail)
                    params = {
                        "Project": project_id,
                        "User": researcher,
                        "Benchmark_kon": ref_kon,
                        "Benchmark_koff": ref_koff,
                        "Benchmark_KD": ref_kd,
                        "Applied_kon_Correction": kon_mult_opt,
                        "Applied_koff_Correction": koff_mult_opt
                    }
                    pd.DataFrame([params]).to_excel(writer, index=False, sheet_name='Parameters')

                st.download_button(
                    label="📥 下载分析结果 (Excel)",
                    data=output.getvalue(),
                    file_name=f"SPR_Analysis_{project_id}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="secondary",
                    use_container_width=True
                )

            # --- 按钮 B: 存数据库 ---
            with c_sv:
                if st.button("☁️ 保存至 PocketBase", type="primary", use_container_width=True):
                    uploaded_file.seek(0)
                    res_json = {
                        "benchmark": {"kon": ref_kon, "koff": ref_koff},
                        "summary_data": df.to_dict(orient="records")  # 存修正后的数据
                    }
                    save_experiment_record(project_id, researcher, uploaded_file, res_json)
                    st.success("已保存!")

        except Exception as e:
            st.error(f"Error: {e}")