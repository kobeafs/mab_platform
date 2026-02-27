# app/db.py
from pocketbase import PocketBase
import streamlit as st
import requests
import json

PB_URL = "http://127.0.0.1:8090"

def get_db():
    """
    核心：单例模式。确保整个应用生命周期内，
    所有页面使用的都是同一个 st.session_state.pb 对象。
    """
    if "pb" not in st.session_state:
        # 如果 session 里没有，就创建一个新的
        st.session_state.pb = PocketBase(PB_URL)
    return st.session_state.pb

# 导出全局变量 pb，供其他页面直接 import pb 使用
pb = get_db()

def login_auth(email, password):
    """供 main.py 登录页面调用"""
    client = get_db()
    try:
        # 统一使用 collection('users') 认证，适配你设置的 API Rules
        auth_data = client.collection('users').auth_with_password(email, password)
        st.session_state.is_logged_in = True
        st.session_state.user_info = auth_data.record
        return True, "登录成功"
    except Exception as e:
        st.session_state.is_logged_in = False
        return False, str(e)

def logout():
    """退出登录"""
    client = get_db()
    client.auth_store.clear()
    st.session_state.is_logged_in = False
    st.session_state.user_info = None
    st.rerun()

# --- 以下是你原来的逻辑，完全保留，确保其他模块不报错 ---

def save_experiment_record(project, name, file_obj, results):
    """保留原来的 requests 手动上传逻辑，不做变动"""
    client = get_db()
    try:
        token = client.auth_store.token  # 这里会自动获取到登录后的新 Token
        headers = {"Authorization": token}
        data_payload = {
            "project_id": project,
            "researcher": name,
            "result_json": json.dumps(results)
        }
        files_payload = {
            "raw_data_file": (file_obj.name, file_obj.getvalue())
        }
        api_url = f"{PB_URL}/api/collections/experiments/records"
        response = requests.post(api_url, headers=headers, data=data_payload, files=files_payload)
        if response.status_code == 200:
            return True, "保存成功！"
        else:
            return False, f"保存失败: {response.text}"
    except Exception as e:
        return False, f"发生错误: {str(e)}"

def fetch_all_experiments():
    """保留原来的获取逻辑"""
    url = f"{PB_URL}/api/collections/experiments/records?perPage=500"
    client = get_db()
    try:
        token = client.auth_store.token
        res = requests.get(url, headers={"Authorization": token}, timeout=5)
        if res.status_code == 200:
            return res.json().get("items", [])
        return []
    except Exception as e:
        print(f"Fetch Error: {e}")
        return []