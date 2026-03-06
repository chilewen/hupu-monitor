import json
import requests
import time
import os
from datetime import datetime
from config import (
    BARK_KEY, BARK_URL, MONITOR_USERS, STATUS_FILE,
    TIMEOUT, FIRST_RUN_LIMIT
)

# 请求头（模拟浏览器，避免被反爬）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://bbs.hupu.com/",
    "X-Requested-With": "XMLHttpRequest"
}

# 新增配置：最大页数限制（避免页数无限递增）
MAX_PAGE_LIMIT = 50
# 保存页面HTML的目录
HTML_SAVE_DIR = "hupu_html"

# 确保HTML保存目录存在
if not os.path.exists(HTML_SAVE_DIR):
    os.makedirs(HTML_SAVE_DIR)

def load_status():
    """加载状态文件（记录已推送的内容）"""
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # 首次运行，初始化状态
        return {
            "pushed_items": {},  # 格式：{user_id: {floor_id: 1}}
            "user_configs": MONITOR_USERS
        }

def save_status(status):
    """保存状态文件"""
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

def save_html_content(html, user_id, page):
    """保存完整的HTML内容到文件，方便调试"""
    file_path = os.path.join(HTML_SAVE_DIR, f"hupu_{user_id}_page{page}.html")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"完整HTML已保存到：{file_path}")

