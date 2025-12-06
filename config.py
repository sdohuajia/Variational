# config.py - 配置文件
# 修改此文件来配置脚本参数

# ========== 基本配置 ==========
URL = "https://omni.variational.io/perpetual/BTC"
START_TIME = None  # 例如: "14:30:00" 或 None 表示立即启动

# ========== MoreLogin 配置（三选一）==========

# 方式1: 使用 MoreLogin API（需要 MoreLogin 客户端启动并登录）
# 在 MoreLogin 客户端中找到你的两个浏览器环境的 ID 或序号
# 环境ID 通常是长数字字符串，环境序号是整数（1, 2, 3...）
# 注意：如果 API 出现 "Http message not readable" 错误，请使用方式2（远程调试端口）
MORELOGIN_ENV1 = None  # 例如: 1760643143825056744 或 "1760643143825088744" 或 1  # 浏览器1的环境ID或序号
MORELOGIN_ENV2 = None  # 例如: 1760644815113397248 或 "1760644815193397248" 或 2  # 浏览器2的环境ID或序号
MORELOGIN_API_URL = "http://127.0.0.1:40000"  # MoreLogin API 地址，默认是本地40000端口（在 MoreLogin API 设置中查看）
MORELOGIN_API_ID = "None"  # MoreLogin API ID（在 MoreLogin API 设置中查看，例如: "None"）
MORELOGIN_API_KEY = "None"  # MoreLogin API Key（在 MoreLogin API 设置中查看，例如: "None"）

# 方式2: 使用远程调试端口（强烈推荐，最稳定可靠）⭐⭐⭐
# 步骤：
# 1. 在 MoreLogin 中手动打开两个浏览器窗口
# 2. 导航到交易页面: https://omni.variational.io/perpetual/BTC
# 3. 在 MoreLogin 中，右键浏览器 -> 设置 -> 启用远程调试
# 4. 记录下端口号（通常是 9222, 9223 等）
# 5. 填写下面的端口号
# 注意：如果 API 失败，脚本会自动尝试使用远程调试端口
MORELOGIN_PORT1 = None  # 例如: 9222  # 浏览器1的远程调试端口（在 MoreLogin 中查看）
MORELOGIN_PORT2 = None  # 例如: 9223  # 浏览器2的远程调试端口（在 MoreLogin 中查看）

# 方式3: 使用浏览器可执行文件路径
# 找到 MoreLogin 浏览器的 chrome.exe 路径
MORELOGIN_PATH1 = None  # 例如: r"C:\Users\YourName\AppData\Local\MoreLogin\Browser\Application\chrome.exe"
MORELOGIN_PATH2 = None  # 例如: r"C:\Users\YourName\AppData\Local\MoreLogin\Browser\Application\chrome.exe"

# ========== 交易配置 ==========
TRADING_PAIR = 'BTC'  # 交易币种，例如: 'BTC', 'ETH', 'SOL' 等
ORDER_QUANTITY = '0.015'  # 开仓数量，例如: '0.01' 表示 0.01 BTC
# 注意：浏览器1会自动开多（买），浏览器2会自动开空（卖），实现对冲
TP_VALUE = '3'  # 止盈数值 (%)
SL_VALUE = '3'  # 止损数值 (%)
ORDER_INTERVAL = 10  # 下单对齐周期（秒），例如 10 表示在 :00, :10, :20... 秒下单

# ========== 高级配置 ==========
COOLDOWN_AFTER_CLOSE = 120  # 平仓后等待多少秒再开新仓（给另一个浏览器时间）
WAIT_BEFORE_FORCE_CLOSE = 30  # 一个浏览器平仓后，等待多少秒再检查并平掉另一个浏览器的持仓


