import json
import requests
import time
import os
import re
from datetime import datetime
from config import (
    BARK_KEY, BARK_URL, MONITOR_USERS, STATUS_FILE,
    TIMEOUT, FIRST_RUN_LIMIT, MAX_PAGE_LIMIT, HTML_SAVE_DIR
)

# 强制创建HTML保存目录（确保目录存在）
os.makedirs(HTML_SAVE_DIR, exist_ok=True)

# 请求头（强化反爬策略，增加Cookie）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://bbs.hupu.com/stock",  # 股票区Referer，更贴合目标帖子
    "Cookie": "HUPU_SID=hupu; _clck=123456789; _clsk=abcdefg;",  # 通用Cookie，可替换为自己的
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0"
}

# 虎扑楼层解析正则（从静态页面提取关键信息）
FLOOR_PATTERN = re.compile(r'"pid":(\d+),"uid":(\d+),"username":"(.*?)","content":"(.*?)","createTime":"(.*?)"')

def load_status():
    """加载状态文件（记录已推送的内容）"""
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "pushed_items": {},
            "user_configs": MONITOR_USERS
        }

def save_status(status):
    """保存状态文件"""
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

def save_debug_file(content, filename, is_json=False):
    """保存调试文件（HTML/JSON）"""
    file_path = os.path.join(HTML_SAVE_DIR, filename)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            if is_json:
                json.dump(content, f, ensure_ascii=False, indent=2)
            else:
                f.write(content)
        print(f"✅ 调试文件已保存：{file_path}")
    except Exception as e:
        print(f"❌ 保存调试文件失败：{str(e)}")

def fetch_hupu_static_page(user_id, thread_id, page):
    """爬取并保存静态页面（核心调试手段）"""
    url = f"https://bbs.hupu.com/{thread_id}_{user_id}-{page}.html"
    print(f"\n=== 爬取静态页面 ===")
    print(f"URL：{url}")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        response.encoding = "utf-8"
        print(f"✅ 静态页面爬取成功，状态码：{response.status_code}")
        
        # 强制保存完整HTML
        save_debug_file(response.text, f"static_{user_id}_page{page}.html")
        
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"❌ 静态页面爬取失败：{str(e)}")
        # 保存错误信息
        save_debug_file(f"爬取失败：{str(e)}", f"error_{user_id}_page{page}.txt")
        return None

def parse_static_content(html, target_user_id):
    """从静态页面解析楼层数据（正则提取JSON中的楼层信息）"""
    print(f"\n=== 解析静态页面（目标用户ID：{target_user_id}）===")
    items = []
    
    if not html:
        print("❌ 无页面内容可解析")
        return items
    
    # 用正则提取楼层数据
    matches = FLOOR_PATTERN.findall(html)
    print(f"🔍 正则匹配到楼层数：{len(matches)}")
    
    for match in matches:
        try:
            floor_id = match[0]
            user_id = match[1]
            username = match[2].replace(r'\u003e', '>').replace(r'\u003c', '<').replace(r'\\"', '"')
            content = match[3].replace(r'\u003e', '>').replace(r'\u003c', '<').replace(r'\\"', '"').strip()
            create_time = match[4]
            
            # 过滤空内容
            if not content:
                continue
            
            print(f"\n--- 楼层 {floor_id} ---")
            print(f"用户ID：{user_id}（{username}）")
            print(f"时间：{create_time}")
            print(f"内容：{content[:200]}...")
            print(f"是否目标用户：{user_id == target_user_id}")
            
            # 只保留目标用户的内容
            if user_id == target_user_id:
                items.append({
                    "floor_id": floor_id,
                    "time": create_time,
                    "content": content,
                    "user_id": user_id
                })
        except Exception as e:
            print(f"❌ 解析单条楼层失败：{str(e)}")
            continue
    
    print(f"\n✅ 解析完成：目标用户有效楼层数 = {len(items)}")
    return items

