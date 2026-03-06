import json
import re
import time
import os
from datetime import datetime
from playwright.sync_api import sync_playwright

# ==================== 全局配置项（可根据需求修改） ====================
# Bark推送密钥（从GitHub Actions Secrets读取，本地测试可直接填写）
BARK_KEY = os.getenv("BARK_KEY", "")
# 页面加载超时时间（秒）
TIMEOUT = 20
# 首次运行推送最新条数
FIRST_RUN_LIMIT = 3
# 最大页数限制（避免无限递增）
MAX_PAGE_LIMIT = 50
# 状态文件路径（仓库根目录）
STATUS_FILE = "hupu_status.json"

# 监控用户列表（可添加多个）
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
    """加载状态文件（记录已推送的楼层）"""
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # 首次运行初始化状态
        return {
            "pushed_items": {},  # 格式：{user_id: {floor_id: 1}}
            "user_configs": MONITOR_USERS
        }

def save_status(status):
    """保存状态文件到仓库"""
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
        print(f"✅ 状态文件已保存到：{STATUS_FILE}")
    except Exception as e:
        print(f"❌ 保存状态文件失败：{str(e)}")

def send_bark_notification(title, content):
    """通过Bark推送通知（内容过长自动截断）"""
    if not BARK_KEY:
        print("⚠️ Bark Key未配置，跳过推送")
        return False
    
    # Bark内容长度限制，截断超长内容
    if len(content) > 500:
        content = content[:500] + "..."
    
    try:
        import requests
        response = requests.get(
            url=f"https://api.day.app/{BARK_KEY}/{title}/{content}",
            params={"isArchive": 1},  # 保存到Bark历史
            timeout=10
        )
        response.raise_for_status()
        print(f"✅ Bark推送成功：{title}")
        return True
    except Exception as e:
        print(f"❌ Bark推送失败：{str(e)}")
        return False

