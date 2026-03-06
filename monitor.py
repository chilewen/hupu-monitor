import json
import re
import time
import os
from datetime import datetime
from playwright.sync_api import sync_playwright

# ==================== 全局配置项 ====================
BARK_KEY = os.getenv("BARK_KEY", "")
TIMEOUT = 20
FIRST_RUN_LIMIT = 3
MAX_PAGE_LIMIT = 50
STATUS_FILE = "hupu_status.json"

# 监控用户列表
MONITOR_USERS = [
    {
        "user_id": "20829162237257",
        "thread_id": "636748637",
        "current_page": 22,
        "is_first_run": True
    },
    {
        "user_id": "197319743786161",
        "thread_id": "636748637",
        "current_page": 1,
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

def send_bark_notification(title, content):
    if not BARK_KEY:
        print("⚠️ Bark Key未配置，跳过推送")
        return False
    
    if len(content) > 500:
        content = content[:500] + "..."
    
    try:
        import requests
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

def fetch_hupu_dynamic_page(user_id, thread_id, page_num):
    """加载动态页面，延长等待时间确保数据加载"""
    url = f"https://bbs.hupu.com/{thread_id}_{user_id}-{page_num}.html"
    print(f"\n📡 开始加载动态页面：{url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ]
        )
        
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://bbs.hupu.com/stock",
                "Cookie": "HUPU_SID=hupu; _clck=123456789; _clsk=abcdefg; HUPU_UID=123456789"
            },
            locale="zh-CN",
            timezone_id="Asia/Shanghai"
        )
        
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page = context.new_page()
        html_content = None
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT * 1000)
            # 延长等待时间，确保动态数据完全加载
            page.wait_for_timeout(8000)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(3000)
            
            html_content = page.content()
            html_length = len(html_content) if html_content else 0
            print(f"✅ 动态页面加载完成，HTML总长度：{html_length} 字符")
            
        except Exception as e:
            print(f"❌ 页面加载失败：{str(e)}")
            try:
                html_content = page.content()
                print(f"⚠️ 超时后获取到的HTML长度：{len(html_content)} 字符")
            except:
                html_content = None
        finally:
            browser.close()
    
    return html_content

def parse_hupu_floor_data(html, target_user_id):
    """终极解析方案：全量扫描页面找楼层数据，不依赖__INITIAL_STATE__"""
    print(f"\n🔍 开始解析目标用户 [{target_user_id}] 的楼层数据")
    valid_floors = []
    
    if not html or len(html) < 1000:
        print("❌ 页面内容无效，跳过解析")
        return valid_floors

    # ========== 方案1：全量扫描所有可能的楼层数据格式 ==========
    # 匹配规则：兼容pid/uid/content/time的任意组合，支持单引号/双引号/无引号
    floor_patterns = [
        # 格式1: "pid":123,"uid":456,"content":"xxx","createTime":"2024-01-01"
        re.compile(r'"pid":(\d+).*?"uid":(\d+).*?"content":"(.*?)".*?"createTime":"(.*?)"', re.DOTALL),
        # 格式2: 'pid':123,'uid':456,'content':'xxx','createTime':'2024-01-01'
        re.compile(r"'pid':(\d+).*?'uid':(\d+).*?'content':'(.*?)'.*?'createTime':'(.*?)'", re.DOTALL),
        # 格式3: pid:123,uid:456,content:"xxx",publishTime:"2024-01-01"
        re.compile(r'pid:(\d+).*?uid:(\d+).*?content:"(.*?)".*?publishTime:"(.*?)"', re.DOTALL),
        # 格式4: "floorId":123,"userId":456,"content":"xxx","publishTime":"2024-01-01"
        re.compile(r'"floorId":(\d+).*?"userId":(\d+).*?"content":"(.*?)".*?"publishTime":"(.*?)"', re.DOTALL),
        # 格式5: floorId:123,userId:456,content:'xxx',createTime:'2024-01-01'
        re.compile(r'floorId:(\d+).*?userId:(\d+).*?content:\'(.*?)\'.*?createTime:\'(.*?)\'', re.DOTALL)
    ]

    # 收集所有匹配结果
    all_matches = []
    for pattern in floor_patterns:
        matches = pattern.findall(html)
        if matches:
            print(f"✅ 匹配规则{floor_patterns.index(pattern)+1}找到 {len(matches)} 条数据")
            all_matches.extend(matches)

    if not all_matches:
        print("❌ 未匹配到任何楼层数据")
        # 调试：打印页面中所有包含数字ID的片段
        id_matches = re.findall(r'(\d{8,15})', html)  # 匹配8位以上的数字（用户ID/楼层ID）
        print(f"🔍 页面中找到的长数字ID（前20个）：{list(set(id_matches))[:20]}")
        return valid_floors

    # ========== 去重并筛选目标用户 ==========
    floor_id_set = set()
    for match in all_matches:
        try:
            floor_id = match[0].strip()
            user_id = match[1].strip()
            content = match[2].strip().replace(r'\n', '\n').replace(r'\u003e', '>').replace(r'\u003c', '<').replace(r'\\"', '"')
            create_time = match[3].strip() if len(match)>=4 else "未知时间"

            # 过滤无效数据
            if not floor_id or not user_id or not content or floor_id in floor_id_set:
                continue
            floor_id_set.add(floor_id)

            # 打印楼层详情
            print(f"\n--- 楼层 [{floor_id}] 详情 ---")
            print(f"用户ID：{user_id}")
            print(f"发布时间：{create_time}")
            print(f"内容：{content[:200]}..." if len(content) > 200 else content)
            print(f"是否目标用户：{user_id == target_user_id}")

            # 筛选目标用户
            if user_id == target_user_id:
                valid_floors.append({
                    "floor_id": floor_id,
                    "user_id": user_id,
                    "time": create_time,
                    "content": content
                })
        except Exception as e:
            print(f"❌ 解析单条楼层失败：{str(e)}")
            continue

    print(f"\n✅ 解析完成：目标用户有效楼层数 = {len(valid_floors)}")
    return valid_floors

