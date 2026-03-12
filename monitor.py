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
        
        return full_html
    except subprocess.CalledProcessError as e:
        print(f"❌ curl执行失败：{e.stderr}")
        return None
    except Exception as e:
        print(f"❌ 执行curl出错：{str(e)}")
        return None

def extract_replies_from_html(html):
    """从HTML中提取__NEXT_DATA__中的replies数据（核心）"""
    if not html:
        print(f"❌ 无HTML内容可解析")
        return None
    
    print(f"\n=====================================")
    print(f"🔍 提取__NEXT_DATA__中的replies数据：")
    print(f"=====================================")
    
    # 匹配<script id="__NEXT_DATA__" type="application/json">标签内的内容
    next_data_pattern = r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>'
    match = re.search(next_data_pattern, html, re.DOTALL)
    
    if not match:
        print(f"❌ 未找到__NEXT_DATA__脚本标签")
        # 打印关键片段辅助排查
        print(f"\n📌 搜索__NEXT_DATA__相关片段：")
        # 搜索包含__NEXT_DATA__的行
        lines = html.split("\n")
        for idx, line in enumerate(lines[:100]):  # 只看前100行
            if "__NEXT_DATA__" in line:
                print(f"行{idx+1}：{line.strip()}")
        return None
    
    try:
        # 获取JSON字符串并清理
        json_str = match.group(1).strip()
        # 修复可能的转义问题
        json_str = json_str.replace(r'\u003c', '<').replace(r'\u003e', '>').replace(r'\\', '\\')
        
        # 解析JSON数据
        next_data = json.loads(json_str)
        
        # 按路径提取replies数据：props.pageProps.detail.replies
        try:
            # 逐层获取，避免KeyError
            props = next_data.get("props", {})
            page_props = props.get("pageProps", {})
            detail = page_props.get("detail", {})
            replies_data = detail.get("replies", {})
            
            if not replies_data:
                print(f"❌ 在__NEXT_DATA__中未找到props.pageProps.detail.replies")
                print(f"📌 detail内容：{json.dumps(detail, ensure_ascii=False, indent=2)[:500]}...")
                return None
            
            # 打印replies基础信息
            print(f"✅ 成功提取replies数据：")
            print(f"- count: {replies_data.get('count', '未知')}")
            print(f"- size: {replies_data.get('size', '未知')}")
            print(f"- current: {replies_data.get('current', '未知')}")
            print(f"- total: {replies_data.get('total', '未知')}")
            print(f"- list长度: {len(replies_data.get('list', []))}")
            
            # 筛选目标euid的回复（包括主回复和引用回复中的目标euid）
            target_euid = TARGET_CONFIG["user_euid"]
            reply_list = replies_data.get("list", [])
            target_replies = []
            
            for reply in reply_list:
                try:
                    # 检查主回复作者的euid
                    main_author = reply.get("author", {})
                    main_euid = main_author.get("euid", "")
                    
                    # 检查引用回复作者的euid
                    quote_author = reply.get("quote", {}).get("author", {})
                    quote_euid = quote_author.get("euid", "")
                    
                    # 收集目标euid的回复（主回复或引用回复匹配都算）
                    matched_author = None
                    if main_euid == target_euid:
                        matched_author = main_author
                        content = reply.get("content", "")
                        reply_type = "主回复"
                    elif quote_euid == target_euid:
                        matched_author = quote_author
                        content = reply.get("quote", {}).get("content", "")
                        reply_type = "引用回复"
                    else:
                        continue
                    
                    # 清理HTML标签
                    content = re.sub(r'<.*?>', '', content)
                    # 处理Unicode转义
                    content = content.encode('utf-8').decode('unicode_escape')
                    
                    target_replies.append({
                        "pid": reply.get("pid", ""),
                        "euid": target_euid,
                        "username": matched_author.get("puname", ""),
                        "time": reply.get("createdAtFormat", "") or reply.get("quote", {}).get("createdAtFormat", ""),
                        "content": content.strip(),
                        "reply_type": reply_type,
                        "location": reply.get("location", "")
                    })
                except Exception as e:
                    print(f"⚠️ 解析单条回复失败：{str(e)}")
                    continue
            
            print(f"\n🎯 匹配到目标euid({target_euid})的回复数：{len(target_replies)}")
            for idx, reply in enumerate(target_replies):
                print(f"\n--- 回复 {idx+1} ({reply['reply_type']}) ---")
                print(f"PID: {reply['pid']}")
                print(f"用户: {reply['username']} ({reply['euid']})")
                print(f"时间: {reply['time']}")
                print(f"位置: {reply['location']}")
                print(f"内容: {reply['content'][:200]}..." if len(reply['content']) > 200 else reply['content'])
            
            # 保存提取的目标回复到JSON文件
            with open("target_replies.json", "w", encoding="utf-8") as f:
                json.dump(target_replies, f, ensure_ascii=False, indent=2)
            print(f"\n✅ 目标回复已保存到：target_replies.json")
            
            return target_replies
            
        except Exception as e:
            print(f"❌ 提取replies路径失败：{str(e)}")
            # 打印完整的__NEXT_DATA__结构（前1000字符）
            print(f"\n📌 __NEXT_DATA__结构预览：")
            print(json.dumps(next_data, ensure_ascii=False, indent=2)[:1000] + "...")
            return None
            
    except json.JSONDecodeError as e:
        print(f"❌ 解析__NEXT_DATA__ JSON失败：{str(e)}")
        print(f"📌 原始JSON字符串前500字符：{json_str[:500]}...")
        return None

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
