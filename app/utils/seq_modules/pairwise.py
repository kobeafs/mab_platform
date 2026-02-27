import streamlit as st
from Bio.Seq import Seq
import py3Dmol
from stmol import showmol


# ==========================================
# 1. 3D 渲染函数：加粗、表面、高亮、偏移量
# ==========================================
def render_3d_structure(pdb_string, mutated_indices, risk_indices, offset=0):
    view = py3Dmol.view(width=800, height=550)
    view.addModel(pdb_string, "pdb")

    # --- 1. 设置基础样式 (全灰) ---
    # 我们把基础飘带设为稍微透明的灰色
    view.setStyle({'cartoon': {'color': '#e0e0e0', 'thickness': 1.0, 'opacity': 0.6}})

    # --- 2. 渲染“一段红”（错义突变） ---
    # 我们直接修改突变残基对应的 cartoon 颜色
    for idx in mutated_indices:
        pdb_idx = str(idx + offset)
        # 修改这一段飘带的颜色为红色，并加厚
        view.setStyle({'resi': pdb_idx}, {'cartoon': {'color': '#d9534f', 'thickness': 1.2}})
        # 保留一个小球和标签作为指引
        view.addLabel(f"MUT:{pdb_idx}",
                      {'fontSize': 10, 'fontColor': '#d9534f', 'backgroundColor': 'white', 'backgroundOpacity': 0.5},
                      {'resi': pdb_idx})

    # --- 3. 渲染“一段黄”（成药性风险） ---
    for r_idx in risk_indices:
        pdb_idx = str(r_idx + offset)
        # 如果是风险位点，将飘带改为黄色
        # 注意：如果既是突变又是风险，后面这行会覆盖颜色，通常风险比突变更值得关注
        view.setStyle({'cartoon': {'color': '#e0e0e0', 'thickness': 1.0}},
                      {'outline': {'color': 'black', 'width': 0.1}})
        view.addLabel(f"RISK:{pdb_idx}", {'fontSize': 10, 'fontColor': '#8a6d3b', 'backgroundColor': '#fcf8e3'},
                      {'resi': pdb_idx})

    # --- 4. 辅助展示 ---
    # 增加侧链显示（淡色），增加细节感
    view.addStyle({'stick': {'radius': 0.1, 'opacity': 0.3}})

    view.setBackgroundColor('#ffffff')
    view.zoomTo()
    view.spin(True)
    showmol(view, height=550, width=800)


# ==========================================
# 2. 风险扫描逻辑
# ==========================================
def scan_liabilities(protein_seq):
    risks = []
    risk_indices = []
    motifs = {
        "NG": "脱酰胺 (Deamidation)",
        "DG": "异构化 (Isomerization)",
        "DP": "酸裂解 (Cleavage)",
        "NXS": "糖基化 (Glycosylation)",
        "NXT": "糖基化 (Glycosylation)"
    }
    for i in range(len(protein_seq) - 1):
        sub_2, sub_3 = protein_seq[i:i + 2], protein_seq[i:i + 3]
        for m, desc in motifs.items():
            if m in [sub_2, sub_3]:
                risks.append({"位点": i + 1, "基序": m, "风险类型": desc})
                risk_indices.extend([i + 1, i + 2] if len(m) == 2 else [i + 1, i + 2, i + 3])
    return risks, list(set(risk_indices))


