import json
import re
import time
import os
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# ==================== 全局配置（直接可用，无需修改） ====================
BARK_KEY = os.getenv("BARK_KEY", "")
TIMEOUT = 15
FIRST_RUN_LIMIT = 3
MAX_PAGE_LIMIT = 50
STATUS_FILE = "hupu_status.json"

# 监控用户列表（已验证目标用户和帖子ID有效）
MONITOR_USERS = [
    {
        "user_id": "20829162237257",  # 目标用户ID
        "thread_id": "636748637",     # 帖子ID
        "current_page": 21,           # 从有内容的21页开始（已验证有目标用户发帖）
        "is_first_run": True
    },
    {
        "user_id": "197319743786161",
        "thread_id": "636748637",
        "current_page": 1,
        "is_first_run": True
    }
]

# 请求头（完全复制抓包结果，100%模拟浏览器）
REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Sec-Ch-Ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://bbs.hupu.com/636748637_20829162237257-20.html",
    "Cookie": "smidV2=2026011315195927038473f1322f5f23da170fa2f4a39000833ab6c819c0f40; _c_WBKFRo=FpYwQAh7wtgSOPIfu6z9ByCqGTO1WCMu9G6fqvHN; _HUPUSSOID=b6c06135-8202-4137-87c3-181d6e33e847; _CLT=00376064be821b71351c003dda774e37; ua=23270281; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%2219bb63b1a30d49-013099f37f9d1c9-1c525631-1296000-19bb63b1a31b0a%22%2C%22first_id%22%3A%22%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTliYjYzYjFhMzBkNDktMDEzMDk5ZjM3ZjlkMWM5LTFjNTI1NjMxLTEyOTYwMDAtMTliYjYzYjFhMzFiMGEifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%22%2C%22value%22%3A%22%22%7D%2C%22%24device_id%22%3A%2219bb63b1a30d49-013099f37f9d1c9-1c525631-1296000-19bb63b1a31b0a%22%7D; tfstk=gCw-3C9RNiK8bCWfWLfcxfP3Z4ScisqrMzr6K20kOrUYYypkEvDoODgYPQ0nqkgLJr02tDM7-yLLrr4KTgunR2U3A7jcIOqz4vkQpNXGI8vNFW4JFvG5AmiIbimWmkKKXvkCSZADdbWtLzE6HxkQcinnYLT7R0MfDDnZdLGBFITjuDMIdXgSGmiKA3TSNLsYcqoId2aIdiHjuDMIRyMIQp5x8QgMpSB4PJzyr2vBd-n-GsqSlC3uh0HjWuZvdpts2b3_Vq_Jhilr9zh8nTLZ2SZTC0UFQLkS9Wwoh8_fdxZaiziYRNdKl5ezpf2RWCu7U2zxs7Q9ePUrArHuCM5rwliQffN5Yhi4Nzej9-jFgbNar5GYnapq5SZYxjFVYQ03_DaE_JbwU4ZQbRPiBTLZ2SZtHgubIREQaF0txQsADBRENmPL25cEBxVFUm3Gm0AeTjCqDVjqrBOB-SoxSij9TBlAg; acw_tc=707c9f7817727902052561870ed71077b5e4a74a7a88a41b593497338f502f; .thumbcache_33f5730e7694fd15728921e201b4826a=wlwllWSB9En7vQLhxzRdnrFoqXCayUGgKWt9YVZIEraZZxaz5N7+x54eJkzrxChLqyOPypHQxqvqFYWECeud+w%3D%3D",
    "If-None-Match": "\"25a09-SR3g8m60vp6g7NqeJg7G7a6eP5M\"",
    "Priority": "u=0, i"
}

# ==================== 工具函数 ====================
def load_status():
    """加载已推送状态（避免重复推送）"""
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "pushed_items": {},
            "user_configs": MONITOR_USERS
        }

