import json
import re
import subprocess
import os
from datetime import datetime

# ==================== 全局配置 ====================
BARK_KEY = os.getenv("BARK_KEY", "")
STATUS_FILE = "hupu_status.json"

# 目标配置
TARGET_CONFIG = {
    "user_euid": "20829162237257",
    "thread_id": "636748637",
    "page_num": 21
}

# 你的curl命令
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

# ==================== 核心函数 ====================
def run_curl_and_get_html():
    """调用本地curl命令，获取HTML内容"""
    try:
        # 执行curl命令
        result = subprocess.run(
            CURL_COMMAND,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8"
        )
        
        # 获取HTML内容
        full_html = result.stdout
        return full_html
    except Exception:
        return None

def clean_html_tags(content):
    """清理所有HTML标签，包括p、img、div等"""
    if not content:
        return ""
    
    # 移除所有HTML标签
    content = re.sub(r'<[^>]+>', '', content)
    
    # 移除HTML实体编码
    content = content.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    
    # 处理Unicode转义
    content = bytes(content, 'utf-8').decode('unicode_escape', errors='ignore')
    
    # 清理多余的空格和换行
    content = re.sub(r'\s+', ' ', content).strip()
    
    return content

def fix_replies_json(replies_str):
    """修复replies JSON字符串的语法错误"""
    if not replies_str:
        return replies_str
    
    # 修复开头/结尾的多余大括号
    replies_str = replies_str.strip()
    while replies_str.startswith('{') and replies_str[1:2] == '{':
        replies_str = replies_str[1:]
    while replies_str.endswith('}') and replies_str[-2:-1] == '}':
        replies_str = replies_str[:-1]
    
    # 确保JSON格式正确
    if not replies_str.startswith('{'):
        replies_str = '{' + replies_str
    if not replies_str.endswith('}'):
        replies_str = replies_str + '}'
    
    # 修复属性名没有双引号的问题
    pattern = r'([{,]\s*)([a-zA-Z0-9_]+)\s*:'
    def add_quotes(match):
        return f'{match.group(1)}"{match.group(2)}":'
    replies_str = re.sub(pattern, add_quotes, replies_str)
    
    # 修复字符串没有双引号的问题
    replies_str = re.sub(r':\s*([^\d\.\-truefalse{[\],}\s]+)(?=[,\}\]])', r':"\1"', replies_str)
    
    # 修复转义问题
    replies_str = replies_str.replace(r'\u003c', '<').replace(r'\u003e', '>')
    replies_str = replies_str.replace(r'\"', '"').replace(r'\\', '\\')
    
    # 移除控制字符和多余逗号
    replies_str = re.sub(r'[\n\r\t]', '', replies_str)
    replies_str = re.sub(r',\s*}', '}', replies_str)
    replies_str = re.sub(r',\s*]', ']', replies_str)
    
    return replies_str

