import json
import re
import time
import os
import requests
from datetime import datetime

# ==================== 全局配置 ====================
BARK_KEY = os.getenv("BARK_KEY", "")
TIMEOUT = 15
FIRST_RUN_LIMIT = 3
MAX_PAGE_LIMIT = 50
STATUS_FILE = "hupu_status.json"

# 监控用户列表
MONITOR_USERS = [
    {
        "user_euid": "20829162237257",
        "thread_id": "636748637",
        "current_page": 21,  # 当前请求的22页
        "is_first_run": True
    },
    {
        "user_euid": "197319743786161",
        "thread_id": "636748637",
        "current_page": 1,
        "is_first_run": True
    }
]

# 请求头（保持和抓包一致）
REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Cookie": "smidV2=2026011315195927038473f1322f5f23da170fa2f4a39000833ab6c819c0f40; _c_WBKFRo=FpYwQAh7wtgSOPIfu6z9ByCqGTO1WCMu9G6fqvHN; _HUPUSSOID=b6c06135-8202-4137-87c3-181d6e33e847; _CLT=00376064be821b71351c003dda774e37; ua=23270281; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%2219bb63b1a30d49-013099f37f9d1c9-1c525631-1296000-19bb63b1a31b0a%22%2C%22first_id%22%3A%22%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTliYjYzYjFhMzBkNDktMDEzMDk5ZjM3ZjlkMWM5LTFjNTI1NjMxLTEyOTYwMDAtMTliYjYzYjFhMzFiMGEifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%22%2C%22value%22%3A%22%22%7D%2C%22%24device_id%22%3A%2219bb63b1a30d49-013099f37f9d1c9-1c525631-1296000-19bb63b1a31b0a%22%7D; tfstk=gCw-3C9RNiK8bCWfWLfcxfP3Z4ScisqrMzr6K20kOrUYYypkEvDoODgYPQ0nqkgLJr02tDM7-yLLrr4KTgunR2U3A7jcIOqz4vkQpNXGI8vNFW4JFvG5AmiIbimWmkKKXvkCSZADdbWtLzE6HxkQcinnYLT7R0MfDDnZdLGBFITjuDMIdXgSGmiKA3TSNLsYcqoId2aIdiHjuDMIRyMIQp5x8QgMpSB4PJzyr2vBd-n-GsqSlC3uh0HjWuZvdpts2b3_Vq_Jhilr9zh8nTLZ2SZTC0UFQLkS9Wwoh8_fdxZaiziYRNdKl5ezpf2RWCu7U2zxs7Q9ePUrArHuCM5rwliQffN5Yhi4Nzej9-jFgbNar5GYnapq5SZYxjFVYQ03_DaE_JbwU4ZQbRPiBTLZ2SZtHgubIREQaF0txQsADBRENmPL25cEBxVFUm3Gm0AeTjCqDVjqrBOB-SoxSij9TBlAg; acw_tc=707c9f7817727902052561870ed71077b5e4a74a7a88a41b593497338f502f; .thumbcache_33f5730e7694fd15728921e201b4826a=wlwllWSB9En7vQLhxzRdnrFoqXCayUGgKWt9YVZIEraZZxaz5N7+x54eJkzrxChLqyOPypHQxqvqFYWECeud+w%3D%3D"
}

# ==================== 工具函数 ====================
def load_status():
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            status = json.load(f)
            # 兼容旧字段
            for user_config in status.get("user_configs", []):
                if "user_id" in user_config and "user_euid" not in user_config:
                    user_config["user_euid"] = user_config.pop("user_id")
            return status
    except:
        return {
            "pushed_items": {},
            "user_configs": MONITOR_USERS
        }

def save_status(status):
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
        print(f"✅ 状态文件已保存：{STATUS_FILE}")
    except Exception as e:
        print(f"❌ 保存状态失败：{str(e)}")

def fetch_hupu_full_html(user_euid, thread_id, page_num):
    """爬取页面并全量打印HTML"""
    url = f"https://bbs.hupu.com/{thread_id}_{user_euid}-{page_num}.html"
    print(f"\n=====================================")
    print(f"📡 爬取URL：{url}")
    print(f"=====================================")
    
    try:
        resp = requests.get(
            url=url,
            headers=REQUEST_HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True
        )
        resp.raise_for_status()
        resp.encoding = "utf-8"
        full_html = resp.text
        
        # 打印核心信息
        print(f"\n✅ 爬取成功！状态码：{resp.status_code}")
        print(f"✅ HTML总长度：{len(full_html)} 字符")
        print(f"\n=====================================")
        print(f"📄 全量HTML内容开始（无截断）：")
        print(f"=====================================\n")
        
        # 全量打印HTML（无任何截断）
        print(full_html)
        
        print(f"\n=====================================")
        print(f"📄 全量HTML内容结束")
        print(f"=====================================")
        
        # 额外：保存HTML到文件（方便本地查看）
        save_path = "hupu_full_html.html"
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(full_html)
        print(f"\n✅ HTML已保存到本地文件：{save_path}")
        
        return full_html
    except requests.exceptions.RequestException as e:
        print(f"❌ 爬取失败：{str(e)}")
        return None

def monitor_single_user(user_config, status):
    """监控单个用户，核心是打印HTML"""
    target_euid = user_config.get("user_euid") or user_config.get("user_id", "")
    thread_id = user_config["thread_id"]
    current_page = user_config["current_page"]
    is_first_run = user_config["is_first_run"]
    
    if not target_euid:
        print(f"❌ 用户配置缺少euid，跳过监控")
        return
    
    print(f"\n=====================================")
    print(f"监控用户：{target_euid} | 帖子：{thread_id}")
    print(f"当前页码：{current_page} | 首次运行：{is_first_run}")
    print(f"=====================================")
    
    # 核心操作：爬取并全量打印HTML
    fetch_hupu_full_html(target_euid, thread_id, current_page)
    
    # 页码保持不变（仅用于打印HTML，不翻页）
    print(f"\n📄 仅打印HTML，页码保持{current_page}不变")

# ==================== 主函数 ====================
def main():
    print(f"\n🚀 虎扑HTML全量打印工具启动 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 加载状态
    status = load_status()
    
    # 只监控第一个用户（当前请求的22页）
    if status["user_configs"]:
        first_user = status["user_configs"][0]
        monitor_single_user(first_user, status)
    else:
        print(f"❌ 无监控用户配置")
    
    # 保存状态
    save_status(status)
    
    print(f"\n🛑 工具运行结束 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