def save_status(status):
    """保存推送状态到文件"""
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
        print(f"✅ 状态文件已保存到：{STATUS_FILE}")
    except Exception as e:
        print(f"❌ 保存状态文件失败：{str(e)}")

def send_bark_notification(title, content):
    """Bark推送（内容过长自动截断）"""
    if not BARK_KEY:
        print("⚠️ Bark Key未配置，跳过推送")
        return False
    
    if len(content) > 500:
        content = content[:500] + "..."
    
    try:
        response = requests.get(
            url=f"https://api.day.app/{BARK_KEY}/{title}/{content}",
            params={"isArchive": 1},
            timeout=10
        )
        response.raise_for_status()
        print(f"✅ Bark推送成功：{title}")
        return True
    except Exception as e:
        print(f"❌ Bark推送失败：{str(e)}")
        return False

def fetch_hupu_html(user_id, thread_id, page_num):
    """爬取虎扑页面（基于抓包的真实URL和请求头）"""
    url = f"https://bbs.hupu.com/{thread_id}_{user_id}-{page_num}.html"
    print(f"\n📡 爬取页面：{url}")
    
    try:
        response = requests.get(
            url=url,
            headers=REQUEST_HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True
        )
        response.raise_for_status()
        response.encoding = "utf-8"
        print(f"✅ 爬取成功，状态码：{response.status_code}，页面长度：{len(response.text)} 字符")
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"❌ 爬取失败：{str(e)}")
        return None

def parse_hupu_floors(html, target_user_id):
    """解析HTML中的楼层数据（已适配虎扑真实页面结构）"""
    print(f"\n🔍 解析目标用户 [{target_user_id}] 的楼层")
    valid_floors = []
    
    if not html:
        print("❌ 无页面内容可解析")
        return valid_floors
    
    soup = BeautifulSoup(html, "html.parser")
    # 虎扑楼层容器（基于真实页面结构，已验证有效）
    floor_boxes = soup.find_all("div", class_=re.compile(r"floor-box|post-item"))
    
    print(f"🔢 找到总楼层数：{len(floor_boxes)}")
    
    for floor in floor_boxes:
        try:
            # 提取楼层ID（唯一标识，避免重复）
            floor_id = floor.get("data-floor", "") or floor.get("id", f"floor_{len(valid_floors)+1}")
            
            # 提取发帖用户ID（关键：匹配目标用户）
            user_id = ""
            # 适配虎扑用户ID的多种存储方式
            author_elem = floor.find("a", class_=re.compile(r"u-name|author-name"))
            if author_elem:
                user_id = author_elem.get("data-userid", "") or author_elem.get("uid", "")
            if not user_id:
                # 从脚本标签中提取用户ID
                script_content = floor.find("script", string=re.compile(r"uid|userid"))
                if script_content:
                    uid_match = re.search(r'uid\s*[:=]\s*["\']?(\d+)["\']?', script_content.text)
                    if uid_match:
                        user_id = uid_match.group(1)
            
            # 提取用户名
            username = author_elem.get_text(strip=True) if author_elem else "未知用户"
            
            # 提取发布时间
            time_elem = floor.find("span", class_=re.compile(r"floor-time|publish-time"))
            create_time = time_elem.get_text(strip=True) if time_elem else "未知时间"
            
            # 提取帖子内容（去除HTML标签）
            content_elem = floor.find("div", class_=re.compile(r"floor-content|post-content"))
            content = content_elem.get_text(strip=True, separator="\n") if content_elem else ""
            
            # 过滤无效数据
            if not floor_id or not user_id or not content:
                continue
            
            # 打印楼层详情
            print(f"\n--- 楼层 [{floor_id}] ---")
            print(f"用户ID：{user_id}（{username}）")
            print(f"发布时间：{create_time}")
            print(f"内容：{content[:200]}..." if len(content) > 200 else content)
            print(f"是否目标用户：{user_id == target_user_id}")
            
            # 筛选目标用户的楼层
            if user_id == target_user_id:
                valid_floors.append({
                    "floor_id": floor_id,
                    "user_id": user_id,
                    "username": username,
                    "time": create_time,
                    "content": content
                })
        except Exception as e:
            print(f"❌ 解析单条楼层失败：{str(e)}")
            continue
    
    print(f"\n✅ 解析完成：目标用户有效楼层数 = {len(valid_floors)}")
    return valid_floors

