import json
import re
import time
import os
from datetime import datetime
from playwright.sync_api import sync_playwright  # 模拟浏览器

# ==================== 配置项 ====================
BARK_KEY = os.getenv("BARK_KEY", "")
TIMEOUT = 30  # 浏览器加载超时时间
FIRST_RUN_LIMIT = 3
MAX_PAGE_LIMIT = 50
STATUS_FILE = "hupu_status.json"  # 相对路径（Action中已确认工作目录）

# 监控用户
MONITOR_USERS = [
    {
        "user_id": "20829162237257",
        "thread_id": "636748637",
        "current_page": 22,
        "is_first_run": True
    }
]

# ==================== 工具函数 ====================
def load_status():
    """加载状态文件"""
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"pushed_items": {}, "user_configs": MONITOR_USERS}

def save_status(status):
    """保存状态文件"""
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
        print(f"✅ 状态文件已保存")
    except Exception as e:
        print(f"❌ 保存状态文件失败：{str(e)}")

def send_bark(title, content):
    """Bark推送"""
    if not BARK_KEY:
        print("⚠️ Bark Key未配置，跳过推送")
        return
    
    # 内容截断（Bark长度限制）
    content = content[:500] + "..." if len(content) > 500 else content
    
    try:
        import requests
        res = requests.get(
            f"https://api.day.app/{BARK_KEY}/{title}/{content}",
            params={"isArchive": 1},
            timeout=10
        )
        res.raise_for_status()
        print(f"✅ Bark推送成功：{title}")
    except Exception as e:
        print(f"❌ Bark推送失败：{str(e)}")

def fetch_hupu_dynamic_page(user_id, thread_id, page):
    """使用Playwright模拟浏览器加载完整页面"""
    url = f"https://bbs.hupu.com/{thread_id}_{user_id}-{page}.html"
    print(f"\n📡 加载动态页面：{url}")
    
    # 初始化Playwright
    with sync_playwright() as p:
        # 启动无头浏览器（无界面）
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://bbs.hupu.com/stock"
            }
        )
        
        page = context.new_page()
        try:
            # 加载页面（等待网络空闲）
            page.goto(url, wait_until="networkidle", timeout=TIMEOUT*1000)
            # 等待楼层元素加载（虎扑楼层容器class）
            page.wait_for_selector(".floor-list", timeout=TIMEOUT*1000)
            # 获取完整的页面HTML（包含动态加载的内容）
            html = page.content()
            print(f"✅ 动态页面加载完成，长度：{len(html)}字符")
            return html
        except Exception as e:
            print(f"❌ 动态页面加载失败：{str(e)}")
            return None
        finally:
            # 关闭浏览器
            browser.close()

def parse_floor_content(html, target_user_id):
    """解析动态加载后的楼层内容"""
    print(f"\n🔍 解析目标用户 {target_user_id} 的楼层")
    items = []
    
    if not html:
        print("❌ 无页面内容可解析")
        return items
    
    # 正则匹配楼层数据（适配虎扑新版动态渲染的JSON）
    # 匹配包含pid、uid、content的核心数据
    floor_pattern = re.compile(
        r'"pid":(\d+).*?"uid":(\d+).*?"username":"(.*?)".*?"content":"(.*?)".*?"createTime":"(.*?)"',
        re.DOTALL  # 允许.匹配换行符
    )
    
    matches = floor_pattern.findall(html)
    print(f"🔢 匹配到总楼层数：{len(matches)}")
    
    # 去重（避免重复楼层）
    floor_ids = set()
    for match in matches:
        try:
            floor_id = match[0]
            user_id = match[1]
            username = match[2].replace(r'\u003e', '>').replace(r'\u003c', '<').replace(r'\\"', '"')
            content = match[3].replace(r'\u003e', '>').replace(r'\u003c', '<').replace(r'\\"', '"').strip()
            create_time = match[4]
            
            # 过滤空内容和重复楼层
            if not content or floor_id in floor_ids:
                continue
            floor_ids.add(floor_id)
            
            # 打印楼层详情
            print(f"\n--- 楼层 {floor_id} ---")
            print(f"用户ID：{user_id}（{username}）")
            print(f"时间：{create_time}")
            print(f"内容：{content[:200]}..." if len(content) > 200 else content)
            print(f"是否目标用户：{user_id == target_user_id}")
            
            # 筛选目标用户内容
            if user_id == target_user_id:
                items.append({
                    "floor_id": floor_id,
                    "time": create_time,
                    "content": content,
                    "user_id": user_id
                })
        except Exception as e:
            print(f"❌ 解析楼层失败：{str(e)}")
            continue
    
    print(f"\n✅ 解析完成：目标用户有效楼层数 = {len(items)}")
    return items

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
    
    # 1. 加载动态页面
    html = fetch_hupu_dynamic_page(user_id, thread_id, current_page)
    if not html:
        print(f"⚠️ 页面加载失败，不递增页数")
        return
    
    # 2. 解析楼层
    items = parse_floor_content(html, user_id)
    
    # 3. 筛选新内容
    new_items = [item for item in items if item["floor_id"] not in pushed_floors]
    print(f"\n🔔 未推送新内容数：{len(new_items)}")
    
    # 4. 页数递增逻辑
    total_matched = len(set([m[0] for m in re.findall(r'"pid":(\d+)', html)]))  # 总唯一楼层数
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
    
    # 安装依赖（Action中自动安装）
    try:
        import playwright
    except ImportError:
        print("📦 安装Playwright依赖...")
        import subprocess
        subprocess.check_call(["pip", "install", "playwright", "requests"])
        subprocess.check_call(["playwright", "install", "chromium"])  # 安装浏览器
    
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
