import json
import re
import subprocess
import os

# ==================== 全局配置 ====================
TARGET_CONFIG = {
    "user_euid": "20829162237257",
    "thread_id": "636748637",
    "page_num": 21
}

# curl命令（保持不变）
CURL_COMMAND = f'''curl 'https://bbs.hupu.com/{TARGET_CONFIG["thread_id"]}_{TARGET_CONFIG["user_euid"]}-{TARGET_CONFIG["page_num"]}.html' \
  -H 'accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7' \
  -H 'accept-language: zh-CN,zh;q=0.9,en;q=0.8' \
  -b 'smidV2=2026011315195927038473f1322f5f23da170fa2f4a39000833ab6c819c0f40; _c_WBKFRo=FpYwQAh7wtgSOPIfu6z9ByCqGTO1WCMu9G6fqvHN; _HUPUSSOID=b6c06135-8202-4137-87c3-181d6e33e847; _CLT=00376064be821b71351c003dda774e37; ua=23270281; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%2219bb63b1a30d49-013099f37f9d1c9-1c525631-1296000-19bb63b1a31b0a%22%2C%22first_id%22%3A%22%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTliYjYzYjFhMzBkNDktMDEzMDk5ZjM3ZjlkMWM5LTFjNTI1NjMxLTEyOTYwMDAtMTliYjYzYjFhMzFiMGEifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%22%2C%22value%22%3A%22%22%7D%2C%22%24device_id%22%3A%2219bb63b1a30d49-013099f37f9d1c9-1c525631-1296000-19bb63b1a31b0a%22%7D; tfstk=gCw-3C9RNiK8bCWfWLfcxfP3Z4ScisqrMzr6K20kOrUYYypkEvDoODgYPQ0nqkgLJr02tDM7-yLLrr4KTgunR2U3A7jcIOqz4vkQpNXGI8vNFW4JFvG5AmiIbimWmkKKXvkCSZADdbWtLzE6HxkQcinnYLT7R0MfDDnZdLGBFITjuDMIdXgSGmiKA3TSNLsYcqoId2aIdiHjuDMIRyMIQp5x8QgMpSB4PJzyr2vBd-n-GsqSlC3uh0HjWuZvdpts2b3_Vq_Jhilr9zh8nTLZ2SZTC0UFQLkS9Wwoh8_fdxZaiziYRNdKl5ezpf2RWCu7U2zxs7Q9ePUrArHuCM5rwliQffN5Yhi4Nzej9-jFgbNar5GYnapq5SZYxjFVYQ03_DaE_JbwU4ZQbRPiBTLZ2SZtHgubIREQaF0txQsADBRENmPL25cEBxVFUm3Gm0AeTjCqDVjqrBOB-SoxSij9TBlAg; acw_tc=707c9f7817727902052561870ed71077b5e4a74a7a88a41b593497338f502f; .thumbcache_33f5730e7694fd15728921e201b4826a=gxHFw9Mmv9CoJFvSLlwsi5mfmTnMhtpLr/3uVjQ7msYqU+mf5+85e6WKg1Y+tdBEqEM/r5UHVXsu+fesaJuH0w%3D%3D' \
  -H 'if-none-match: "259ef-1lmunewi0WnHSDa3L4g4nxIwVZA"' \
  -H 'priority: u=0, i' \
  -H 'referer: https://bbs.hupu.com/636748637_20829162237257-22.html' \
  -H 'sec-ch-ua: "Not:A-Brand\";v=\"99\", \"Google Chrome\";v=\"145\", \"Chromium\";v=\"145"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-platform: "macOS"' \
  -H 'sec-fetch-dest: document' \
  -H 'sec-fetch-mode: navigate' \
  -H 'sec-fetch-site: same-origin' \
  -H 'upgrade-insecure-requests: 1' \
  -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36' \
  --silent --show-error'''

def run_curl_and_get_html():
    """获取HTML内容"""
    try:
        result = subprocess.run(
            CURL_COMMAND,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8"
        )
        return result.stdout
    except Exception:
        return None

def clean_html_tags(content):
    """清理HTML标签"""
    if not content:
        return ""
    content = re.sub(r'<[^>]+>', '', content)
    content = content.replace("&nbsp;", " ").replace("&amp;", "&")
    content = bytes(content, 'utf-8').decode('unicode_escape', errors='ignore')
    content = re.sub(r'\s+', ' ', content).strip()
    return content

