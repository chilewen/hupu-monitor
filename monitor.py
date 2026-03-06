import json
import re
import time
import os
import requests
from datetime import datetime

# ==================== 全局配置 ====================
BARK_KEY = os.getenv("BARK_KEY", "")  # GitHub Secrets 配置
TIMEOUT = 15
FIRST_RUN_LIMIT = 3  # 首次运行只推送最新3条
MAX_PAGE_LIMIT = 50  # 最大翻页限制
STATUS_FILE = "hupu_status.json"  # 状态保存文件

# 监控用户列表（euid 是目标用户标识）
MONITOR_USERS = [
    {
        "user_euid": "20829162237257",  # 目标用户euid
        "thread_id": "636748637",       # 帖子ID
        "current_page": 21,             # 起始页码（你指定的21页）
        "is_first_run": True
    },
    {
        "user_euid": "197319743786161", # 其他监控用户
        "thread_id": "636748637",
        "current_page": 1,
        "is_first_run": True
    }
]

# 请求头（保持和你抓包一致）
REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Cookie": "smidV2=2026011315195927038473f1322f5f23da170fa2f4a39000833ab6c819c0f40; _c_WBKFRo=FpYwQAh7wtgSOPIfu6z9ByCqGTO1WCMu9G6fqvHN; _HUPUSSOID=b6c06135-8202-4137-87c3-181d6e33e847; _CLT=00376064be821b71351c003dda774e37; ua=23270281; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%2219bb63b1a30d49-013099f37f9d1c9-1c525631-1296000-19bb63b1a31b0a%22%2C%22first_id%22%3A%22%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTliYjYzYjFhMzBkNDktMDEzMDk5ZjM3ZjlkMWM5LTFjNTI1NjMxLTEyOTYwMDAtMTliYjYzYjFhMzFiMGEifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%22%2C%22value%22%3A%22%22%7D%2C%22%24device_id%22%3A%2219bb63b1a30d49-013099f37f9d1c9-1c525631-1296000-19bb63b1a31b0a%22%7D; tfstk=gCw-3C9RNiK8bCWfWLfcxfP3Z4ScisqrMzr6K20kOrUYYypkEvDoODgYPQ0nqkgLJr02tDM7-yLLrr4KTgunR2U3A7jcIOqz4vkQpNXGI8vNFW4JFvG5AmiIbimWmkKKXvkCSZADdbWtLzE6HxkQcinnYLT7R0MfDDnZdLGBFITjuDMIdXgSGmiKA3TSNLsYcqoId2aIdiHjuDMIRyMIQp5x8QgMpSB4PJzyr2vBd-n-GsqSlC3uh0HjWuZvdpts2b3_Vq_Jhilr9zh8nTLZ2SZTC0UFQLkS9Wwoh8_fdxZaiziYRNdKl5ezpf2RWCu7U2zxs7Q9ePUrArHuCM5rwliQffN5Yhi4Nzej9-jFgbNar5GYnapq5SZYxjFVYQ03_DaE_JbwU4ZQbRPiBTLZ2SZtHgubIREQaF0txQsADBRENmPL25cEBxVFUm3Gm0AeTjCqDVjqrBOB-SoxSij9TBlAg; acw_tc=707c9f7817727902052561870ed71077b5e4a74a7a88a41b593497338f502f; .thumbcache_33f5730e7694fd15728921e201b4826a=wlwllWSB9En7vQLhxzRdnrFoqXCayUGgKWt9YVZIEraZZxaz5N7+x54eJkzrxChLqyOPypHQxqvqFYWECeud+w%3D%3D"
}

# ==================== 核心工具函数 ====================
def load_status():
    """加载已推送状态（增加字段兼容逻辑）"""
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            status = json.load(f)
            # 兼容旧的user_id字段 → 新的user_euid字段
            for user_config in status.get("user_configs", []):
                if "user_id" in user_config and "user_euid" not in user_config:
                    user_config["user_euid"] = user_config.pop("user_id")
            return status
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "pushed_items": {},  # 格式：{user_euid: {pid: 1}}
            "user_configs": MONITOR_USERS
        }

def save_status(status):
    """保存推送状态到文件"""
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
        print(f"✅ 状态文件已保存：{STATUS_FILE}")
    except Exception as e:
        print(f"❌ 保存状态失败：{str(e)}")

def send_bark_notification(title, content):
    """Bark推送（自动截断超长内容）"""
    if not BARK_KEY:
        print("⚠️ Bark Key未配置，跳过推送")
        return False
    
    content = content[:800] + "..." if len(content) > 800 else content
    try:
        resp = requests.get(
            url=f"https://api.day.app/{BARK_KEY}/{title}/{content}",
            params={"isArchive": 1},
            timeout=10
        )
        resp.raise_for_status()
        print(f"✅ Bark推送成功：{title}")
        return True
    except Exception as e:
        print(f"❌ Bark推送失败：{str(e)}")
        return False

def extract_json_from_html(html):
    """从HTML中提取包含replies的JSON数据（核心！）"""
    # 匹配包含replies的JSON块（虎扑把数据嵌在script标签里）
    json_pattern = r'window\.bbs_thread_info\s*=\s*({.*?});'
    match = re.search(json_pattern, html, re.DOTALL)
    
    if not match:
        print("❌ 未找到包含replies的JSON数据")
        return None
    
    try:
        json_data = json.loads(match.group(1))
        # 提取核心的replies数据
        replies = json_data.get("replies", {})
        if not replies or "list" not in replies:
            print("❌ JSON中无有效replies数据")
            return None
        print(f"✅ 成功提取JSON：replies.count={replies.get('count', 0)}, total_page={replies.get('total', 0)}")
        return replies
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析失败：{str(e)}")
        return None

