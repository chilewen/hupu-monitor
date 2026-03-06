import json
import re
import time
import os
from datetime import datetime
from playwright.sync_api import sync_playwright

# ==================== 配置项 ====================
BARK_KEY = os.getenv("BARK_KEY", "")
TIMEOUT = 20  # 缩短超时时间（避免不必要等待）
FIRST_RUN_LIMIT = 3
MAX_PAGE_LIMIT = 50
STATUS_FILE = "hupu_status.json"

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
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"pushed_items": {}, "user_configs": MONITOR_USERS}

def save_status(status):
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
        print(f"✅ 状态文件已保存")
    except Exception as e:
        print(f"❌ 保存状态文件失败：{str(e)}")

def send_bark(title, content):
    if not BARK_KEY:
        print("⚠️ Bark Key未配置，跳过推送")
        return
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

def fetch_hupu_dynamic_page(user_id, thread_id, page_num):
    """修复版：绕过反爬 + 宽松的等待策略"""
    url = f"https://bbs.hupu.com/{thread_id}_{user_id}-{page_num}.html"
    print(f"\n📡 加载动态页面：{url}")
    
    with sync_playwright() as p:
        # 1. 绕过反爬：伪装成有头浏览器，禁用自动化特征
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",  # 禁用自动化检测
                "--no-sandbox",  # 解决Ubuntu权限问题
                "--disable-dev-shm-usage",
                "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ]
        )
        
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://bbs.hupu.com/",
                "Cookie": "HUPU_SID=123456; _clck=789012; HUPU_UID=123456789"  # 可选：替换为自己的虎扑Cookie
            },
            # 2. 隐藏自动化特征
            java_script_enabled=True,
            locale="zh-CN",
            timezone_id="Asia/Shanghai"
        )
        
        # 3. 进一步隐藏webdriver特征
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page = context.new_page()
        try:
            # 4. 宽松的加载策略：只等待页面基本加载，不等待网络空闲
            page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT*1000)
            # 5. 等待任意内容加载（放弃特定选择器，避免因class变化超时）
            page.wait_for_timeout(5000)  # 强制等待5秒，让动态内容加载
            # 6. 滚动页面（触发懒加载）
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)  # 滚动后再等2秒
            
            # 获取完整HTML
            html = page.content()
            print(f"✅ 动态页面加载完成，HTML长度：{len(html)} 字符")
            
            # 打印前1000字符调试
            print(f"🔍 HTML预览：{html[:1000]}...")
            return html
        except Exception as e:
            print(f"❌ 动态页面加载失败：{str(e)}")
            # 即使超时，也尝试获取已加载的HTML
            try:
                html = page.content()
                print(f"⚠️ 超时后获取到的HTML：{html[:500]}...")
                return html
            except:
                return None
        finally:
            browser.close()

def parse_floor_content(html, target_user_id):
    print(f"\n🔍 解析目标用户 {target_user_id} 的楼层")
    items = []
    if not html:
        print("❌ 无页面内容可解析")
        return items
    
    # 适配虎扑新版的楼层正则（兼容多种格式）
    floor_pattern = re.compile(
        r'(?:pid|floorId)["\']?:["\']?(\d+)["\']?,.*?(?:uid|userId)["\']?:["\']?(\d+)["\']?,.*?(?:content)["\']?:["\']?(.*?)["\']?,.*?(?:createTime|publishTime)["\']?:["\']?(.*?)["\']?',
        re.DOTALL | re.IGNORECASE
    )
    
    matches = floor_pattern.findall(html)
    print(f"🔢 匹配到总楼层数：{len(matches)}")
    
    floor_ids = set()
    for match in matches:
        try:
            floor_id = match[0].strip('"').strip("'")
            user_id = match[1].strip('"').strip("'")
            content = match[2].strip('"').strip("'").replace(r'\n', '\n').replace(r'\u003e', '>').replace(r'\u003c', '<')
            create_time = match[3].strip('"').strip("'") if len(match)>=4 else "未知时间"
            
            if not content or floor_id in floor_ids or user_id == "":
                continue
            floor_ids.add(floor_id)
            
            print(f"\n--- 楼层 {floor_id} ---")
            print(f"用户ID：{user_id}")
            print(f"时间：{create_time}")
            print(f"内容：{content[:200]}..." if len(content) > 200 else content)
            print(f"是否目标用户：{user_id == target_user_id}")
            
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

def monitor_user(user_config, status):
    user_id = user_config["user_id"]
    thread_id = user_config["thread_id"]
    current_page = user_config["current_page"]
    is_first_run = user_config["is_first_run"]
    
    pushed_floors = status["pushed_items"].get(user_id, {})
    print(f"\n=====================================")
    print(f"监控用户：{user_id}")
    print(f"当前页数：{current_page} | 首次运行：{is_first_run}")
    print(f"已推送楼层：{list(pushed_floors.keys()) or ['无']}")
    print(f"=====================================")
    
    if current_page > MAX_PAGE_LIMIT:
        print(f"⚠️ 页数{current_page}超过最大值{MAX_PAGE_LIMIT}，停止递增")
        return
    
    # 加载动态页面
    html = fetch_hupu_dynamic_page(user_id, thread_id, current_page)
    if not html or len(html) < 1000:  # 过滤空内容/短内容
        print(f"⚠️ 页面内容无效，不递增页数")
        return
    
    # 解析楼层
    items = parse_floor_content(html, user_id)
    
    # 筛选新内容
    new_items = [item for item in items if item["floor_id"] not in pushed_floors]
    print(f"\n🔔 未推送新内容数：{len(new_items)}")
    
    # 页数递增逻辑
    total_matched = len(floor_ids) if 'floor_ids' in locals() else 0
    increment = False
    if len(items) == 0 and total_matched > 0 and current_page < MAX_PAGE_LIMIT:
        increment = True
        print(f"📄 有楼层但无目标用户内容，页数+1（{current_page}→{current_page+1}）")
        user_config["current_page"] += 1
    elif len(items) == 0 and total_matched == 0:
        print(f"📄 无任何楼层数据，不递增页数")
    else:
        print(f"📄 有目标用户内容，页数不变")
    
    # 推送新内容
    if new_items:
        if is_first_run:
            new_items = new_items[-FIRST_RUN_LIMIT:]
            user_config["is_first_run"] = False
            print(f"🎉 首次运行，推送最新{FIRST_RUN_LIMIT}条")
        
        for item in new_items:
            title = f"虎扑监控 | {user_id} | 楼层{item['floor_id']}"
            content = f"时间：{item['time']}\n内容：{item['content']}"
            send_bark(title, content)
            pushed_floors[item["floor_id"]] = 1
            time.sleep(1)
    
    status["pushed_items"][user_id] = pushed_floors

def main():
    print(f"\n🚀 监控开始：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 安装依赖
    try:
        import playwright
    except ImportError:
        print("📦 安装Playwright依赖...")
        import subprocess
        subprocess.check_call(["pip", "install", "playwright", "requests"])
        subprocess.check_call(["playwright", "install", "chromium"])
    
    # 加载状态
    status = load_status()
    
    # 监控用户
    for user_config in status["user_configs"]:
        monitor_user(user_config, status)
    
    # 保存状态
    save_status(status)
    
    print(f"\n🛑 监控结束：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
