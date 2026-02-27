import pandas as pd
import io


def get_96_well_struct():
    """返回96孔板的行（A-H）和列（1-12）"""
    rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    cols = [str(i) for i in range(1, 13)]
    return rows, cols


def format_db_to_grid(records):
    """将PocketBase记录列表转换为以slot为Key的字典"""
    grid_data = {}
    for rec in records:
        grid_data[rec.slot] = {
            "id": rec.id,
            "rack_id": getattr(rec, 'rack_id', 'Unassigned'),
            "project_name": rec.project_name,
            "sample_id": rec.sample_id,
            "sample_type": rec.sample_type,
            "conc_mgml": rec.conc_mgml,
            "vol_ul": rec.vol_ul,
            "box_name": rec.box_name
        }
    return grid_data


def generate_excel_template():
    """生成带示例数据的Excel导入模板"""
    df = pd.DataFrame({
        'rack_id': ['Rack-01', 'Rack-01', 'Rack-02'],
        'slot': ['A1', 'A2', 'B1'],
        'project_name': ['Project-A', 'Project-A', 'Project-B'],
        'sample_id': ['Clone-001', 'Clone-002', 'Ctrl-Pos'],
        'sample_type': ['Purified mAb', 'Purified mAb', 'Serum'],
        'conc_mgml': [1.2, 0.5, 0.0],
        'vol_ul': [500, 200, 1000]
    })
    output = io.BytesIO()
    # 需要安装 pip install xlsxwriter
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventory_Template')
    return output.getvalue()


def process_excel_upload(uploaded_file):
    """解析上传的Excel并进行预处理"""
    try:
        df = pd.read_excel(uploaded_file)
        df.columns = [c.lower().strip() for c in df.columns]  # 统一列名格式

        # 检查核心列
        if 'slot' not in df.columns or 'sample_id' not in df.columns:
            return None, "错误：Excel必须包含 'slot' 和 'sample_id' 列"

        # 格式化slot列
        df['slot'] = df['slot'].astype(str).str.upper().str.strip()
        return df, "OK"
    except Exception as e:
        return None, f"解析失败: {str(e)}"