def send_bark_notification(title, content):
    """通过Bark推送通知"""
    if not BARK_KEY:
        print("⚠️ Bark Key未配置，跳过推送")
        return False
    
    # 内容过长时截断（Bark有长度限制）
    if len(content) > 500:
        content = content[:500] + "..."
    
    try:
        response = requests.get(
            f"https://api.day.app/{BARK_KEY}/{title}/{content}",
            timeout=TIMEOUT,
            params={"isArchive": 1}
        )
        response.raise_for_status()
        print(f"✅ Bark推送成功：{title}")
        return True
    except Exception as e:
        print(f"❌ Bark推送失败：{str(e)}")
        return False

def monitor_single_user(user_config, status):
    """监控单个用户的帖子"""
    user_id = user_config["user_id"]
    thread_id = user_config["thread_id"]
    current_page = user_config["current_page"]
    is_first_run = user_config["is_first_run"]
    
    # 基础信息打印
    pushed_floors = status["pushed_items"].get(user_id, {})
    print(f"\n=====================================")
    print(f"监控用户：{user_id}")
    print(f"当前页数：{current_page} | 首次运行：{is_first_run}")
    print(f"已推送楼层：{list(pushed_floors.keys()) or ['无']}")
    print(f"最大页数限制：{MAX_PAGE_LIMIT}")
    print(f"=====================================")
    
    # 页数超限检查
    if current_page > MAX_PAGE_LIMIT:
        print(f"⚠️ 页数{current_page}超过最大值{MAX_PAGE_LIMIT}，停止监控")
        return
    
    # 1. 优先爬取静态页面（必保存，用于调试）
    html = fetch_hupu_static_page(user_id, thread_id, current_page)
    if not html:
        print(f"⚠️ 静态页面爬取失败，不递增页数")
        return
    
    # 2. 解析静态页面内容
    items = parse_static_content(html, user_id)
    
    # 3. 筛选未推送的新内容
    new_items = [item for item in items if item["floor_id"] not in pushed_floors]
    print(f"\n🔔 未推送新内容数：{len(new_items)}")
    
    # 4. 页数递增逻辑（仅当以下条件都满足时递增）
    # - 页面解析到楼层数据（总匹配数>0）
    # - 无目标用户内容
    # - 未超最大页数
    total_matched = len(FLOOR_PATTERN.findall(html))
    increment_page = False
    if len(items) == 0 and total_matched > 0 and current_page < MAX_PAGE_LIMIT:
        increment_page = True
        print(f"📄 页面有楼层但无目标用户内容，页数+1（{current_page}→{current_page+1}）")
    elif len(items) == 0 and total_matched == 0:
        print(f"📄 页面无任何楼层数据，不递增页数")
    else:
        print(f"📄 页面有目标用户内容，页数保持不变")
    
    # 5. 推送新内容
    if new_items:
        # 首次运行只推最新3条
        if is_first_run:
            new_items = new_items[-FIRST_RUN_LIMIT:]
            user_config["is_first_run"] = False
            print(f"🎉 首次运行，推送最新{FIRST_RUN_LIMIT}条内容")
        
        # 逐条推送
        for idx, item in enumerate(new_items):
            title = f"虎扑监控 | {user_id} | 楼层{item['floor_id']}"
            content = f"时间：{item['time']}\n内容：{item['content']}"
            send_bark_notification(title, content)
            # 标记已推送
            pushed_floors[item["floor_id"]] = 1
            time.sleep(1)  # 避免推送过快
    
    # 6. 更新页数（仅当满足条件时）
    if increment_page:
        user_config["current_page"] += 1
    
    # 7. 保存状态
    status["pushed_items"][user_id] = pushed_floors

def main():
    """主函数"""
    print(f"\n🚀 监控开始：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 安装依赖（如需）
    try:
        import bs4
    except ImportError:
        print("📦 安装依赖包...")
        import subprocess
        subprocess.check_call(["pip", "install", "beautifulsoup4", "requests"])
    
    # 加载状态
    status = load_status()
    
    # 遍历监控用户
    for user_config in status["user_configs"]:
        monitor_single_user(user_config, status)
    
    # 保存最终状态
    save_status(status)
    
    print(f"\n🛑 监控结束：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
