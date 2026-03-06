# 配置文件，可自定义修改
import os

# Bark 推送配置（优先从环境变量读取，避免硬编码）
BARK_KEY = os.getenv("BARK_KEY", "你的Bark Key")  # 替换为你的Bark Key，或在GitHub Secrets中配置
BARK_URL = f"https://api.day.app/{BARK_KEY}/"

# 监控的用户列表（支持多个用户）
# 格式：{"user_id": 用户ID, "thread_id": 帖子ID, "current_page": 初始页数, "is_first_run": 是否首次运行}
MONITOR_USERS = [
    {
        "user_id": "20829162237257",
        "thread_id": "636748637",
        "current_page": 22,
        "is_first_run": True  # 首次运行标记，执行后会自动改为False
    },
    # 可添加更多用户
    # {
    #     "user_id": "另一个用户ID",
    #     "thread_id": "对应帖子ID",
    #     "current_page": 1,
    #     "is_first_run": True
    # }
]

# 状态文件路径（记录已推送的内容，避免重复）
STATUS_FILE = "hupu_status.json"

# 请求超时时间
TIMEOUT = 10

# 每次获取最新条数（首次运行）
FIRST_RUN_LIMIT = 3