# ==========================================
# 3. HTML 比对视图函数
# ==========================================
def render_dna_protein_alignment(ref_seq_str, query_seq_str):
    """
    通过 CSS 强制 1AA : 3DNA 对齐的渲染函数
    """
    ref_seq_str = ref_seq_str.upper().strip()
    query_seq_str = query_seq_str.upper().strip()

    # 翻译序列
    ref_aa = str(Seq(ref_seq_str).translate())
    query_aa = str(Seq(query_seq_str).translate())

    # CSS 样式：定义单元格宽度
    html = """
    <style>
        .seq-wrapper { font-family: 'Consolas', 'Courier New', monospace; font-size: 15px; line-height: 1.8; }
        .seq-block { margin-bottom: 30px; padding: 15px; background: #f8f9fa; border-left: 5px solid #007bff; border-radius: 4px; }

        /* 标签列固定宽度 */
        .label { display: inline-block; width: 50px; color: #888; font-weight: bold; font-size: 12px; }

        /* 碱基单元：1个字符宽 */
        .b { display: inline-block; width: 1ch; text-align: center; }

        /* 氨基酸单元：3个字符宽，确保对齐下方的3个碱基 */
        .aa { display: inline-block; width: 3ch; text-align: center; font-weight: bold; }

        /* 颜色定义 */
        .m { color: #d9534f; background: #fce8e8; font-weight: bold; } /* DNA突变 */
        .match { color: #ccc; } /* 一致部分 */
        .aa-m { color: #d9534f; text-decoration: underline; } /* 错义突变 */
        .aa-s { color: #5bc0de; } /* 同义突变 */
    </style>
    <div class='seq-wrapper'>
    """

    chunk_size = 60  # 每行显示 60bp (20AA)
    length = min(len(ref_seq_str), len(query_seq_str))

    for i in range(0, length, chunk_size):
        end = min(i + chunk_size, length)
        dna_r = ref_seq_str[i:end]
        dna_q = query_seq_str[i:end]
        aa_r = ref_aa[i // 3: end // 3]
        aa_q = query_aa[i // 3: end // 3]

        # --- 第一行：Reference AA ---
        html += f"<div class='seq-block'><div class='row'><span class='label'>REF AA</span>"
        for aa in aa_r:
            html += f"<span class='aa'>{aa}</span>"
        html += "</div>"

        # --- 第二行：Reference DNA ---
        html += f"<div class='row'><span class='label'>{i + 1:03d}</span>"
        for base in dna_r:
            html += f"<span class='b'>{base}</span>"
        html += "</div>"

        # --- 第三行：Clone DNA (对比) ---
        html += f"<div class='row'><span class='label'>CLO</span>"
        diff_in_codon = []  # 记录哪些密码子发生了突变
        for j, (r, q) in enumerate(zip(dna_r, dna_q)):
            if r == q:
                html += f"<span class='b match'>.</span>"
            else:
                html += f"<span class='b m'>{q}</span>"
                diff_in_codon.append(j // 3)  # 记录突变所属的氨基酸索引
        html += "</div>"

        # --- 第四行：Clone AA / Diff (对比) ---
        html += f"<div class='row'><span class='label'>DIFF</span>"
        for k, (ar, aq) in enumerate(zip(aa_r, aa_q)):
            has_dna_mut = (k in diff_in_codon)
            if ar == aq:
                if has_dna_mut:
                    # 同义突变 (蓝色)
                    html += f"<span class='aa aa-s'>{aq}</span>"
                else:
                    # 完全一致 (灰色点)
                    html += f"<span class='aa match'>.</span>"
            else:
                # 错义突变 (红色下划线)
                html += f"<span class='aa aa-m'>{aq}</span>"
        html += "</div></div>"

    html += "</div>"
    return html


# ==========================================
# 4. 主入口 show 函数
# ==========================================
def show():
    st.header("⚖️ 序列差异比对与 3D 成药性扫描")

    col_a, col_b = st.columns(2)
    with col_a:
        ref_seq = st.text_area("Reference (DNA)",
                               value="CAGTCGGTGGAGGAGTCCGGGGGTCGCCTGGTCACGCCTGGGACACCCCTGACACTCACCTGCACAGTCTCTGGATTCTCCCTCAGTAGCTATGCAATGAGCTGGGTCCGCCAGGCTCCAGGGAAGGGGCTGGAATGGATCGGA",
                               height=120)
    with col_b:
        clone_seq = st.text_area("Clone (DNA)",
                                 value="CAGTCGGTGGAGGAGTCCGGGGGTCGCCTGGTCACGCCTGGGACACCCCTGACACTCACCTGCACAGTCTCTGGATTCTCCCTCAGTAGCTATGCATTGAGCTGGGTCCGCCAGGCTCCAGGGAAGGGGCTGGAATGGATCGGT",
                                 height=120)

    st.markdown("### 🧪 3D 结构映射配置")
    cp1, cp2 = st.columns([3, 1])
    with cp1:
        uploaded_pdb = st.file_uploader("📂 上传参考结构 (.pdb)", type=['pdb'])
    with cp2:
        offset = st.number_input("PDB 序号偏移量", value=0, help="如果PDB第一个残基序号是10，序列是从1开始，请输入9")

    if st.button("🚀 开始双维综合分析", type="primary"):
        s1, s2 = ref_seq.replace("\n", "").strip().upper(), clone_seq.replace("\n", "").strip().upper()
        if len(s1) != len(s2):
            st.error("⚠️ 序列长度不一致，无法进行 3D 映射。")
            return

        # 1. 序列比对
        st.markdown("#### 1️⃣ 序列对比视图")
        st.markdown(render_dna_protein_alignment(s1, s2), unsafe_allow_html=True)

        # 2. 逻辑计算
        ref_aa = str(Seq(s1).translate())
        clone_aa = str(Seq(s2).translate())
        mutated_indices = [i + 1 for i, (r, q) in enumerate(zip(ref_aa, clone_aa)) if r != q]
        risks, risk_indices = scan_liabilities(clone_aa)

        # 3. 风险展示
        if risks:
            st.warning("⚠️ 检测到成药性风险位点：")
            st.table(risks)
        else:
            st.success("✅ 未检测到明显的成药性基序风险。")

        # 4. 3D 渲染
        if uploaded_pdb:
            st.markdown("#### 2️⃣ 3D 空间风险投影 (红色:突变 / 黄色:风险)")
            pdb_str = uploaded_pdb.getvalue().decode("utf-8")
            render_3d_structure(pdb_str, mutated_indices, risk_indices, offset)
        else:
            st.info("ℹ️ 上传 PDB 文件后即可查看 3D 空间投影。")