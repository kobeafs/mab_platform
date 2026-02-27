import streamlit as st
import pandas as pd
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
# 组件：绘制 384 象限示意图 (HTML/CSS)
# ==========================================
def show_384_guide_component():
    """
    使用 HTML 渲染一个直观的 384 象限映射图
    """
    st.markdown("""
    <style>
        .guide-container {
            display: flex;
            gap: 20px;
            align-items: center;
            margin-bottom: 20px;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 8px;
            border: 1px solid #e9ecef;
        }
        .plate-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 2px;
            border: 2px solid #333;
            padding: 2px;
            background: #fff;
        }
        .well {
            width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 10px;
            font-weight: bold;
            color: #fff;
            border-radius: 50%;
        }
        .q1 { background-color: #2c7bb6; } /* 蓝 */
        .q2 { background-color: #d7191c; } /* 红 */
        .q3 { background-color: #fdae61; color: #333; } /* 橙 */
        .q4 { background-color: #abdda4; color: #333; } /* 绿 */

        .legend-box { font-size: 14px; line-height: 1.8; }
        .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 5px; }
    </style>

    <div class="guide-container">
        <div>
            <div style="text-align:center; font-weight:bold; margin-bottom:5px;">384 孔板局部示意 (A1-B2)</div>
            <div class="plate-grid">
                <!-- Row A -->
                <div class="well q1">A1</div> <div class="well q2">A2</div>
                <!-- Row B -->
                <div class="well q3">B1</div> <div class="well q4">B2</div>
            </div>
        </div>
        <div class="legend-box">
            <strong>象限映射规则 (Interleaved):</strong><br>
            <span class="dot q1"></span> <strong>Q1 (Source 1)</strong>: 奇数行 / 奇数列 (A1, A3...)<br>
            <span class="dot q2"></span> <strong>Q2 (Source 2)</strong>: 奇数行 / 偶数列 (A2, A4...)<br>
            <span class="dot q3"></span> <strong>Q3 (Source 3)</strong>: 偶数行 / 奇数列 (B1, B3...)<br>
            <span class="dot q4"></span> <strong>Q4 (Source 4)</strong>: 偶数行 / 偶数列 (B2, B4...)
        </div>
    </div>
    """, unsafe_allow_html=True)


# ==========================================
# 辅助函数：读取 96 孔板
# ==========================================
def parse_plate_96(file_obj, plate_name):
    try:
        df_raw = pd.read_excel(file_obj, header=None)
        df_matrix = df_raw.iloc[0:8, 0:12].copy()
        df_matrix.index = list('ABCDEFGH')
        df_matrix.columns = list(range(1, 13))
        df_matrix = df_matrix.apply(pd.to_numeric, errors='coerce').fillna(0)

        data = []
        for r in df_matrix.index:
            for c in df_matrix.columns:
                val = df_matrix.loc[r, c]
                data.append({
                    "Plate": plate_name, "Well": f"{r}{c}", "Row": r, "Col": c, "OD": float(val), "Source": "Direct"
                })
        return pd.DataFrame(data), [("96_Plate", df_matrix, plate_name)]
    except:
        return None, None


# ==========================================
# 辅助函数：读取 384 孔板并拆分
# ==========================================
def parse_plate_384(file_obj, filename_base):
    try:
        df_raw = pd.read_excel(file_obj, header=None)
        df_384 = df_raw.iloc[0:16, 0:24].copy()

        rows_96 = list('ABCDEFGH')
        cols_96 = list(range(1, 13))
        plates = {k: pd.DataFrame(index=rows_96, columns=cols_96) for k in ["Q1", "Q2", "Q3", "Q4"]}

        data_list = []
        rows_384 = list('ABCDEFGHIJKLMNOP')

        for r_384 in range(16):
            for c_384 in range(24):
                val = df_384.iloc[r_384, c_384]
                val = float(val) if (pd.notna(val) and isinstance(val, (int, float))) else 0.0

                # 坐标变换
                r_96 = r_384 // 2
                c_96 = c_384 // 2
                row_lbl = rows_96[r_96]
                col_lbl = cols_96[c_96]

                is_r_even = (r_384 % 2 == 0)
                is_c_even = (c_384 % 2 == 0)

                if is_r_even and is_c_even:
                    q = "Q1"
                elif is_r_even and not is_c_even:
                    q = "Q2"
                elif not is_r_even and is_c_even:
                    q = "Q3"
                else:
                    q = "Q4"

                plates[q].loc[row_lbl, col_lbl] = val

                plate_name_final = f"{filename_base}_{q}"
                well_384 = f"{rows_384[r_384]}{c_384 + 1}"

                data_list.append({
                    "Plate": plate_name_final, "Well": f"{row_lbl}{col_lbl}",
                    "Row": row_lbl, "Col": col_lbl, "OD": val, "Source": f"384-{well_384}"
                })

        matrix_list = []
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            name = f"{filename_base}_{q}"
            matrix_list.append((q, plates[q], name))

        return pd.DataFrame(data_list), matrix_list
    except:
        return None, None