def extract_replies_data(html):
    """提取并解析replies数据"""
    if not html:
        return None
    
    # 提取__NEXT_DATA__标签内容
    next_data_pattern = r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>'
    next_data_match = re.search(next_data_pattern, html, re.DOTALL)
    
    if not next_data_match:
        return None
    
    next_data_str = next_data_match.group(1).strip()
    
    # 提取replies数据块
    replies_pattern = r'"replies"\s*:\s*({[^}]*?"count"\s*:\s*\d+[^}]*?"size"\s*:\s*\d+[^}]*?"current"\s*:\s*\d+[^}]*?"total"\s*:\s*\d+[^}]*?"list"\s*:\s*\[(.*?)\]\s*[^}]*})'
    replies_match = re.search(replies_pattern, next_data_str, re.DOTALL)
    
    if not replies_match:
        return None
    
    try:
        # 获取并修复replies JSON
        replies_str = replies_match.group(1)
        fixed_replies_str = fix_replies_json(replies_str)
        
        # 解析replies数据
        replies_data = json.loads(fixed_replies_str)
        reply_list = replies_data.get("list", [])
        
        # 筛选目标euid的回复
        target_euid = TARGET_CONFIG["user_euid"]
        target_replies = []
        
        for reply in reply_list:
            try:
                # 检查主回复作者euid
                main_author = reply.get("author", {})
                main_euid = main_author.get("euid", "")
                
                # 检查引用回复作者euid
                quote = reply.get("quote", {})
                quote_author = quote.get("author", {})
                quote_euid = quote_author.get("euid", "")
                
                # 收集目标回复
                if main_euid == target_euid or quote_euid == target_euid:
                    if main_euid == target_euid:
                        author_info = main_author
                        content = reply.get("content", "")
                        reply_type = "主回复"
                        create_time = reply.get("createdAtFormat", "")
                    else:
                        author_info = quote_author
                        content = quote.get("content", "")
                        reply_type = "引用回复"
                        create_time = quote.get("createdAtFormat", "")
                    
                    # 清理HTML标签
                    clean_content = clean_html_tags(content)
                    
                    target_replies.append({
                        "pid": reply.get("pid", ""),
                        "euid": target_euid,
                        "username": author_info.get("puname", ""),
                        "time": create_time,
                        "content": clean_content,
                        "reply_type": reply_type,
                        "location": reply.get("location", "")
                    })
                    
            except Exception:
                continue
        
        return target_replies
        
    except Exception:
        # 尝试直接提取list中的回复项
        list_pattern = r'"list"\s*:\s*\[(.*?)\]\s*,'
        list_match = re.search(list_pattern, next_data_str, re.DOTALL)
        
        if list_match:
            list_str = list_match.group(1)
            reply_items = re.findall(r'\{[^{}]*"pid"\s*:\s*"[^"]+"[^}]*"author"\s*:\s*\{[^}]*"euid"\s*:\s*"[^"]+"[^}]*\}[^}]*\}', list_str)
            
            target_replies = []
            for item_str in reply_items:
                try:
                    # 修复并解析单条回复
                    item_str = '{' + item_str + '}'
                    item_str = fix_replies_json(item_str)
                    reply = json.loads(item_str)
                    
                    # 检查euid
                    main_author = reply.get("author", {})
                    main_euid = main_author.get("euid", "")
                    quote = reply.get("quote", {})
                    quote_author = quote.get("author", {})
                    quote_euid = quote_author.get("euid", "")
                    
                    if main_euid == target_euid or quote_euid == target_euid:
                        if main_euid == target_euid:
                            author_info = main_author
                            content = reply.get("content", "")
                            reply_type = "主回复"
                            create_time = reply.get("createdAtFormat", "")
                        else:
                            author_info = quote_author
                            content = quote.get("content", "")
                            reply_type = "引用回复"
                            create_time = quote.get("createdAtFormat", "")
                        
                        clean_content = clean_html_tags(content)
                        
                        target_replies.append({
                            "pid": reply.get("pid", ""),
                            "euid": target_euid,
                            "username": author_info.get("puname", ""),
                            "time": create_time,
                            "content": clean_content,
                            "reply_type": reply_type
                        })
                except Exception:
                    continue
            
            return target_replies
    
    return None

# ==================== 主函数 ====================
def main():
    # 1. 获取HTML内容
    html = run_curl_and_get_html()
    
    # 2. 提取replies数据
    target_replies = extract_replies_data(html)
    
    # 3. 输出结果
    if target_replies and len(target_replies) > 0:
        print(f"\n🎯 匹配到目标euid({TARGET_CONFIG['user_euid']})的回复数：{len(target_replies)}")
        for idx, reply in enumerate(target_replies):
            print(f"\n--- 回复 {idx+1} ({reply['reply_type']}) ---")
            print(f"PID: {reply['pid']}")
            print(f"用户: {reply['username']} ({reply['euid']})")
            print(f"时间: {reply['time']}")
            if 'location' in reply and reply['location']:
                print(f"位置: {reply['location']}")
            print(f"内容: {reply['content']}")
        
        # 保存结果到文件
        with open("target_replies.json", "w", encoding="utf-8") as f:
            json.dump(target_replies, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 目标回复已保存到：target_replies.json")
    else:
        print(f"\n❌ 未找到目标euid的回复数据")

if __name__ == "__main__":
    main()
