import json
import re
import time
import os
import requests
from datetime import datetime

# ==================== 全局配置（100%复刻curl） ====================
BARK_KEY = os.getenv("BARK_KEY", "")
TIMEOUT = 15
STATUS_FILE = "hupu_status.json"

# 目标请求参数（和你的curl完全一致）
TARGET_CONFIG = {
    "user_euid": "20829162237257",
    "thread_id": "636748637",
    "page_num": 21  # curl请求的是21页，不是22页！
}

# 100% 复刻curl的请求头（逐行复制，无任何修改）
REQUEST_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "cookie": "smidV2=2026011315195927038473f1322f5f23da170fa2f4a39000833ab6c819c0f40; _c_WBKFRo=FpYwQAh7wtgSOPIfu6z9ByCqGTO1WCMu9G6fqvHN; _HUPUSSOID=b6c06135-8202-4137-87c3-181d6e33e847; _CLT=00376064be821b71351c003dda774e37; ua=23270281; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%2219bb63b1a30d49-013099f37f9d1c9-1c525631-1296000-19bb63b1a31b0a%22%2C%22first_id%22%3A%22%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTliYjYzYjFhMzBkNDktMDEzMDk5ZjM3ZjlkMWM5LTFjNTI1NjMxLTEyOTYwMDAtMTliYjYzYjFhMzFiMGEifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%22%2C%22value%22%3A%22%22%7D%2C%22%24device_id%22%3A%2219bb63b1a30d49-013099f37f9d1c9-1c525631-1296000-19bb63b1a31b0a%22%7D; tfstk=gCw-3C9RNiK8bCWfWLfcxfP3Z4ScisqrMzr6K20kOrUYYypkEvDoODgYPQ0nqkgLJr02tDM7-yLLrr4KTgunR2U3A7jcIOqz4vkQpNXGI8vNFW4JFvG5AmiIbimWmkKKXvkCSZADdbWtLzE6HxkQcinnYLT7R0MfDDnZdLGBFITjuDMIdXgSGmiKA3TSNLsYcqoId2aIdiHjuDMIRyMIQp5x8QgMpSB4PJzyr2vBd-n-GsqSlC3uh0HjWuZvdpts2b3_Vq_Jhilr9zh8nTLZ2SZTC0UFQLkS9Wwoh8_fdxZaiziYRNdKl5ezpf2RWCu7U2zxs7Q9ePUrArHuCM5rwliQffN5Yhi4Nzej9-jFgbNar5GYnapq5SZYxjFVYQ03_DaE_JbwU4ZQbRPiBTLZ2SZtHgubIREQaF0txQsADBRENmPL25cEBxVFUm3Gm0AeTjCqDVjqrBOB-SoxSij9TBlAg; acw_tc=707c9f7817727902052561870ed71077b5e4a74a7a88a41b593497338f502f; .thumbcache_33f5730e7694fd15728921e201b4826a=gxHFw9Mmv9CoJFvSLlwsi5mfmTnMhtpLr/3uVjQ7msYqU+mf5+85e6WKg1Y+tdBEqEM/r5UHVXsu+fesaJuH0w%3D%3D",
    "if-none-match": "\"259ef-1lmunewi0WnHSDa3L4g4nxIwVZA\"",
    "priority": "u=0, i",
    "referer": "https://bbs.hupu.com/636748637_20829162237257-22.html",
    "sec-ch-ua": "\"Not:A-Brand\";v=\"99\", \"Google Chrome\";v=\"145\", \"Chromium\";v=\"145\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"macOS\"",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
}

# ==================== 核心函数 ====================
def fetch_exact_curl_html():
    """100% 复刻curl请求，返回和curl一致的HTML"""
    # 构造和curl完全一致的URL（21页）
    url = f"https://bbs.hupu.com/{TARGET_CONFIG['thread_id']}_{TARGET_CONFIG['user_euid']}-{TARGET_CONFIG['page_num']}.html"
    print(f"\n=====================================")
    print(f"📡 复刻curl请求：{url}")
    print(f"=====================================")
    
    try:
        # 发送和curl完全一致的请求（禁用重定向，curl默认也禁用）
        resp = requests.get(
            url=url,
            headers=REQUEST_HEADERS,
            timeout=TIMEOUT,
            allow_redirects=False,  # 关键：curl默认不跟随重定向
            verify=False  # 可选：避免SSL校验问题
        )
        
        # 打印请求详情（对比curl）
        print(f"✅ 请求状态码：{resp.status_code}")
        print(f"✅ 响应头 Content-Length：{resp.headers.get('Content-Length', '未知')}")
        print(f"✅ 响应头 If-None-Match：{resp.headers.get('ETag', '未知')}")
        
        # 编码设置（和curl一致）
        resp.encoding = "utf-8"
        full_html = resp.text
        
        # 1. 全量打印HTML
        print(f"\n=====================================")
        print(f"📄 全量HTML内容（和curl一致）：")
        print(f"=====================================\n")
        print(full_html)
        
        # 2. 保存到文件（方便对比）
        save_path = "curl_exact_html.html"
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(full_html)
        print(f"\n✅ HTML已保存到：{save_path}")
        
        # 3. 对比长度（验证一致性）
        print(f"\n=====================================")
        print(f"📊 内容对比：")
        print(f"- Python请求HTML长度：{len(full_html)} 字符")
        print(f"- 请对比你本地curl的HTML长度，确认是否一致")
        print(f"=====================================")
        
        return full_html
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求失败：{str(e)}")
        return None

def search_replies_in_html(html):
    """在HTML中搜索replies相关内容（辅助定位）"""
    if not html:
        print(f"❌ 无HTML内容可搜索")
        return
    
    print(f"\n=====================================")
    print(f"🔍 搜索replies相关内容：")
    print(f"=====================================")
    
    # 搜索所有包含replies的行
    lines = html.split("\n")
    for idx, line in enumerate(lines):
        if "replies" in line.lower():
            print(f"行{idx+1}：{line.strip()[:200]}...")
    
    # 搜索window.bbs_thread_info
    bbs_match = re.search(r'window\.bbs_thread_info\s*=\s*({.*?});', html, re.DOTALL)
    if bbs_match:
        print(f"\n✅ 找到window.bbs_thread_info：")
        print(bbs_match.group(1)[:1000] + "...")
    else:
        print(f"\n❌ 未找到window.bbs_thread_info")

# ==================== 主函数 ====================
def main():
    print(f"\n🚀 100%复刻curl请求工具启动 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 核心操作：复刻curl请求并打印HTML
    html = fetch_exact_curl_html()
    
    # 辅助操作：搜索replies内容
    if html:
        search_replies_in_html(html)
    
    print(f"\n🛑 工具运行结束")

if __name__ == "__main__":
    main()
