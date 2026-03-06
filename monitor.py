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

# 你的curl命令（完整复制，仅做格式调整）
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
    """调用本地curl命令，获取100%一致的HTML"""
    print(f"\n=====================================")
    print(f"📡 执行本地curl命令：")
    print(f"=====================================")
    print(CURL_COMMAND)
    
    try:
        # 执行curl命令，捕获输出
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
        error_output = result.stderr
        
        # 打印基础信息
        print(f"\n✅ curl执行成功！")
        print(f"❌ curl错误输出：{error_output if error_output else '无'}")
        print(f"📊 HTML长度：{len(full_html)} 字符（对比你本地的153896）")
        
        # 验证长度是否匹配
        if len(full_html) == 153896:
            print(f"🎉 长度完全匹配！和本地curl结果一致")
        else:
            print(f"⚠️ 长度不匹配（本地153896 vs 当前{len(full_html)}），但内容已尽可能一致")
        
        # 保存到文件
        save_path = "curl_exact_html.html"
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(full_html)
        print(f"\n✅ HTML已保存到：{save_path}")
        
        # 全量打印（可选，注释掉避免输出过长）
        # print(f"\n=====================================")
        # print(f"📄 全量HTML内容：")
        # print(f"=====================================\n")
        # print(full_html)
        
        return full_html
    except subprocess.CalledProcessError as e:
        print(f"❌ curl执行失败：{e.stderr}")
        return None
    except Exception as e:
        print(f"❌ 执行curl出错：{str(e)}")
        return None

def extract_replies_from_html(html):
    """从HTML中提取replies数据（核心）"""
    if not html:
        print(f"❌ 无HTML内容可解析")
        return None
    
    print(f"\n=====================================")
    print(f"🔍 提取replies数据：")
    print(f"=====================================")
    
    # 第一步：搜索所有包含replies的JSON片段
    # 匹配任意包含replies的大JSON块（虎扑的核心数据）
    json_patterns = [
        r'window\.bbs_thread_info\s*=\s*({.*?});',  # 主数据
        r'var\s+threadData\s*=\s*({.*?});',         # 备选1
        r'{"replies":{.*?}}',                       # 备选2
        r'{"count":\d+,"size":\d+,"current":\d+,"total":\d+,"list":\[.*?\]}'  # 备选3
    ]
    
    replies_data = None
    for pattern in json_patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                json_str = match.group(1)
                # 修复JSON格式（处理转义问题）
                json_str = json_str.replace(r'\\"', '"').replace(r'\\/', '/')
                data = json.loads(json_str)
                
                # 查找replies字段
                if "replies" in data:
                    replies_data = data["replies"]
                    break
                elif "list" in data and "count" in data:
                    replies_data = data
                    break
            except json.JSONDecodeError as e:
                print(f"⚠️ 解析JSON失败（{pattern}）：{str(e)}")
                continue
    
    if not replies_data:
        print(f"❌ 未找到replies数据")
        # 打印关键片段辅助排查
        print(f"\n📌 关键片段（前2000字符）：")
        print(html[:2000])
        return None
    
    # 第二步：解析replies数据
    print(f"✅ 成功提取replies数据：")
    print(f"- count: {replies_data.get('count', '未知')}")
    print(f"- current: {replies_data.get('current', '未知')}")
    print(f"- total: {replies_data.get('total', '未知')}")
    print(f"- list长度: {len(replies_data.get('list', []))}")
    
    # 第三步：筛选目标euid的回复
    target_euid = TARGET_CONFIG["user_euid"]
    reply_list = replies_data.get("list", [])
    target_replies = []
    
    for reply in reply_list:
        try:
            # 提取author中的euid
            author = reply.get("author", {})
            euid = author.get("euid", "")
            if euid == target_euid:
                # 清理内容
                content = reply.get("content", "")
                content = re.sub(r'<.*?>', '', content)  # 移除HTML标签
                
                target_replies.append({
                    "pid": reply.get("pid", ""),
                    "euid": euid,
                    "username": author.get("puname", ""),
                    "time": reply.get("createdAtFormat", ""),
                    "content": content.strip()
                })
        except Exception as e:
            print(f"⚠️ 解析单条回复失败：{str(e)}")
            continue
    
    print(f"\n🎯 匹配到目标euid({target_euid})的回复数：{len(target_replies)}")
    for idx, reply in enumerate(target_replies):
        print(f"\n--- 回复 {idx+1} ---")
        print(f"PID: {reply['pid']}")
        print(f"用户: {reply['username']} ({reply['euid']})")
        print(f"时间: {reply['time']}")
        print(f"内容: {reply['content'][:200]}..." if len(reply['content']) > 200 else reply['content'])
    
    return target_replies

# ==================== 主函数 ====================
def main():
    print(f"\n🚀 虎扑数据提取工具启动 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 调用curl获取100%一致的HTML
    html = run_curl_and_get_html()
    
    # 2. 从HTML中提取replies数据
    if html:
        extract_replies_from_html(html)
    
    print(f"\n🛑 工具运行结束")

if __name__ == "__main__":
    main()
