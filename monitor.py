import re
import time
import os
from datetime import datetime
from playwright.sync_api import sync_playwright

# ==================== 仅保留必要配置 ====================
TIMEOUT = 20
# 监控用户（仅用于生成URL）
MONITOR_USERS = [
    {
        "user_id": "20829162237257",
        "thread_id": "636748637",
        "current_page": 21,
        "is_first_run": True
    }
]

# ==================== 核心：加载页面并打印完整HTML ====================
def fetch_and_print_full_html(user_id, thread_id, page_num):
    """加载页面并打印完整的HTML内容（无截断）"""
    url = f"https://bbs.hupu.com/{thread_id}_{user_id}-{page_num}.html"
    print(f"\n=====================================")
    print(f"加载URL：{url}")
    print(f"=====================================\n")
    
    with sync_playwright() as p:
        # 启动浏览器（保持反爬配置，确保页面正常加载）
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
            }
        )
        
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page = context.new_page()
        full_html = ""
        
        try:
            # 加载页面
            page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT * 1000)
            page.wait_for_timeout(8000)  # 延长等待
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(3000)
            
            # 获取完整HTML
            # 替换原有的 full_html = page.content()
            # 改为：提取<body>标签的实时innerHTML（和浏览器Elements面板一致）
            full_html = page.evaluate("() => document.body.innerHTML")
            # 补充：也可以提取整个document的实时HTML
            # full_html = page.evaluate("() => document.documentElement.outerHTML")
            print(f"✅ 页面加载完成，总字符数：{len(full_html)}")
            print(f"\n=====================================")
            print(f"完整HTML内容开始（无截断）：")
            print(f"=====================================\n")
            # 打印完整HTML（无任何截断）
            print(full_html)
            
        except Exception as e:
            print(f"❌ 页面加载失败：{str(e)}")
        finally:
            browser.close()
    
    return full_html

# ==================== 主函数 ====================
def main():
    print(f"🚀 虎扑页面完整内容打印工具 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 自动安装依赖
    try:
        import playwright
    except ImportError:
        print("📦 安装Playwright依赖...")
        import subprocess
        subprocess.check_call(["pip", "install", "playwright"])
        subprocess.check_call(["playwright", "install", "chromium"])
    
    # 加载并打印第一个用户的页面
    target_user = MONITOR_USERS[0]
    fetch_and_print_full_html(
        user_id=target_user["user_id"],
        thread_id=target_user["thread_id"],
        page_num=target_user["current_page"]
    )
    
    print(f"\n🛑 打印完成 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