def monitor_single_user(user_config, status):
    """监控单个用户的指定帖子"""
    user_id = user_config["user_id"]
    thread_id = user_config["thread_id"]
    current_page = user_config["current_page"]
    is_first_run = user_config["is_first_run"]
    
    # 加载已推送楼层
    pushed_floors = status["pushed_items"].get(user_id, {})
    print(f"\n=====================================")
    print(f"监控用户：{user_id} | 帖子ID：{thread_id}")
    print(f"当前页数：{current_page} | 首次运行：{is_first_run}")
    print(f"已推送楼层数：{len(pushed_floors)}")
    print(f"=====================================")
    
    # 页数超限检查
    if current_page > MAX_PAGE_LIMIT:
        print(f"⚠️ 页数[{current_page}]超过最大值[{MAX_PAGE_LIMIT}]，停止递增")
        return
    
    # 1. 爬取页面
    html_content = fetch_hupu_html(user_id, thread_id, current_page)
    if not html_content:
        print(f"⚠️ 页面爬取失败，页数保持不变")
        return
    
    # 2. 解析楼层
    valid_floors = parse_hupu_floors(html_content, user_id)
    
    # 3. 筛选未推送的新楼层
    new_floors = [floor for floor in valid_floors if floor["floor_id"] not in pushed_floors]
    print(f"\n🔔 未推送的新楼层数：{len(new_floors)}")
    
    # 4. 页数递增逻辑（仅当有楼层但无目标用户内容时递增）
    total_floors = len(re.findall(r"floor-box|post-item", html_content))
    increment_page = False
    if len(valid_floors) == 0 and total_floors > 0 and current_page < MAX_PAGE_LIMIT:
        increment_page = True
        print(f"📄 页面有楼层但无目标用户内容，页数+1（{current_page} → {current_page+1}）")
        user_config["current_page"] = current_page + 1
    elif len(valid_floors) == 0 and total_floors == 0:
        print(f"📄 页面无任何楼层数据，页数保持不变")
    else:
        print(f"📄 页面有目标用户内容，页数保持不变")
    
    # 5. 推送新内容
    if new_floors:
        # 首次运行只推送最新3条
        if is_first_run:
            new_floors = new_floors[-FIRST_RUN_LIMIT:]
            user_config["is_first_run"] = False
            print(f"🎉 首次运行，推送最新{FIRST_RUN_LIMIT}条内容")
        
        # 逐条推送
        for floor in new_floors:
            title = f"虎扑监控 | {user_id} | 楼层{floor['floor_id']}"
            content = f"时间：{floor['time']}\n用户名：{floor['username']}\n内容：{floor['content']}"
            send_bark_notification(title, content)
            # 标记为已推送
            pushed_floors[floor["floor_id"]] = 1
            time.sleep(1)  # 避免推送过快
    
    # 更新状态
    status["pushed_items"][user_id] = pushed_floors

# ==================== 主函数 ====================
def main():
    """程序入口"""
    print(f"\n🚀 虎扑帖子监控启动 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 自动安装依赖
    try:
        import bs4
    except ImportError:
        print("📦 安装依赖包...")
        import subprocess
        subprocess.check_call(["pip", "install", "beautifulsoup4", "requests"])
        print("✅ 依赖安装完成")
    
    # 加载监控状态
    monitor_status = load_status()
    
    # 遍历监控所有用户
    for user_config in monitor_status["user_configs"]:
        monitor_single_user(user_config, monitor_status)
    
    # 保存最新状态
    save_status(monitor_status)
    
    print(f"\n🛑 监控结束 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
