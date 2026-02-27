# app/utils/system_logic.py
import json


def add_log(pb, operator, module, action, details="", old_data=None, new_data=None):
    """
    通用日志记录函数 (v3.0 增强版)
    增加了 old_data 和 new_data 用于记录操作前后的数据快照
    """
    try:
        # 构造快照字典
        snapshot = {
            "before": old_data if old_data else {},
            "after": new_data if new_data else {}
        }

        data = {
            "operator": operator,
            "module": module,
            "action": action,
            "details": details,
            "change_snapshot": snapshot  # 注意：这个字段名要和 PocketBase 里的对应
        }

        pb.collection('logs').create(data)
        return True
    except Exception as e:
        # 在控制台打印错误，方便调试
        print(f"日志记录失败: {e}")
        return False