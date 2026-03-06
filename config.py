# 配置文件，可自定义修改
import os

# Bark 推送配置
BARK_KEY = os.getenv("BARK_KEY", "你的Bark Key")
BARK_URL = f"https://api.day.app/{BARK_KEY}/"

# 监控的用户列表
MONITOR_USERS = [
    {
        "user_id": "20829162237257",
        "thread_id": "636748637",
        "current_page": 22,  # 改回初始页数22
        "is_first_run": True
    },
    {
        "user_id": "197319743786161",
        "thread_id": "636748637",
        "current_page": 1,
        "is_first_run": True
    }
]

# 状态文件路径
STATUS_FILE = "hupu_status.json"

# 请求超时时间
TIMEOUT = 15

# 首次运行推送条数
FIRST_RUN_LIMIT = 3

# 最大页数限制（避免无限递增）
MAX_PAGE_LIMIT = 50

# 调试文件保存目录
HTML_SAVE_DIR = "hupu_html"
