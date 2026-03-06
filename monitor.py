import json
import requests
import time
import os
import re
from datetime import datetime

# ==================== 配置项（直接写在脚本里，避免依赖config.py路径问题） ====================
BARK_KEY = os.getenv("BARK_KEY", "")  # 从Action Secrets读取
TIMEOUT = 15
FIRST_RUN_LIMIT = 3
MAX_PAGE_LIMIT = 50
STATUS_FILE = "/home/runner/work/hupu-monitor/hupu-monitor/hupu_status.json"  # Action绝对路径
# 监控用户
MONITOR_USERS = [
    {
        "user_id": "20829162237257",
        "thread_id": "636748637",
        "current_page": 22,
        "is_first_run": True
    }
]

# ==================== 核心配置 ====================
# 强化请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://bbs.hupu.com/stock",
    "Cookie": "HUPU_SID=hupu; _clck=123456789; _clsk=abcdefg;",
    "Upgrade-Insecure-Requests": "1"
}

# 虎扑楼层解析正则（适配新版页面）
FLOOR_PATTERN = re.compile(r'"pid":(\d+),"uid":"?(\d+)"?,"username":"(.*?)","content":"(.*?)","createTime":"(.*?)"')

# ==================== 工具函数 ====================
def load_status():
    """加载状态文件"""
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"pushed_items": {}, "user_configs": MONITOR_USERS}

def save_status(status):
    """保存状态文件"""
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
        print(f"✅ 状态文件已保存到：{STATUS_FILE}")
    except Exception as e:
        print(f"❌ 保存状态文件失败：{str(e)}")

def print_debug_info(title, content):
    """打印调试信息（替代文件保存，适配Action）"""
    print(f"\n========== {title} ==========")
    # 内容过长时截断（避免日志溢出）
    if len(str(content)) > 3000:
        print(str(content)[:3000] + "\n...（内容过长，已截断）")
    else:
        print(content)
    print("=" * (len(title) + 20))

def fetch_hupu_page(user_id, thread_id, page):
    """爬取虎扑页面并打印完整内容到日志"""
    url = f"https://bbs.hupu.com/{thread_id}_{user_id}-{page}.html"
    print(f"\n📡 爬取URL：{url}")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        response.encoding = "utf-8"
        print(f"✅ 爬取成功，状态码：{response.status_code}")
        
        # 打印完整页面内容到日志（调试用）
        print_debug_info(f"页面完整内容（{user_id}-page{page}）", response.text)
        
        return response.text
    except Exception as e:
        print(f"❌ 爬取失败：{str(e)}")
        return None

def parse_floor_content(html, target_user_id):
    """解析楼层内容"""
    print(f"\n🔍 开始解析目标用户{target_user_id}的楼层")
    items = []
    
    if not html:
        print("❌ 无页面内容")
        return items
    
    # 正则匹配所有楼层
    matches = FLOOR_PATTERN.findall(html)
    print(f"🔢 正则匹配到总楼层数：{len(matches)}")
    
    # 遍历匹配结果
    for idx, match in enumerate(matches):
        try:
            floor_id = match[0]
            user_id = match[1].strip('"')  # 兼容带引号的user_id
            username = match[2].replace(r'\u003e', '>').replace(r'\u003c', '<').replace(r'\\"', '"')
            content = match[3].replace(r'\u003e', '>').replace(r'\u003c', '<').replace(r'\\"', '"').strip()
            create_time = match[4]
            
            # 打印每一层的详细信息
            print(f"\n--- 楼层 {idx+1} ---")
            print(f"楼层ID：{floor_id}")
            print(f"用户ID：{user_id}（用户名：{username}）")
            print(f"发布时间：{create_time}")
            print(f"内容：{content[:200]}..." if len(content) > 200 else f"内容：{content}")
            print(f"是否目标用户：{user_id == target_user_id}")
            
            # 筛选目标用户的内容
            if user_id == target_user_id and content:
                items.append({
                    "floor_id": floor_id,
                    "time": create_time,
                    "content": content,
                    "user_id": user_id
                })
        except Exception as e:
            print(f"❌ 解析楼层{idx+1}失败：{str(e)}")
            continue
    
    print(f"\n✅ 解析完成：目标用户有效楼层数 = {len(items)}")
    return items

def send_bark(title, content):
    """Bark推送"""
    if not BARK_KEY:
        print("⚠️ Bark Key未配置，跳过推送")
        return
    
    # 内容截断
    content = content[:500] + "..." if len(content) > 500 else content
    
    try:
        res = requests.get(
            f"https://api.day.app/{BARK_KEY}/{title}/{content}",
            params={"isArchive": 1},
            timeout=TIMEOUT
        )
        res.raise_for_status()
        print(f"✅ Bark推送成功")
    except Exception as e:
        print(f"❌ Bark推送失败：{str(e)}")

# ==================== 主逻辑 ====================
def monitor_user(user_config, status):
    """监控单个用户"""
    user_id = user_config["user_id"]
    thread_id = user_config["thread_id"]
    current_page = user_config["current_page"]
    is_first_run = user_config["is_first_run"]
    
    # 基础信息
    pushed_floors = status["pushed_items"].get(user_id, {})
    print(f"\n=====================================")
    print(f"监控用户：{user_id}")
    print(f"当前页数：{current_page} | 首次运行：{is_first_run}")
    print(f"已推送楼层：{list(pushed_floors.keys()) or ['无']}")
    print(f"=====================================")
    
    # 页数超限检查
    if current_page > MAX_PAGE_LIMIT:
        print(f"⚠️ 页数{current_page}超过最大值{MAX_PAGE_LIMIT}，停止递增")
        return
    
    # 1. 爬取页面
    html = fetch_hupu_page(user_id, thread_id, current_page)
    if not html:
        print(f"⚠️ 页面爬取失败，不递增页数")
        return
    
    # 2. 解析楼层
    items = parse_floor_content(html, user_id)
    
    # 3. 筛选新内容
    new_items = [item for item in items if item["floor_id"] not in pushed_floors]
    print(f"\n🔔 未推送新内容数：{len(new_items)}")
    
    # 4. 页数递增逻辑
    total_matched = len(FLOOR_PATTERN.findall(html))
    increment = False
    if len(items) == 0 and total_matched > 0 and current_page < MAX_PAGE_LIMIT:
        increment = True
        print(f"📄 有楼层但无目标用户内容，页数+1（{current_page}→{current_page+1}）")
        user_config["current_page"] += 1
    elif len(items) == 0 and total_matched == 0:
        print(f"📄 无任何楼层数据，不递增页数")
    else:
        print(f"📄 有目标用户内容，页数不变")
    
    # 5. 推送新内容
    if new_items:
        # 首次运行只推最新3条
        if is_first_run:
            new_items = new_items[-FIRST_RUN_LIMIT:]
            user_config["is_first_run"] = False
            print(f"🎉 首次运行，推送最新{FIRST_RUN_LIMIT}条")
        
        # 逐条推送
        for item in new_items:
            title = f"虎扑监控 | {user_id} | 楼层{item['floor_id']}"
            content = f"时间：{item['time']}\n内容：{item['content']}"
            send_bark(title, content)
            pushed_floors[item["floor_id"]] = 1
            time.sleep(1)  # 避免推送过快
    
    # 更新状态
    status["pushed_items"][user_id] = pushed_floors

def main():
    """主函数"""
    print(f"\n🚀 监控开始：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 加载状态
    status = load_status()
    
    # 监控所有用户
    for user_config in status["user_configs"]:
        monitor_user(user_config, status)
    
    # 保存状态
    save_status(status)
    
    print(f"\n🛑 监控结束：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
