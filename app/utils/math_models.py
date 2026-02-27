import numpy as np
from scipy.stats import linregress


# --- 线性拟合 (旧的保留) ---
def linear_fit(x, y):
    slope, intercept, r_value, p_value, std_err = linregress(x, y)
    r_squared = r_value ** 2

    def model_func(y_input):
        # x = (y - c) / m
        return (y_input - intercept) / slope

    return model_func, r_squared, f"y = {slope:.4f}x + {intercept:.4f}"


# --- 二次多项式拟合 (Quadratic Fit) ---
def poly_fit(x, y):
    """
    拟合 y = ax^2 + bx + c
    并返回一个能通过 y 计算 x 的函数
    """
    # 1. 拟合 (2代表二次)
    coeffs = np.polyfit(x, y, 2)
    a, b, c = coeffs

    # 计算 R²
    p = np.poly1d(coeffs)
    y_pred = p(x)
    y_mean = np.mean(y)
    ss_tot = np.sum((y - y_mean) ** 2)
    ss_res = np.sum((y - y_pred) ** 2)
    r_squared = 1 - (ss_res / ss_tot)

    # 2. 定义反算函数 (已知 OD 算 Conc)
    def model_func(y_input):
        # 解方程: ax^2 + bx + (c - y_input) = 0
        # x = [-b ± sqrt(b^2 - 4a(c-y))] / 2a
        # BCA 曲线通常是单调的，我们取正根或在合理范围内的根

        delta = b ** 2 - 4 * a * (c - y_input)

        # 如果 delta < 0，说明 OD 值超出了曲线范围（无解），返回 0 或 NaN
        if isinstance(delta, (int, float)):
            if delta < 0: return np.nan
            root1 = (-b + np.sqrt(delta)) / (2 * a)
            root2 = (-b - np.sqrt(delta)) / (2 * a)
            # 返回正值的那个解 (浓度不能为负)
            return root1 if root1 >= 0 else root2
        else:
            # 处理数组输入
            delta[delta < 0] = np.nan
            root1 = (-b + np.sqrt(delta)) / (2 * a)
            root2 = (-b - np.sqrt(delta)) / (2 * a)
            # 简单的逻辑：BCA通常斜率为正，选较大的根或较小的根视 a 的符号而定
            # 这里做一个简单处理：返回非负结果
            res = np.where(root1 >= 0, root1, root2)
            return res

    formula_str = f"y = {a:.2e}x² + {b:.4f}x + {c:.4f}"
    return model_func, r_squared, formula_str


# ... (上面是之前的 linear_fit 和 poly_fit) ...

from scipy.optimize import curve_fit


# --- 4PL 拟合 (EC50 核心算法) ---
def four_pl_model(x, A, B, C, D):
    """
    4PL 方程:
    y = D + (A - D) / (1 + (x / C) ** B)

    A: Bottom (底值/最小值)
    D: Top (顶值/最大值)
    C: EC50 (半最大效应浓度)
    B: Hill Slope (斜率)
    """
    return D + (A - D) / (1 + (x / C) ** B)


def fit_4pl(x_data, y_data):
    """
    执行 4PL 拟合
    返回: 拟合参数(A,B,C,D), R², 拟合曲线生成函数
    """
    x = np.array(x_data)
    y = np.array(y_data)

    # 1. 初始参数猜测 (p0) - 这对 curve_fit 收敛至关重要
    # 否则很容易报 "Optimal parameters not found"
    try:
        p0_A = min(y)  # Bottom
        p0_D = max(y)  # Top
        p0_C = np.median(x)  # EC50 猜中间浓度
        p0_B = 1.0  # Slope 猜 1
        p0 = [p0_A, p0_B, p0_C, p0_D]

        # 2. 执行拟合
        # maxfev=10000 增加迭代次数防止报错
        popt, pcov = curve_fit(four_pl_model, x, y, p0=p0, maxfev=10000)
        A, B, C, D = popt

        # 3. 计算 R²
        residuals = y - four_pl_model(x, *popt)
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot)

        # 4. 封装预测函数 (方便画图)
        def predict_func(x_in):
            return four_pl_model(x_in, A, B, C, D)

        return popt, r_squared, predict_func

    except Exception as e:
        # 拟合失败
        return None, 0, None