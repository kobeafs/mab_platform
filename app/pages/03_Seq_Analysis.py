import streamlit as st

if "is_logged_in" not in st.session_state or not st.session_state.is_logged_in:
    st.warning("请先回到主页进行登录")
    st.stop()
import streamlit as st
import pandas as pd
import numpy as np
import sys
import os
import io
import json
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import seaborn as sns
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.Align import PairwiseAligner

# --- 路径设置 (确保能引用 utils) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# --- 引入数据库和工具 ---
from db import save_experiment_record

# 引入比对渲染工具
try:
    from utils.seq_modules import pairwise
except ImportError:
    pairwise = None # 或者处理报错

# ==========================================
# 0. 全局配置
# ==========================================
st.set_page_config(page_title="Seq Analysis Pro", layout="wide", page_icon="🧬")
st.title("🧬 序列分析一体机 (Seq Analysis Pro)")

if 'seq_analysis_result' not in st.session_state:
    st.session_state['seq_analysis_result'] = None

# ==========================================
# 1. 侧边栏：全局设置
# ==========================================
st.sidebar.header("📝 实验信息")
project_id = st.sidebar.text_input("项目编号", value="SEQ-2024-001")
researcher = st.sidebar.text_input("实验员", value="User")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 分析参数")
genetic_code = st.sidebar.selectbox("遗传密码表", [1, 11], index=0, help="1=标准, 11=细菌/古菌")

# ==========================================
# 2. 核心功能区
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs([
    "🧬 翻译 & 风险扫描",
    "⚖️ 双序列比对 (Pairwise)",
    "🌳 批量聚类 (Clustering)",
    "📈 测序峰图 (.ab1)"
])

# --- TAB 1: 翻译 ---
with tab1:
    st.markdown("### DNA -> Protein 翻译与成药性检查")
    col_t1, col_t2 = st.columns([1, 1])
    with col_t1:
        seq_input = st.text_area("输入 DNA 序列 (支持多行FASTA或纯序列)", height=200, placeholder=">Clone1\nATGCGC...")
    with col_t2:
        st.info("ℹ️ **功能说明**\n- 自动翻译\n- 风险扫描 (NG, DG, DP, Met)\n- Cys 二硫键检查")

    if seq_input:
        sequences = []
        if ">" in seq_input:
            parts = seq_input.split(">")
            for p in parts:
                if not p.strip(): continue
                lines = p.strip().split("\n")
                name = lines[0]
                seq_str = "".join(lines[1:]).replace("\n", "").replace(" ", "").upper()
                sequences.append({"name": name, "dna": seq_str})
        else:
            sequences.append({"name": "Input_Seq", "dna": seq_input.replace("\n", "").replace(" ", "").upper()})

        results = []
        for s in sequences:
            try:
                dna_obj = Seq(s['dna'])
                padding = (3 - len(dna_obj) % 3) % 3
                protein = str((dna_obj + "N" * padding).translate(table=genetic_code))

                liabilities = []
                if "NG" in protein: liabilities.append("NG")
                if "DG" in protein: liabilities.append("DG")
                if "DP" in protein: liabilities.append("DP")
                if "M" in protein: liabilities.append("Met")
                if "C" in protein: liabilities.append(f"Cys x {protein.count('C')}")

                results.append({
                    "Name": s['name'], "Protein Length": len(protein), "Protein Seq": protein,
                    "Risks": ", ".join(liabilities) if liabilities else "Pass"
                })
            except Exception as e:
                st.error(f"解析失败: {e}")

        if results:
            df_trans = pd.DataFrame(results)
            st.markdown("#### 分析结果")
            st.dataframe(df_trans.style.applymap(
                lambda x: "background-color: #ffcccc" if "NG" in str(x) or "DG" in str(x) else "", subset=["Risks"]),
                         use_container_width=True)
            st.session_state['seq_analysis_result'] = df_trans.to_dict(orient="records")

# --- TAB 2: 比对 ---
with tab2:
    if pairwise:
        pairwise.show()  # 直接调用我们在 pairwise.py 里写好的带 3D 逻辑的完整界面
    else:
        st.error("无法加载 utils.seq_modules.pairwise 模块")