# ==========================================
# 样式函数
# ==========================================
def highlight_hits(val, cutoff):
    try:
        if float(val) >= cutoff:
            return 'background-color: #ffcccc; color: #cc0000; font-weight: bold; border: 1px solid #ffaaaa'
        else:
            return 'background-color: #ffffff; color: #cccccc; border: 1px solid #eeeeee'
    except:
        return ''


# ==========================================
# 主界面
# ==========================================
def show():
    st.header("🔍 B细胞/杂交瘤高通量筛选 (HTS)")
    st.info("💡 支持 96 孔板直接上传，或 384 孔板 (4合1) 自动拆分。")

    # --- 1. 设置 ---
    with st.container():
        c1, c2, c3 = st.columns([1, 1, 1])
        project_id = c1.text_input("项目编号", value="Screen-2024", key="scr_p")
        researcher = c2.text_input("实验员", value="User", key="scr_u")
        plate_type = c3.selectbox("板型格式", ["96-Well (Standard)", "384-Well (4-in-1 Split)"], index=0)

    # --- 2. 384 模式下的图示引导 (新增) ---
    if "384" in plate_type:
        show_384_guide_component()

    # --- 3. 导入 ---
    st.subheader("1. 数据导入")
    label = "📂 批量上传 96 孔 Excel" if "96" in plate_type else "📂 批量上传 384 孔 Excel"
    uploaded_files = st.file_uploader(label, type=["xlsx", "xls"], accept_multiple_files=True, key="scr_up")

    if not uploaded_files:
        st.warning("请上传数据文件。")
        return

    # --- 4. 阈值 ---
    st.subheader("2. 阳性阈值 (Cutoff)")
    c_rule, c_val = st.columns([2, 1])
    with c_rule:
        method = st.radio("判定策略",
                          ["固定阈值 (Fixed OD)", "基于阴性对照 (Neg + 3SD)", "动态统计 (板内后10%数据为背景)"])
    with c_val:
        manual_cutoff = 0.5
        neg_pos = "H12"
        if "固定" in method:
            manual_cutoff = st.number_input("OD >", 0.5, step=0.1)
        elif "阴性对照" in method:
            neg_pos = st.text_input("阴性孔位 (96孔坐标)", "H12")

    # --- 5. 分析逻辑 ---
    if st.button("🚀 开始分析 & 拆解数据", type="primary"):
        all_data_long = []
        plate_matrices = []  # 用于显示的列表
        # 用于 Excel 导出的字典： { "Filename": { "Q1": matrix, "Q2": matrix... } }
        plate_groups_for_excel = {}
        summary_stats = []

        progress = st.progress(0)

        for i, f in enumerate(uploaded_files):
            progress.progress((i + 1) / len(uploaded_files))
            fname = f.name.split('.')[0]

            # 这里的 fname 作为分组的 Key
            plate_groups_for_excel[fname] = {}

            if "96" in plate_type:
                df_long, matrices = parse_plate_96(f, fname)
            else:
                df_long, matrices = parse_plate_384(f, fname)

            if df_long is None: continue

            # 处理每一块(虚拟)板
            for q_tag, df_matrix, final_name in matrices:
                # 筛选当前板的数据
                sub_df_long = df_long[df_long['Plate'] == final_name].copy()

                # 计算 Cutoff
                cutoff = 0.5
                if "固定" in method:
                    cutoff = manual_cutoff
                elif "阴性对照" in method:
                    try:
                        nr, nc = neg_pos[0].upper(), int(neg_pos[1:])
                        neg_val = df_matrix.loc[nr, nc]
                        cutoff = neg_val * 3.0 if neg_val > 0.1 else neg_val + 0.2
                    except:
                        cutoff = 0.5
                elif "动态" in method:
                    vals = sorted(sub_df_long['OD'].values)
                    bg = vals[:10]
                    cutoff = np.mean(bg) + 3 * np.std(bg)
                    if cutoff < 0.2: cutoff = 0.2

                sub_df_long['Cutoff'] = cutoff
                sub_df_long['Result'] = sub_df_long['OD'].apply(lambda x: 'Positive' if x >= cutoff else 'Negative')
                hits = len(sub_df_long[sub_df_long['Result'] == 'Positive'])

                all_data_long.append(sub_df_long)

                # 存入列表用于网页展示
                plate_matrices.append({
                    "name": final_name,
                    "matrix": df_matrix,
                    "cutoff": cutoff,
                    "hits": hits
                })

                # 存入字典用于 Excel 导出 (保留 Q 标签)
                # 结构: groups["File1"]["Q1"] = {matrix, cutoff}
                plate_groups_for_excel[fname][q_tag if "384" in plate_type else "96_Plate"] = {
                    "matrix": df_matrix,
                    "cutoff": cutoff
                }

                summary_stats.append({
                    "Source File": fname, "Plate ID": final_name, "Cutoff": cutoff, "Hits": hits
                })

        progress.empty()

        if all_data_long:
            df_final = pd.concat(all_data_long, ignore_index=True)
            df_hits = df_final[df_final['Result'] == 'Positive'].sort_values(by='OD', ascending=False)

            # --- 展示结果 ---
            st.markdown("---")
            st.subheader(f"3. 筛选结果 (共 {len(df_hits)} 个阳性)")

            t1, t2, t3 = st.tabs(["📊 板图概览", "📋 挑克隆名单", "📈 统计"])

            with t1:
                st.caption("以下展示拆解后的 **96孔板视图**。")
                for pm in plate_matrices:
                    title = f"🧩 板号: {pm['name']} (Hits: {pm['hits']})"
                    with st.expander(title, expanded=True):
                        styler = pm['matrix'].style \
                            .format("{:.3f}") \
                            .applymap(lambda x: highlight_hits(x, pm['cutoff']))
                        st.dataframe(styler, use_container_width=True, height=330)

            with t2:
                cols = ['Plate', 'Well', 'OD', 'Result', 'Cutoff']
                if "384" in plate_type: cols.append('Source')
                st.dataframe(df_hits[cols].style.background_gradient(subset=['OD'], cmap='Reds'),
                             use_container_width=True)

            with t3:
                st.dataframe(pd.DataFrame(summary_stats), use_container_width=True)

            # --- 下载与保存 ---
            st.markdown("---")
            c1, c2 = st.columns([1, 1])
            with c1:
                # --- Excel 导出核心逻辑 (田字格布局) ---
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    wb = writer.book
                    # 格式：红底红字
                    red_fmt = wb.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})

                    # 1. 名单 & 统计
                    df_hits.to_excel(writer, sheet_name='Pick_List', index=False)
                    pd.DataFrame(summary_stats).to_excel(writer, sheet_name='Summary', index=False)

                    # 2. 板图 (按源文件分组，每个文件一个 Sheet)
                    for file_base, quadrants in plate_groups_for_excel.items():
                        # Sheet 名限制 31 字符
                        sheet_name = file_base[:30]
                        ws = wb.add_worksheet(sheet_name)

                        # 如果是 96 孔，只有一个
                        if "96_Plate" in quadrants:
                            info = quadrants["96_Plate"]
                            ws.write(0, 0, f"Plate: {file_base} (Cutoff: {info['cutoff']:.3f})")
                            # 写入数据
                            # Pandas to_excel 不能直接指定 writer 的 cell，需要手动循环或转换
                            # 这里简单点：直接把 DataFrame 写在特定位置
                            # 为了方便，我们临时创建一个 writer 只写这部分是不行的，必须全手动

                            # 手动写入 96 孔矩阵 (带表头)
                            # 写表头
                            ws.write_row(1, 0, [""] + list(range(1, 13)))
                            for r_idx, r_label in enumerate(list('ABCDEFGH')):
                                ws.write(r_idx + 2, 0, r_label)  # 行号
                                for c_idx in range(12):
                                    val = info['matrix'].iloc[r_idx, c_idx]
                                    ws.write(r_idx + 2, c_idx + 1, val)
                                    # 条件格式
                                    if val >= info['cutoff']:
                                        ws.write(r_idx + 2, c_idx + 1, val, red_fmt)

                        else:
                            # 384 模式：田字格排布
                            # Q1 (0,0) | Q2 (0, 14)
                            # Q3 (11,0) | Q4 (11, 14)

                            positions = {
                                "Q1": (0, 0),  # Row 0, Col 0
                                "Q2": (0, 14),  # Row 0, Col 14 (中间空1列 + 行标题)
                                "Q3": (11, 0),  # Row 11, Col 0 (中间空2行)
                                "Q4": (11, 14)
                            }

                            for q_tag, pos in positions.items():
                                if q_tag in quadrants:
                                    info = quadrants[q_tag]
                                    start_r, start_c = pos

                                    # 标题
                                    ws.write(start_r, start_c, f"{q_tag} (Cutoff: {info['cutoff']:.3f})")

                                    # 表头 (1-12)
                                    ws.write_row(start_r + 1, start_c + 1, list(range(1, 13)))

                                    # 数据主体
                                    for r_idx, r_label in enumerate(list('ABCDEFGH')):
                                        # 行号 (A-H)
                                        ws.write(start_r + r_idx + 2, start_c, r_label)

                                        for c_idx in range(12):
                                            val = info['matrix'].iloc[r_idx, c_idx]
                                            cell_r = start_r + r_idx + 2
                                            cell_c = start_c + c_idx + 1

                                            ws.write(cell_r, cell_c, val)
                                            if val >= info['cutoff']:
                                                ws.write(cell_r, cell_c, val, red_fmt)

                st.download_button("📥 下载筛选报告 (田字格打印版)", output.getvalue(), f"Screen_{project_id}.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   type="secondary", use_container_width=True)

            with c2:
                if st.button("☁️ 保存至 PocketBase", type="primary", use_container_width=True):
                    if uploaded_files:
                        uploaded_files[0].seek(0)
                        res_json = {"summary": summary_stats, "top_hits": df_hits.head(50).to_dict(orient="records")}
                        success, msg = save_experiment_record(project_id, researcher, uploaded_files[0], res_json)
                        if success:
                            st.success("已保存!")
                        else:
                            st.error(msg)