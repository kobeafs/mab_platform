import streamlit as st

if "is_logged_in" not in st.session_state or not st.session_state.is_logged_in:
    st.warning("请先回到主页进行登录")
    st.stop()
import streamlit as st
import sys
import os

# 1. 确保能找到 utils 文件夹 (关键步骤)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 2. 引入刚才建好的三个子模块
from utils.elisa_modules import bca, titer, screening

# 3. 页面设置
st.set_page_config(page_title="ELISA Analysis", layout="wide")

# 4. 侧边栏导航 (只在这里显示三个子选项)
st.sidebar.title("ELISA 导航")
module = st.sidebar.radio(
    "选择实验模式:",
    ["BCA 蛋白定量", "效价检测 (Titer)", "B细胞筛选"]
)

# 5. 根据选择加载对应的文件
if module == "BCA 蛋白定量":
    bca.show()
elif module == "效价检测 (Titer)":
    titer.show()
elif module == "B细胞筛选":
    screening.show()