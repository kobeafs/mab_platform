# SmartLab-mAb: 抗体研发数字化管理平台 🐰🧪

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-red.svg)](https://streamlit.io/)
[![Database](https://img.shields.io/badge/DB-PocketBase-green.svg)](https://pocketbase.io/)

### 🚀 为什么开发这个项目？
在 7 年的兔单抗一线研发中，我发现传统实验室依赖 Excel 记录数据，存在**数据散乱、无法溯源、库存更新滞后**等痛点。本项目通过 Python 全栈开发，旨在构建一个“干湿结合”的数字化工作流。

---

### 📸 界面演示 (预览)
<img width="1901" height="904" alt="主页" src="https://github.com/user-attachments/assets/a6e31afe-da8b-4109-b39a-334189c021c9" />
<img width="1810" height="860" alt="ScreenShot_2026-02-28_011620_994" src="https://github.com/user-attachments/assets/8db3b57d-2642-444b-997d-fdb64e2aee31" />
进入登录界面后，可以在主页查看所有信息

*图1：ELISA 自动化数据分析看板*
<img width="1833" height="874" alt="ScreenShot_2026-02-28_011838_955" src="https://github.com/user-attachments/assets/bea98813-1256-45a5-b84e-79dfc4933145" />
包含ELISA定量，效价检测，B细胞筛选。定量以及效价检测支持一键拟合计算，B细胞支持批量上传96孔/384孔原始数据，设置阳性阈值，并生成分表总表，一键导出汇总表，方便打印挑克隆。


*图2：WB数据分析*
<img width="1815" height="908" alt="ScreenShot_2026-02-28_012124_923" src="https://github.com/user-attachments/assets/902fff36-9ead-405a-8591-d9904c5842db" />
一键框选条带，自动读取光密度，计算纯度以及浓度。

图3：免疫录入
<img width="1849" height="874" alt="ScreenShot_2026-02-28_011709_531" src="https://github.com/user-attachments/assets/a465e437-1f04-437d-a90d-fc711805fe67" />
免疫可用excel批量导入兔子，并勾选采血等操作，再导出excel，并支持搜索功能

图4：序列分析
<img width="1784" height="864" alt="ScreenShot_2026-02-28_012223_939" src="https://github.com/user-attachments/assets/df267360-45bc-4385-9a21-69e66db3e0c0" />
序列分析支持风险扫描 (NG, DG, DP, Met)，序列比对，3D结构映射，批量比对。

图5：SPR分析
<img width="1812" height="872" alt="ScreenShot_2026-02-28_012403_762" src="https://github.com/user-attachments/assets/aa1c7773-7427-4fd0-841e-3f33e1e025e9" />
亲和力分析排序，动力学模拟

图6：库存管理
<img width="1824" height="876" alt="ScreenShot_2026-02-28_012425_267" src="https://github.com/user-attachments/assets/51bef0ba-50aa-4153-a106-76dbf7265c76" />
可手动储存样品录入，也可下载excel模板批量操作，搜索样本，项目号，抗体，兔号的准确位置

图7：pocketbase
<img width="1912" height="898" alt="ScreenShot_2026-02-28_015810_001" src="https://github.com/user-attachments/assets/b9175f2e-7540-4215-83fc-c922e28727cb" />
使用pocketbase储存数据，具备数据库存储（内置 SQLite），用户权限，REST API，文件存储，后台管理面板功能，保障数据合规，操作溯源。


---

### ✨ 核心功能
- **📊 实验数据自动化**：一键上传 ELISA/SPR 原始数据，自动生成拟合曲线与可视化报表。
- **🧬 序列资产管理**：抗体序列结构化存储，支持生信分析与表位标注。
- **📦 智能库存质控**：样品入库，出库，录入。
- **🔒 安全账户体系**：基于 PocketBase 实现多用户权限管理，确保研发数据安全。

---

### 🛠️ 技术架构
- **前端可视化**: Streamlit
- **后端/数据库**: PocketBase (Golang powered)
- **数据处理**: Pandas, NumPy, Plotly
- **生物信息**: Biopython

---

### 👨‍🔬 作者寄语
本项目是我从“传统实验员”向“数字化研发人员”转型的代表作。它不仅是一个工具，更是我对抗体研发流程标准化的思考。