def fetch_hupu_dynamic_page(user_id, thread_id, page_num):
    """
    使用Playwright模拟浏览器加载虎扑动态页面
    绕过反爬检测，获取完整的页面内容
    """
    url = f"https://bbs.hupu.com/{thread_id}_{user_id}-{page_num}.html"
    print(f"\n📡 开始加载动态页面：{url}")
    
    with sync_playwright() as p:
        # 启动Chrome浏览器，配置反爬参数
        browser = p.chromium.launch(
            headless=True,  # 无头模式（无界面）
            args=[
                "--disable-blink-features=AutomationControlled",  # 禁用自动化检测
                "--no-sandbox",  # 解决Ubuntu权限问题
                "--disable-dev-shm-usage",  # 解决内存不足问题
                "--disable-web-security",  # 放宽跨域限制
                "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ]
        )
        
        # 创建浏览器上下文，伪装真实环境
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},  # 模拟桌面分辨率
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": "https://bbs.hupu.com/stock",  # 股票区Referer
                "Cookie": "HUPU_SID=hupu; _clck=123456789; _clsk=abcdefg; HUPU_UID=123456789"  # 通用Cookie（可选替换为自己的）
            },
            locale="zh-CN",
            timezone_id="Asia/Shanghai"
        )
        
        # 隐藏webdriver标识（关键反爬）
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        """)
        
        page = context.new_page()
        html_content = None
        
        try:
            # 加载页面（仅等待DOM加载完成，不等待网络空闲）
            page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT * 1000)
            
            # 强制等待+滚动页面，触发动态内容加载
            page.wait_for_timeout(5000)  # 等待5秒
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")  # 滚动到底部
            page.wait_for_timeout(2000)  # 滚动后再等2秒
            
            # 获取完整的页面HTML
            html_content = page.content()
            html_length = len(html_content) if html_content else 0
            print(f"✅ 动态页面加载完成，HTML总长度：{html_length} 字符")
            
            # 打印HTML预览（前1000字符，方便调试）
            if html_content:
                print(f"🔍 HTML预览（前1000字符）：\n{html_content[:1000]}...")
                
        except Exception as e:
            print(f"❌ 动态页面加载超时/失败：{str(e)}")
            # 即使超时，尝试获取已加载的内容
            try:
                html_content = page.content()
                print(f"⚠️ 超时后获取到的HTML长度：{len(html_content)} 字符")
            except:
                html_content = None
        finally:
            # 确保浏览器关闭
            browser.close()
    
    return html_content

def parse_hupu_floor_data(html, target_user_id):
    """
    解析虎扑页面中的楼层数据
    从window.__INITIAL_STATE__中提取结构化数据，适配新版页面
    """
    print(f"\n🔍 开始解析目标用户 [{target_user_id}] 的楼层数据")
    valid_floors = []
    
    if not html or len(html) < 1000:
        print("❌ 页面内容无效（过短/为空），跳过解析")
        return valid_floors
    
    # ========== 第一步：提取window.__INITIAL_STATE__ ==========
    init_state_pattern = re.compile(
        r'window\.__INITIAL_STATE__\s*=\s*({.*?});\s*</script>',
        re.DOTALL | re.IGNORECASE
    )
    init_state_match = init_state_pattern.search(html)
    
    if not init_state_match:
        print("❌ 未找到window.__INITIAL_STATE__（核心数据入口）")
        # 调试：打印页面中所有包含pid/uid的片段
        pid_uid_matches = re.findall(r'"pid":\d+|"uid":\d+|"floorId":\d+|"userId":\d+', html)
        print(f"🔍 页面中找到的pid/uid片段（前10个）：{pid_uid_matches[:10]}")
        return valid_floors
    
    # ========== 第二步：解析INITIAL_STATE JSON ==========
    try:
        init_state = json.loads(init_state_match.group(1))
        print(f"✅ 成功解析INITIAL_STATE，顶级键：{list(init_state.keys())}")
    except json.JSONDecodeError as e:
        print(f"❌ 解析INITIAL_STATE失败：{str(e)}")
        return valid_floors
    
    # ========== 第三步：提取楼层数据（适配多种路径） ==========
    posts = []
    # 路径1：thread -> postList
    if "thread" in init_state and isinstance(init_state["thread"], dict):
        posts = init_state["thread"].get("postList", []) or init_state["thread"].get("posts", [])
    # 路径2：直接顶级posts
    elif "posts" in init_state and isinstance(init_state["posts"], list):
        posts = init_state["posts"]
    # 路径3：data -> thread -> posts
    elif "data" in init_state and isinstance(init_state["data"], dict):
        thread_data = init_state["data"].get("thread", {})
        posts = thread_data.get("postList", []) or thread_data.get("posts", [])
    
    print(f"🔢 从INITIAL_STATE中提取到总楼层数：{len(posts)}")
    
    # 调试：打印前2条楼层数据结构
    if len(posts) > 0:
        print(f"🔍 前2条楼层数据示例：\n{json.dumps(posts[:2], ensure_ascii=False, indent=2)}")
    
    # ========== 第四步：筛选目标用户的有效楼层 ==========
    floor_id_set = set()  # 去重（避免重复楼层）
    for floor in posts:
        try:
            # 适配多种字段名（兼容新版/旧版）
            floor_id = str(floor.get("pid", floor.get("floorId", "")))
            author_info = floor.get("author", {}) if isinstance(floor.get("author"), dict) else {}
            user_id = str(author_info.get("uid", author_info.get("userId", "")))
            username = author_info.get("username", "未知用户")
            content = floor.get("content", "").strip()
            create_time = floor.get("createTime", floor.get("publishTime", "未知时间"))
            
            # 过滤无效数据
            if not floor_id or not user_id or not content or floor_id in floor_id_set:
                continue
            
            # 标记已处理的楼层ID（去重）
            floor_id_set.add(floor_id)
            
            # 打印楼层详情
            print(f"\n--- 楼层 [{floor_id}] 详情 ---")
            print(f"用户ID：{user_id}（用户名：{username}）")
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
    """监控单个用户的指定帖子页数"""
    user_id = user_config["user_id"]
    thread_id = user_config["thread_id"]
    current_page = user_config["current_page"]
    is_first_run = user_config["is_first_run"]
    
    # 基础信息打印
    pushed_floors = status["pushed_items"].get(user_id, {})
    print(f"\n=====================================")
    print(f"开始监控用户：{user_id}")
    print(f"帖子ID：{thread_id} | 当前页数：{current_page}")
    print(f"首次运行：{is_first_run} | 已推送楼层数：{len(pushed_floors)}")
    print(f"=====================================")
    
    # 页数超限检查
    if current_page > MAX_PAGE_LIMIT:
        print(f"⚠️ 当前页数 [{current_page}] 超过最大值 [{MAX_PAGE_LIMIT}]，停止递增")
        return
    
    # 1. 加载动态页面
    html_content = fetch_hupu_dynamic_page(user_id, thread_id, current_page)
    if not html_content:
        print(f"⚠️ 页面加载失败，页数保持不变")
        return
    
    # 2. 解析楼层数据
    valid_floors = parse_hupu_floor_data(html_content, user_id)
    
    # 3. 筛选未推送的新楼层
    new_floors = [floor for floor in valid_floors if floor["floor_id"] not in pushed_floors]
    print(f"\n🔔 未推送的新楼层数：{len(new_floors)}")
    
    # 4. 页数递增逻辑（仅在有楼层但无目标用户内容时递增）
    total_floors = len(re.findall(r'"pid":\d+', html_content))  # 页面总楼层数
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
            print(f"🎉 首次运行，仅推送最新{FIRST_RUN_LIMIT}条内容")
        
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
    print(f"\n🚀 虎扑帖子监控程序启动 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 安装依赖（自动检测+安装）
    try:
        import playwright
        import requests
    except ImportError:
        print("📦 检测到依赖缺失，开始自动安装...")
        import subprocess
        subprocess.check_call(["pip", "install", "playwright", "requests"])
        subprocess.check_call(["playwright", "install", "chromium"])
        print("✅ 依赖安装完成")
    
    # 加载监控状态
    monitor_status = load_status()
    
    # 遍历监控所有用户
    for user_config in monitor_status["user_configs"]:
        monitor_single_user(user_config, monitor_status)
    
    # 保存最新状态
    save_status(monitor_status)
    
    print(f"\n🛑 监控程序结束 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
