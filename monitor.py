import json
import requests
import time
from datetime import datetime
from config import (
    BARK_KEY, BARK_URL, MONITOR_USERS, STATUS_FILE,
    TIMEOUT, FIRST_RUN_LIMIT
)

# 请求头（模拟浏览器，避免被反爬）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://bbs.hupu.com/"
}

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

def fetch_hupu_post(user_id, thread_id, page):
    """爬取虎扑帖子内容"""
    url = f"https://bbs.hupu.com/{thread_id}_{user_id}-{page}.html"
    print(f"\n=== 开始爬取：用户{user_id} 帖子{thread_id} 第{page}页 ===")
    print(f"请求URL：{url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()  # 抛出HTTP错误
        response.encoding = "utf-8"
        print(f"爬取成功，响应状态码：{response.status_code}")
        print(f"页面内容前2000字符：\n{response.text[:2000]}")  # 打印前2000字符，避免内容过长
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"爬取失败（用户ID：{user_id}，页数：{page}）：{str(e)}")
        return None

def parse_post_content(html, user_id):
    """解析帖子内容，提取关键信息"""
    from bs4 import BeautifulSoup  # 延迟导入，避免未安装报错
    soup = BeautifulSoup(html, "html.parser")
    
    print(f"\n=== 开始解析用户{user_id}的内容 ===")
    # 定位楼层内容（虎扑帖子的楼层class可能会变，需根据实际调整）
    floors = soup.find_all("div", class_="floor-box")  # 核心楼层容器
    print(f"找到的总楼层数：{len(floors)}")
    
    items = []
    # 打印所有楼层的原始信息（方便调试）
    for idx, floor in enumerate(floors):
        print(f"\n--- 楼层{idx+1}原始信息 ---")
        # 提取楼层ID（唯一标识，避免重复推送）
        floor_id = floor.get("data-floor", "")
        print(f"楼层ID：{floor_id}")
        
        # 提取发布时间
        time_elem = floor.find("span", class_="floor-time")
        floor_time = time_elem.get_text(strip=True) if time_elem else "未知时间"
        print(f"发布时间：{floor_time}")
        
        # 提取内容
        content_elem = floor.find("div", class_="floor-content")
        floor_content = content_elem.get_text(strip=True) if content_elem else "无内容"
        print(f"楼层内容：{floor_content[:500]}")  # 只打印前500字符
        
        # 提取用户名（验证是否是目标用户）
        author_elem = floor.find("a", class_="u-name")
        author_id = author_elem.get("data-userid", "") if author_elem else ""
        author_name = author_elem.get_text(strip=True) if author_elem else "未知用户"
        print(f"发帖用户ID：{author_id}，用户名：{author_name}")
        print(f"目标用户ID：{user_id}，是否匹配：{author_id == user_id}")
        
        # 只保留目标用户的内容
        if author_id == user_id:
            items.append({
                "floor_id": floor_id,
                "time": floor_time,
                "content": floor_content,
                "user_id": user_id
            })
    
    print(f"\n解析完成：目标用户{user_id}的有效楼层数：{len(items)}")
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
    
    # 爬取当前页内容
    html = fetch_hupu_post(user_id, thread_id, current_page)
    if not html:
        return
    
    # 解析内容
    items = parse_post_content(html, user_id)
    if not items:
        print(f"用户{user_id}第{current_page}页无目标用户内容")
        # 尝试下一页（自动刷新页数）
        user_config["current_page"] += 1
        return
    
    # 筛选未推送的内容
    new_items = [item for item in items if item["floor_id"] not in pushed_floors]
    print(f"未推送的新内容数：{len(new_items)}")
    
    if not new_items:
        print(f"用户{user_id}第{current_page}页无未推送内容，尝试下一页")
        user_config["current_page"] += 1
        return
    
    # 首次运行只取最新3条
    if is_first_run:
        new_items = new_items[-FIRST_RUN_LIMIT:]
        # 标记首次运行完成
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
    
    # 安装依赖（如果未安装）
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