def fetch_hupu_replies(user_euid, thread_id, page_num):
    """爬取页面并提取replies数据"""
    # 构造请求URL（和你抓包一致）
    url = f"https://bbs.hupu.com/{thread_id}_{user_euid}-{page_num}.html"
    print(f"\n📡 请求URL：{url}")
    
    try:
        resp = requests.get(
            url=url,
            headers=REQUEST_HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True
        )
        resp.raise_for_status()
        resp.encoding = "utf-8"
        
        # 从HTML中提取JSON格式的replies数据
        replies = extract_json_from_html(resp.text)
        return replies
    except requests.exceptions.RequestException as e:
        print(f"❌ 爬取失败：{str(e)}")
        return None

def parse_replies(replies, target_euid):
    """解析replies.list，提取目标euid的回复"""
    if not replies:
        return []
    
    valid_replies = []
    reply_list = replies.get("list", [])
    print(f"\n🔍 解析replies.list：共{len(reply_list)}条回复，匹配euid={target_euid}")
    
    for item in reply_list:
        try:
            # 核心：通过author.euid匹配目标用户
            author = item.get("author", {})
            euid = author.get("euid", "")
            if euid != target_euid:
                continue
            
            # 提取关键信息
            pid = item.get("pid", "")  # 唯一标识，避免重复推送
            content = item.get("content", "")
            # 清理content中的HTML标签（如<p>、<img>）
            content = re.sub(r'<.*?>', '', content)
            create_time = item.get("createdAtFormat", "未知时间")
            username = author.get("puname", "未知用户")
            location = item.get("location", "未知地点")
            
            if not pid or not content:
                continue
            
            # 构造结构化数据
            valid_replies.append({
                "pid": pid,
                "euid": euid,
                "username": username,
                "time": create_time,
                "location": location,
                "content": content.strip()
            })
            
            # 打印解析结果（调试用）
            print(f"\n--- 匹配到目标回复 [pid={pid}] ---")
            print(f"用户：{username} ({euid})")
            print(f"时间：{create_time} | 地点：{location}")
            print(f"内容：{content[:100]}..." if len(content) > 100 else content)
        except Exception as e:
            print(f"❌ 解析单条回复失败：{str(e)}")
            continue
    
    print(f"\n✅ 解析完成：目标用户有效回复数 = {len(valid_replies)}")
    return valid_replies

def monitor_single_user(user_config, status):
    """监控单个用户的回复"""
    # 兼容旧字段：优先取user_euid，没有则取user_id
    target_euid = user_config.get("user_euid") or user_config.get("user_id", "")
    thread_id = user_config["thread_id"]
    current_page = user_config["current_page"]
    is_first_run = user_config["is_first_run"]
    
    if not target_euid:
        print(f"❌ 用户配置缺少euid，跳过监控")
        return
    
    # 加载已推送的pid
    pushed_pids = status["pushed_items"].get(target_euid, {})
    print(f"\n=====================================")
    print(f"监控用户：{target_euid} | 帖子：{thread_id}")
    print(f"当前页码：{current_page} | 首次运行：{is_first_run}")
    print(f"已推送回复数：{len(pushed_pids)}")
    print(f"=====================================")
    
    # 页码超限检查
    if current_page > MAX_PAGE_LIMIT:
        print(f"⚠️ 页码[{current_page}]超过最大值[{MAX_PAGE_LIMIT}]，停止翻页")
        return
    
    # 1. 爬取并提取replies数据
    replies = fetch_hupu_replies(target_euid, thread_id, current_page)
    if not replies:
        print(f"⚠️ 未获取到replies数据，页码保持不变")
        return
    
    # 2. 解析目标用户的回复
    valid_replies = parse_replies(replies, target_euid)
    
    # 3. 页码递增逻辑（无目标回复且有更多页时递增）
    total_pages = replies.get("total", 0)
    reply_list_len = len(replies.get("list", []))
    increment_page = False
    
    if len(valid_replies) == 0 and reply_list_len > 0 and current_page < total_pages and current_page < MAX_PAGE_LIMIT:
        increment_page = True
        user_config["current_page"] = current_page + 1
        print(f"📄 无目标回复，页码+1（{current_page} → {user_config['current_page']}）")
    else:
        print(f"📄 有目标回复/无更多数据，页码保持{current_page}")
    
    # 4. 筛选未推送的新回复
    new_replies = [r for r in valid_replies if r["pid"] not in pushed_pids]
    print(f"\n🔔 未推送的新回复数：{len(new_replies)}")
    
    # 5. 推送新回复
    if new_replies:
        # 首次运行只推送最新3条
        if is_first_run:
            new_replies = new_replies[-FIRST_RUN_LIMIT:]
            user_config["is_first_run"] = False
            print(f"🎉 首次运行，仅推送最新{FIRST_RUN_LIMIT}条回复")
        
        # 逐条推送
        for reply in new_replies:
            title = f"虎扑监控 | {reply['username']} | 回复{reply['pid']}"
            content = (
                f"时间：{reply['time']}\n"
                f"地点：{reply['location']}\n"
                f"内容：{reply['content']}"
            )
            send_bark_notification(title, content)
            # 标记为已推送
            pushed_pids[reply["pid"]] = 1
            time.sleep(1)  # 避免推送过快
    
    # 更新状态
    status["pushed_items"][target_euid] = pushed_pids

# ==================== 主函数 ====================
def main():
    """程序入口"""
    print(f"\n🚀 虎扑回复监控启动 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 加载状态
    status = load_status()
    
    # 遍历监控所有用户
    for user_config in status["user_configs"]:
        monitor_single_user(user_config, status)
    
    # 保存最新状态
    save_status(status)
    
    print(f"\n🛑 监控结束 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