# --- TAB 3: 聚类 ---
with tab3:
    st.markdown("### 批量序列相似度分析")
    msa_file = st.file_uploader("上传 Excel", type=["xlsx", "csv"], key="msa_upload")

    if msa_file:
        try:
            df_msa = pd.read_excel(msa_file) if msa_file.name.endswith("xlsx") else pd.read_csv(msa_file)
            target_col = next((c for c in df_msa.columns if "seq" in c.lower() or "dna" in c.lower()), None)

            if target_col:
                st.success(f"已识别序列列: `{target_col}`")
                if st.button("计算相似度热图"):
                    seqs = df_msa[target_col].dropna().astype(str).tolist()
                    names = df_msa.iloc[:, 0].astype(str).tolist()

                    from difflib import SequenceMatcher

                    n = len(seqs)
                    matrix = np.zeros((n, n))
                    for i in range(n):
                        for j in range(n):
                            if i == j:
                                matrix[i][j] = 1.0
                            elif i < j:
                                r = SequenceMatcher(None, seqs[i], seqs[j]).ratio()
                                matrix[i][j] = r
                                matrix[j][i] = r

                    fig, ax = plt.subplots(figsize=(8, 6))
                    sns.heatmap(matrix, xticklabels=names, yticklabels=names, cmap="viridis", ax=ax)
                    st.pyplot(fig)
                    # 将 numpy 矩阵转 list，否则 JSON 保存会报错
                    st.session_state['seq_analysis_result'] = {"matrix": matrix.tolist(), "names": names}
            else:
                st.error("未找到包含 'Seq' 或 'DNA' 的列")
        except Exception as e:
            st.error(f"读取失败: {e}")

# --- TAB 4: AB1 ---
with tab4:
    st.markdown("### 测序峰图查看器")
    ab1_file = st.file_uploader("上传 .ab1 文件", type=["ab1", "abi"])

    if ab1_file:
        try:
            record = SeqIO.read(ab1_file, "abi")
            raw = record.annotations['abif_raw']
            channels = ['DATA9', 'DATA10', 'DATA11', 'DATA12']
            colors, bases = ['black', 'green', 'red', 'blue'], ['G', 'A', 'T', 'C']

            fig = go.Figure()
            for i, chan in enumerate(channels):
                if chan in raw:
                    fig.add_trace(
                        go.Scatter(y=raw[chan], mode='lines', name=bases[i], line=dict(color=colors[i], width=1)))

            fig.update_layout(title=f"Trace: {ab1_file.name}", height=400, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
            st.text_area("Base Call Sequence", str(record.seq), height=100)

            # AB1 结果比较大，这里只存由机器读出的序列文本
            st.session_state['seq_analysis_result'] = {"read_sequence": str(record.seq)}
        except Exception as e:
            st.error(f"AB1 解析失败: {e}")

# ==========================================
# 3. 底部保存区 (修复版)
# ==========================================
st.markdown("---")
col_save, _ = st.columns([1, 4])

with col_save:
    if st.button("💾 保存分析记录到 Database", type="primary", use_container_width=True):

        # 1. 准备要保存的文件对象
        final_file_obj = None

        # 优先级 A: AB1 文件 (如果是 AB1 模式)
        if ab1_file:
            ab1_file.seek(0)
            final_file_obj = ab1_file

        # 优先级 B: Excel 文件 (如果是聚类模式)
        elif msa_file:
            msa_file.seek(0)
            final_file_obj = msa_file

        # 优先级 C: 纯文本输入 (如果没有物理文件，我们创建一个虚拟文件)
        # 这对于保存 TAB1 和 TAB2 的结果非常重要
        elif seq_input or (seq_a and seq_b):
            # 将文本内容打包成一个 .fasta 文件
            content = ""
            if seq_input:
                content += f"# Translation Input\n{seq_input}\n"
            if seq_a:
                content += f"\n# Alignment\n>Ref\n{seq_a}\n>Clone\n{seq_b}"

            # 创建内存文件流
            final_file_obj = io.BytesIO(content.encode('utf-8'))
            final_file_obj.name = "sequence_input.fasta"  # PocketBase 需要文件名

        # 2. 准备 JSON 数据 (处理 NumPy 序列化问题)
        try:
            # 确保数据是纯 Python 类型 (List, Dict, Str, Float)
            raw_data = st.session_state.get('seq_analysis_result', {})
            # 使用 json.loads(json.dumps(...)) 技巧或者 default=str 是一种简单清洗方式
            # 这里我们手动确保它是一个 dict
            if raw_data is None: raw_data = {"status": "No analysis result generated"}

            # 构造 Payload
            json_payload = {
                "module": "Sequence Analysis",
                "data": raw_data
            }
        except Exception as e:
            st.error(f"数据格式化错误: {e}")
            st.stop()

        # 3. 执行保存
        if final_file_obj:
            # 再次确保指针在开头
            final_file_obj.seek(0)

            # 调用 db.py
            success, msg = save_experiment_record(
                project=project_id,
                name=researcher,
                file_obj=final_file_obj,
                results=json_payload
            )

            if success:
                st.success("✅ 保存成功！")
            else:
                st.error(f"❌ 保存失败: {msg}")
        else:
            st.warning("没有检测到任何输入数据（文件或文本），无法保存。")