def fetch_hupu_post_dynamic(thread_id, page):
    """
    爬取虎扑新版页面的动态数据（通过真实接口）
    thread_id: 帖子ID（如636748637）
    page: 页数
    """
    # 虎扑新版楼层数据接口（抓包获取）
    api_url = f"https://bbs.hupu.com/api/v1/bbs/thread/content?tid={thread_id}&pageNo={page}&pageSize=20"
    print(f"\n=== 开始爬取动态数据 ===")
    print(f"API请求URL：{api_url}")
    
    try:
        response = requests.get(api_url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        print(f"API响应状态码：{response.status_code}")
        # 保存API响应内容
        api_file = os.path.join(HTML_SAVE_DIR, f"hupu_api_{thread_id}_page{page}.json")
        with open(api_file, "w", encoding="utf-8") as f:
            json.dump(response.json(), f, ensure_ascii=False, indent=2)
        print(f"API响应已保存到：{api_file}")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API爬取失败：{str(e)}")
        return None

def fetch_hupu_post_static(user_id, thread_id, page):
    """爬取虎扑静态页面（备用）"""
    url = f"https://bbs.hupu.com/{thread_id}_{user_id}-{page}.html"
    print(f"\n=== 开始爬取静态页面 ===")
    print(f"请求URL：{url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        response.encoding = "utf-8"
        print(f"爬取成功，响应状态码：{response.status_code}")
        # 保存完整HTML到文件
        save_html_content(response.text, user_id, page)
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"静态页面爬取失败：{str(e)}")
        return None

def parse_dynamic_content(api_data, target_user_id):
    """解析动态API返回的楼层数据"""
    print(f"\n=== 开始解析动态数据（目标用户ID：{target_user_id}）===")
    items = []
    
    if not api_data or "data" not in api_data or "posts" not in api_data["data"]:
        print("API返回数据格式异常")
        return items
    
    posts = api_data["data"]["posts"]
    print(f"API返回总楼层数：{len(posts)}")
    
    for post in posts:
        try:
            # 提取核心信息
            floor_id = str(post.get("pid", ""))  # 楼层ID
            user_id = str(post.get("author", {}).get("uid", ""))  # 发帖用户ID
            user_name = post.get("author", {}).get("username", "未知用户")  # 用户名
            floor_time = post.get("createTime", "未知时间")  # 发布时间
            # 提取内容（处理富文本）
            content = post.get("content", "")
            # 去除HTML标签
            import re
            content = re.sub(r'<[^>]+>', '', content).strip()
            
            print(f"\n--- 楼层ID：{floor_id} ---")
            print(f"发帖用户ID：{user_id}，用户名：{user_name}")
            print(f"发布时间：{floor_time}")
            print(f"内容：{content[:500]}")
            print(f"是否目标用户：{user_id == target_user_id}")
            
            # 只保留目标用户的内容
            if user_id == target_user_id:
                items.append({
                    "floor_id": floor_id,
                    "time": floor_time,
                    "content": content,
                    "user_id": user_id
                })
        except Exception as e:
            print(f"解析单条楼层失败：{str(e)}")
            continue
    
    print(f"\n解析完成：目标用户的有效楼层数：{len(items)}")
    return items

def send_bark_notification(title, content):
    """通过Bark推送通知"""
    if not BARK_KEY:
        print("Bark Key未配置，跳过推送")
        return False
    
    params = {
        "title": title,
        "body": content,
        "isArchive": 1  # 保存到Bark历史
    }
    
    try:
        response = requests.get(BARK_URL, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        print(f"Bark推送成功：{title}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Bark推送失败：{str(e)}")
        return False

def monitor_single_user(user_config, status):
    """监控单个用户的帖子"""
    user_id = user_config["user_id"]
    thread_id = user_config["thread_id"]
    current_page = user_config["current_page"]
    is_first_run = user_config["is_first_run"]
    
    # 加载已推送的楼层ID
    pushed_floors = status["pushed_items"].get(user_id, {})
    print(f"\n=== 监控用户{user_id} ===")
    print(f"当前页数：{current_page}，首次运行：{is_first_run}")
    print(f"已推送的楼层ID：{list(pushed_floors.keys())}")
    print(f"最大页数限制：{MAX_PAGE_LIMIT}")
    
    # 检查页数是否超过最大值
    if current_page > MAX_PAGE_LIMIT:
        print(f"当前页数{current_page}超过最大值{MAX_PAGE_LIMIT}，停止递增")
        return
    
    # 优先爬取动态API数据
    api_data = fetch_hupu_post_dynamic(thread_id, current_page)
    if not api_data:
        # API爬取失败，尝试静态页面（备用）
        fetch_hupu_post_static(user_id, thread_id, current_page)
        print(f"用户{user_id}第{current_page}页API爬取失败，不递增页数")
        return
    
    # 解析动态数据
    items = parse_dynamic_content(api_data, user_id)
    
    # 筛选未推送的内容
    new_items = [item for item in items if item["floor_id"] not in pushed_floors]
    print(f"未推送的新内容数：{len(new_items)}")
    
    # 页数递增逻辑调整：
    # 1. 只有当页面有楼层数据（总楼层数>0）但无目标用户内容时，才递增页数
    # 2. 页数不超过最大值
    total_floors = len(api_data["data"]["posts"]) if api_data and "data" in api_data and "posts" in api_data["data"] else 0
    if len(items) == 0 and total_floors > 0 and current_page < MAX_PAGE_LIMIT:
        print(f"页面有楼层数据但无目标用户内容，页数递增（{current_page} → {current_page+1}）")
        user_config["current_page"] += 1
    elif len(items) == 0 and total_floors == 0:
        print(f"页面无任何楼层数据，不递增页数（当前页数：{current_page}）")
    else:
        print(f"页面有目标用户内容，页数保持不变（{current_page}）")
    
    if not new_items:
        return
    
    # 首次运行只取最新3条
    if is_first_run:
        new_items = new_items[-FIRST_RUN_LIMIT:]
        user_config["is_first_run"] = False
        print(f"首次运行，推送用户{user_id}最新{FIRST_RUN_LIMIT}条内容")
    
    # 推送内容到Bark
    for item in new_items:
        title = f"虎扑监控-{user_id}-{item['time']}"
        content = item["content"]
        send_bark_notification(title, content)
        # 记录已推送
        pushed_floors[item["floor_id"]] = 1
    
    # 更新状态
    status["pushed_items"][user_id] = pushed_floors

def main():
    """主函数"""
    print(f"监控开始：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 安装依赖
    try:
        import bs4
    except ImportError:
        print("安装BeautifulSoup4依赖...")
        import subprocess
        subprocess.check_call(["pip", "install", "beautifulsoup4", "requests"])
    
    # 加载状态
    status = load_status()
    
    # 遍历所有监控用户
    for user_config in status["user_configs"]:
        monitor_single_user(user_config, status)
    
    # 保存状态
    save_status(status)
    print(f"\n监控结束：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