def fix_special_char_json(replies_str):
    """
    修复包含特殊字符的JSON字符串
    重点处理content字段中的URL特殊字符
    """
    if not replies_str:
        return replies_str
    
    # 1. 修复开头/结尾多余大括号
    replies_str = replies_str.strip()
    while replies_str.startswith('{') and replies_str[1:2] == '{':
        replies_str = replies_str[1:]
    while replies_str.endswith('}') and replies_str[-2:-1] == '}':
        replies_str = replies_str[:-1]
    
    # 2. 关键修复：处理content字段中的特殊字符
    # 匹配 "content":"..." 格式的字段，保留引号内的内容
    content_pattern = r'("content"\s*:\s*")(.*?)("(?:,|\s*}|]))'
    def fix_content(match):
        key = match.group(1)
        content = match.group(2)
        end = match.group(3)
        
        # 对content内容进行转义处理
        # 转义双引号、反斜杠等特殊字符
        content = content.replace('\\', '\\\\')  # 反斜杠转义
        content = content.replace('"', '\\"')    # 双引号转义
        content = content.replace('\n', '\\n')  # 换行符转义
        content = content.replace('\r', '\\r')  # 回车符转义
        
        return f"{key}{content}{end}"
    
    # 修复所有content字段
    replies_str = re.sub(content_pattern, fix_content, replies_str, flags=re.DOTALL)
    
    # 3. 修复其他JSON语法问题
    # 确保属性名有双引号
    pattern = r'([{,]\s*)([a-zA-Z0-9_]+)\s*:'
    def add_quotes(match):
        return f'{match.group(1)}"{match.group(2)}":'
    replies_str = re.sub(pattern, add_quotes, replies_str)
    
    # 4. 修复Unicode编码
    replies_str = replies_str.replace(r'\u003c', '<').replace(r'\u003e', '>')
    
    # 5. 移除控制字符和多余逗号
    replies_str = re.sub(r'[\n\r\t]', '', replies_str)
    replies_str = re.sub(r',\s*}', '}', replies_str)
    replies_str = re.sub(r',\s*]', ']', replies_str)
    
    # 6. 确保JSON格式完整
    if not replies_str.startswith('{'):
        replies_str = '{' + replies_str
    if not replies_str.endswith('}'):
        replies_str = replies_str + '}'
    
    return replies_str

def extract_and_parse_replies():
    """核心提取解析函数"""
    # 1. 获取HTML
    html = run_curl_and_get_html()
    if not html:
        print("❌ 获取HTML失败")
        return
    
    # 2. 提取__NEXT_DATA__
    next_data_pattern = r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>'
    next_data_match = re.search(next_data_pattern, html, re.DOTALL)
    if not next_data_match:
        print("❌ 未找到__NEXT_DATA__")
        return
    
    next_data_str = next_data_match.group(1).strip()
    
    # 3. 提取replies数据块
    replies_pattern = r'"replies"\s*:\s*({[^}]*?"count"\s*:\s*\d+[^}]*?"size"\s*:\s*\d+[^}]*?"current"\s*:\s*\d+[^}]*?"total"\s*:\s*\d+[^}]*?"list"\s*:\s*\[(.*?)\]\s*[^}]*})'
    replies_match = re.search(replies_pattern, next_data_str, re.DOTALL)
    if not replies_match:
        print("❌ 未提取到replies数据块")
        return
    
    replies_str = replies_match.group(1)
    print(f"📌 原始replies数据（出错位置附近）：")
    print(replies_str[150:170])  # 打印第161列附近的内容
    
    # 4. 修复并解析JSON（关键修复）
    fixed_replies_str = fix_special_char_json(replies_str)
    
    try:
        # 解析修复后的JSON
        replies_data = json.loads(fixed_replies_str)
        print("\n✅ JSON解析成功！")
        
        # 打印完整的replies数据
        print("\n" + "="*50)
        print("📋 完整的replies数据：")
        print("="*50)
        print(json.dumps(replies_data, ensure_ascii=False, indent=2))
        
        # 提取list中的回复并打印
        reply_list = replies_data.get("list", [])
        print(f"\n📊 共提取到 {len(reply_list)} 条回复：")
        
        for i, reply in enumerate(reply_list):
            print(f"\n--- 回复 {i+1} ---")
            print(f"PID: {reply.get('pid', '未知')}")
            print(f"作者EUID: {reply.get('author', {}).get('euid', '未知')}")
            print(f"作者名称: {reply.get('author', {}).get('puname', '未知')}")
            print(f"时间: {reply.get('createdAtFormat', '未知')}")
            print(f"内容: {clean_html_tags(reply.get('content', ''))}")
            
            # 检查是否是目标EUID的回复
            if reply.get('author', {}).get('euid', '') == TARGET_CONFIG['user_euid']:
                print("🔹 👉 这是目标用户的回复！")
        
        # 筛选目标EUID的回复
        target_replies = [
            r for r in reply_list 
            if r.get('author', {}).get('euid', '') == TARGET_CONFIG['user_euid']
        ]
        
        print(f"\n🎯 找到 {len(target_replies)} 条目标EUID的回复")
        
    except json.JSONDecodeError as e:
        print(f"\n❌ JSON解析失败详情：")
        print(f"  错误类型: {type(e).__name__}")
        print(f"  错误位置: line {e.lineno}, column {e.colno} (char {e.pos})")
        print(f"  错误信息: {e.msg}")
        print(f"  出错位置内容: {fixed_replies_str[e.pos-10:e.pos+10]}")
        
        # 保存修复后的JSON用于调试
        with open("fixed_replies_debug.json", "w", encoding="utf-8") as f:
            f.write(fixed_replies_str)
        print("\n📄 修复后的JSON已保存到 fixed_replies_debug.json")

if __name__ == "__main__":
    extract_and_parse_replies()
