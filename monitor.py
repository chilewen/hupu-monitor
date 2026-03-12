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

def ultra_strong_filter(raw_str):
    """
    超强过滤函数：彻底移除所有HTML标签、特殊字符和转义序列
    确保JSON能够正常解析
    """
    if not raw_str:
        return ""
    
    # ========== 第一步：移除所有HTML相关内容 ==========
    # 1. 移除Unicode编码的HTML标签 (\u003c = <, \u003e = >)
    raw_str = re.sub(r'\\u003c[^\\]+\\u003e', '', raw_str)
    # 2. 移除普通HTML标签
    raw_str = re.sub(r'<[^>]+>', '', raw_str)
    # 3. 移除所有img标签相关内容（包括URL）
    raw_str = re.sub(r'<img[^>]*>', '', raw_str)
    raw_str = re.sub(r'img\s+src\s*=\s*["\'][^"\']+["\']', '', raw_str)
    
    # ========== 第二步：移除影响JSON解析的特殊字符 ==========
    # 1. 移除所有反斜杠转义（除了必要的）
    raw_str = raw_str.replace('\\', '')
    # 2. 移除所有URL特殊字符
    raw_str = re.sub(r'https?://[^"]+', '', raw_str)
    # 3. 移除可能导致JSON错误的特殊字符
    raw_str = raw_str.replace('/', '').replace('=', '').replace('?', '')
    raw_str = raw_str.replace('&', '').replace('%', '').replace('+', '')
    
    # ========== 第三步：修复JSON语法 ==========
    # 1. 确保双引号配对
    quote_count = raw_str.count('"')
    if quote_count % 2 != 0:
        raw_str = raw_str.rstrip('"')  # 移除最后一个未配对的引号
    
    # 2. 移除行尾多余的逗号
    raw_str = re.sub(r',\s*}', '}', raw_str)
    raw_str = re.sub(r',\s*]', ']', raw_str)
    
    # 3. 修复属性名格式
    raw_str = re.sub(r'([{,]\s*)([a-zA-Z0-9_]+)\s*:', r'\1"\2":', raw_str)
    
    return raw_str

def extract_replies_with_strong_filter():
    """使用强过滤提取并解析replies数据"""
    # 1. 获取HTML内容
    html = run_curl_and_get_html()
    if not html:
        print("❌ 无法获取HTML内容")
        return
    
    # 2. 提取__NEXT_DATA__
    next_data_pattern = r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>'
    next_data_match = re.search(next_data_pattern, html, re.DOTALL)
    if not next_data_match:
        print("❌ 未找到__NEXT_DATA__标签")
        return
    
    next_data_str = next_data_match.group(1).strip()
    
    # 3. 提取replies数据块
    replies_pattern = r'"replies"\s*:\s*({[^}]*?"count"\s*:\s*\d+[^}]*?"size"\s*:\s*\d+[^}]*?"current"\s*:\s*\d+[^}]*?"total"\s*:\s*\d+[^}]*?"list"\s*:\s*\[(.*?)\]\s*[^}]*})'
    replies_match = re.search(replies_pattern, next_data_str, re.DOTALL)
    
    if not replies_match:
        print("❌ 未提取到replies数据块")
        return
    
    # 4. 强过滤处理
    raw_replies = replies_match.group(1)
    print(f"📥 原始replies数据长度: {len(raw_replies)}")
    
    # 应用超强过滤
    filtered_replies = ultra_strong_filter(raw_replies)
    print(f"🧹 强过滤后数据长度: {len(filtered_replies)}")
    
    # 5. 解析处理后的JSON
    try:
        replies_data = json.loads(filtered_replies)
        print("\n✅ JSON解析成功！")
        
        # 打印完整的replies数据
        print("\n" + "="*60)
        print("📋 强过滤后的完整replies数据：")
        print("="*60)
        print(json.dumps(replies_data, ensure_ascii=False, indent=2))
        
        # 提取并打印所有回复
        reply_list = replies_data.get("list", [])
        print(f"\n📊 共提取到 {len(reply_list)} 条回复：")
        
        for i, reply in enumerate(reply_list):
            print(f"\n--- 回复 {i+1} ---")
            print(f"PID: {reply.get('pid', '未知')}")
            print(f"作者ID: {reply.get('authorId', '未知')}")
            print(f"作者EUID: {reply.get('author', {}).get('euid', '未知')}")
            print(f"作者昵称: {reply.get('author', {}).get('puname', '未知')}")
            print(f"发布时间: {reply.get('createdAtFormat', '未知')}")
            print(f"纯文本内容: {reply.get('content', '无内容')}")
            
            # 标记目标用户回复
            if reply.get('author', {}).get('euid', '') == TARGET_CONFIG['user_euid']:
                print("🔴 【目标用户回复】")
        
        # 筛选目标用户回复
        target_replies = [
            r for r in reply_list 
            if r.get('author', {}).get('euid', '') == TARGET_CONFIG['user_euid']
        ]
        
        print(f"\n" + "="*60)
        print(f"🎯 目标EUID({TARGET_CONFIG['user_euid']})的回复: {len(target_replies)} 条")
        print("="*60)
        
        if target_replies:
            for i, reply in enumerate(target_replies):
                print(f"\n目标回复 {i+1}:")
                print(f"内容: {reply.get('content', '无')}")
        else:
            print("❌ 未找到目标用户的回复")
        
        # 保存结果
        with open("filtered_replies_result.json", "w", encoding="utf-8") as f:
            json.dump({
                "total_replies": len(reply_list),
                "target_replies": target_replies,
                "full_replies_data": replies_data
            }, f, ensure_ascii=False, indent=2)
        print("\n💾 结果已保存到 filtered_replies_result.json")
        
    except json.JSONDecodeError as e:
        print(f"\n❌ JSON解析失败: {e}")
        # 保存过滤后的数据用于调试
        with open("filtered_replies_debug.txt", "w", encoding="utf-8") as f:
            f.write(filtered_replies)
        print("📄 过滤后的数据已保存到 filtered_replies_debug.txt")

if __name__ == "__main__":
    extract_replies_with_strong_filter()
