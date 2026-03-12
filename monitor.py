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
    except Exception as e:
        print(f"❌ 获取HTML失败: {e}")
        return None

def ultra_strong_filter(raw_str):
    """超强过滤函数"""
    if not raw_str:
        return ""
    
    # ========== 第一步：移除所有HTML相关内容 ==========
    raw_str = re.sub(r'\\u003c[^\\]+\\u003e', '', raw_str)  # Unicode HTML标签
    raw_str = re.sub(r'<[^>]+>', '', raw_str)  # 普通HTML标签
    raw_str = re.sub(r'img\s+src\s*=\s*["\'][^"\']+["\']', '', raw_str)  # img标签
    
    # ========== 第二步：移除所有特殊字符 ==========
    raw_str = raw_str.replace('\\', '')  # 移除所有反斜杠
    raw_str = re.sub(r'https?://[^"]+', '', raw_str)  # 移除URL
    raw_str = raw_str.replace('/', '').replace('=', '').replace('?', '')
    raw_str = raw_str.replace('&', '').replace('%', '').replace('+', '')
    raw_str = raw_str.replace(';', '').replace(':', '').replace('*', '')
    
    # ========== 第三步：修复JSON语法 ==========
    raw_str = re.sub(r',\s*}', '}', raw_str)
    raw_str = re.sub(r',\s*]', ']', raw_str)
    raw_str = re.sub(r'([{,]\s*)([a-zA-Z0-9_]+)\s*:', r'\1"\2":', raw_str)
    
    # 确保首尾是大括号
    if not raw_str.startswith('{'):
        raw_str = '{' + raw_str
    if not raw_str.endswith('}'):
        raw_str = raw_str + '}'
    
    return raw_str

def print_char_by_char(s, error_pos=None):
    """逐字符打印字符串，标记错误位置"""
    print("\n" + "="*80)
    print("📝 逐字符分析（字符位置 → 字符内容）：")
    print("="*80)
    
    # 每20个字符一行
    for i in range(0, len(s), 20):
        line_chars = s[i:i+20]
        line_str = ""
        for j, c in enumerate(line_chars):
            pos = i + j
            # 标记错误位置
            if error_pos is not None and pos == error_pos:
                line_str += f"[{pos}:{repr(c)}] "  # 错误位置高亮
            else:
                line_str += f"{pos}:{repr(c)} "
        
        print(line_str.strip())
    
    if error_pos is not None:
        print(f"\n🔴 错误位置 {error_pos} 附近内容：")
        start = max(0, error_pos - 10)
        end = min(len(s), error_pos + 10)
        for pos in range(start, end):
            if pos == error_pos:
                print(f"[{pos}:{repr(s[pos])}] ← 错误位置")
            else:
                print(f"{pos}:{repr(s[pos])}")

def extract_replies_with_full_debug():
    """完整调试版本：打印所有内容"""
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
    
    # 3. 提取replies数据块
    replies_pattern = r'"replies"\s*:\s*({[^}]*?"count"\s*:\s*\d+[^}]*?"size"\s*:\s*\d+[^}]*?"current"\s*:\s*\d+[^}]*?"total"\s*:\s*\d+[^}]*?"list"\s*:\s*\[(.*?)\]\s*[^}]*})'
    replies_match = re.search(replies_pattern, next_data_match.group(1), re.DOTALL)
    
    if not replies_match:
        print("❌ 未提取到replies数据块")
        return
    
    # 4. 获取原始数据并打印全部
    raw_replies = replies_match.group(1)
    print("📥 " + "="*80)
    print("原始replies数据（全部）：")
    print("="*80)
    print(raw_replies)
    print(f"\n📏 原始数据长度: {len(raw_replies)} 字符")
    
    # 5. 强过滤处理并打印全部
    filtered_replies = ultra_strong_filter(raw_replies)
    print("\n🧹 " + "="*80)
    print("强过滤后replies数据（全部）：")
    print("="*80)
    print(filtered_replies)
    print(f"\n📏 过滤后数据长度: {len(filtered_replies)} 字符")
    
    # 6. 尝试解析JSON
    try:
        replies_data = json.loads(filtered_replies)
        print("\n✅ JSON解析成功！")
        
        # 打印解析结果
        print("\n" + "="*80)
        print("解析后的replies数据：")
        print("="*80)
        print(json.dumps(replies_data, ensure_ascii=False, indent=2))
        
    except json.JSONDecodeError as e:
        print(f"\n❌ JSON解析失败详情：")
        print(f"  错误类型: {type(e).__name__}")
        print(f"  错误位置: line {e.lineno}, column {e.colno} (char {e.pos})")
        print(f"  错误信息: {e.msg}")
        
        # 逐字符打印并标记错误位置
        print_char_by_char(filtered_replies, e.pos)
        
        # 保存所有调试信息
        with open("debug_all_info.txt", "w", encoding="utf-8") as f:
            f.write("=== 原始数据 ===\n")
            f.write(raw_replies + "\n\n")
            f.write("=== 过滤后数据 ===\n")
            f.write(filtered_replies + "\n\n")
            f.write(f"=== 错误信息 ===\n")
            f.write(f"位置: char {e.pos}\n")
            f.write(f"信息: {e.msg}\n")
            f.write(f"错误位置内容: {filtered_replies[max(0,e.pos-10):e.pos+10]}\n")
        
        print("\n📄 所有调试信息已保存到 debug_all_info.txt")
        
        # ========== 终极方案：直接提取关键数据 ==========
        print("\n💥 终极方案：不解析JSON，直接提取关键数据")
        print("="*80)
        
        # 直接提取list中的回复
        list_pattern = r'"list"\s*:\s*\[(.*?)\]\s*[,}]'
        list_match = re.search(list_pattern, raw_replies, re.DOTALL)
        
        if list_match:
            list_content = list_match.group(1)
            
            # 提取所有回复的PID
            pids = re.findall(r'"pid"\s*:\s*"([^"]+)"', list_content)
            # 提取所有作者EUID
            euids = re.findall(r'"euid"\s*:\s*"([^"]+)"', list_content)
            # 提取所有作者名称
            names = re.findall(r'"puname"\s*:\s*"([^"]+)"', list_content)
            # 提取所有内容（清理HTML）
            contents = re.findall(r'"content"\s*:\s*"([^"]+)"', list_content)
            clean_contents = [re.sub(r'<[^>]+>', '', c).replace('\\u003c', '').replace('\\u003e', '') for c in contents]
            
            print(f"📊 直接提取统计：")
            print(f"  - 回复数量: {len(pids)}")
            print(f"  - 所有EUID: {euids}")
            print(f"  - 目标EUID: {TARGET_CONFIG['user_euid']}")
            
            # 匹配目标回复
            target_indexes = [i for i, euid in enumerate(euids) if euid == TARGET_CONFIG['user_euid']]
            
            if target_indexes:
                print(f"\n🎯 找到 {len(target_indexes)} 条目标回复：")
                for idx in target_indexes:
                    print(f"\n回复 {idx+1}:")
                    print(f"  PID: {pids[idx] if idx < len(pids) else '未知'}")
                    print(f"  作者: {names[idx] if idx < len(names) else '未知'}")
                    print(f"  内容: {clean_contents[idx] if idx < len(clean_contents) else '未知'}")
            else:
                print(f"\n❌ 未找到目标EUID的回复")
        else:
            print("❌ 无法直接提取list数据")

if __name__ == "__main__":
    extract_replies_with_full_debug()
