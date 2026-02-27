import streamlit as st

if "is_logged_in" not in st.session_state or not st.session_state.is_logged_in:
    st.warning("请先回到主页进行登录")
    st.stop()
import streamlit as st
import sys
import os

# 1. 路径设置 (这一步是为了让页面能找到 utils 文件夹)
# 获取当前文件所在目录的上级目录，即项目根目录
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 2. 引入我们在 utils 里写好的逻辑模块
try:
    from utils.affinity_modules import affinity
except ImportError as e:
    st.error(f"模块导入失败，请检查 utils/affinity_modules/affinity.py 是否存在。\n错误详情: {e}")
    st.stop()

# 3. 页面基础配置
st.set_page_config(
    page_title="SPR/BLI Affinity Analysis",
    layout="wide",
    page_icon="🧲"
)

# 4. 调用模块显示界面
if __name__ == "__main__":
    affinity.show()