def monitor_single_user(user_config, status):
    user_id = user_config["user_id"]
    thread_id = user_config["thread_id"]
    current_page = user_config["current_page"]
    is_first_run = user_config["is_first_run"]
    
    pushed_floors = status["pushed_items"].get(user_id, {})
    print(f"\n=====================================")
    print(f"开始监控用户：{user_id}")
    print(f"帖子ID：{thread_id} | 当前页数：{current_page}")
    print(f"首次运行：{is_first_run} | 已推送楼层数：{len(pushed_floors)}")
    print(f"=====================================")
    
    if current_page > MAX_PAGE_LIMIT:
        print(f"⚠️ 当前页数超过最大值，停止递增")
        return
    
    # 加载页面
    html_content = fetch_hupu_dynamic_page(user_id, thread_id, current_page)
    if not html_content:
        print(f"⚠️ 页面加载失败，页数保持不变")
        return
    
    # 解析楼层
    valid_floors = parse_hupu_floor_data(html_content, user_id)
    
    # 筛选新楼层
    new_floors = [floor for floor in valid_floors if floor["floor_id"] not in pushed_floors]
    print(f"\n🔔 未推送的新楼层数：{len(new_floors)}")
    
    # 页数递增逻辑
    total_floors = len(set([m[0] for m in all_matches])) if 'all_matches' in locals() else 0
    increment_page = False
    if len(valid_floors) == 0 and total_floors > 0 and current_page < MAX_PAGE_LIMIT:
        increment_page = True
        print(f"📄 页数+1（{current_page} → {current_page+1}）")
        user_config["current_page"] = current_page + 1
    else:
        print(f"📄 页数保持不变")
    
    # 推送新内容
    if new_floors:
        if is_first_run:
            new_floors = new_floors[-FIRST_RUN_LIMIT:]
            user_config["is_first_run"] = False
            print(f"🎉 首次运行，推送最新{FIRST_RUN_LIMIT}条")
        
        for floor in new_floors:
            title = f"虎扑监控 | {user_id} | 楼层{floor['floor_id']}"
            content = f"时间：{floor['time']}\n内容：{floor['content']}"
            send_bark_notification(title, content)
            pushed_floors[floor["floor_id"]] = 1
            time.sleep(1)
    
    status["pushed_items"][user_id] = pushed_floors

# ==================== 主函数 ====================
def main():
    print(f"\n🚀 虎扑帖子监控启动 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 安装依赖
    try:
        import playwright
        import requests
    except ImportError:
        print("📦 安装依赖...")
        import subprocess
        subprocess.check_call(["pip", "install", "playwright", "requests"])
        subprocess.check_call(["playwright", "install", "chromium"])
    
    # 加载状态
    monitor_status = load_status()
    
    # 监控用户
    for user_config in monitor_status["user_configs"]:
        monitor_single_user(user_config, monitor_status)
    
    # 保存状态
    save_status(monitor_status)
    
    print(f"\n🛑 监控结束 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
