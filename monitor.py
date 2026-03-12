import json
import re
import subprocess
import os
import time

# ==================== 配置项 ====================
CONFIG = {
    "thread_id": "636748637",
    "target_euid": "20829162237257",
    "page_num": 21,
    "state_file": "reply_push_state.json"  # 记录推送状态的文件
}

# CURL请求命令
CURL_TEMPLATE = '''curl 'https://bbs.hupu.com/{thread_id}_{euid}-{page_num}.html' \
  -H 'accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7' \
  -H 'accept-language: zh-CN,zh;q=0.9,en;q=0.8' \
  -H 'sec-ch-ua: "Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-platform: "macOS"' \
  -H 'sec-fetch-dest: document' \
  -H 'sec-fetch-mode: navigate' \
  -H 'sec-fetch-site: same-origin' \
  -H 'upgrade-insecure-requests: 1' \
  -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36' \
  --silent --show-error'''

# ==================== 核心功能函数 ====================
def load_push_state():
    """加载推送状态（记录已推送的回复ID）- 增加容错处理"""
    default_state = {
        "pushed_pids": [],
        "first_run": True,
        "last_total_page": 0,
        "last_check_time": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    if os.path.exists(CONFIG["state_file"]):
        try:
            with open(CONFIG["state_file"], "r", encoding="utf-8") as f:
                state = json.load(f)
            # 补充缺失的字段
            for key, value in default_state.items():
                if key not in state:
                    state[key] = value
            return state
        except Exception as e:
            print(f"⚠️ 加载状态文件失败: {e}，使用默认状态")
            return default_state
    return default_state

def save_push_state(state):
    """保存推送状态"""
    try:
        state["last_check_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(CONFIG["state_file"], "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 保存状态文件失败: {e}")

def clean_content_for_json(content):
    """仅清理content字段，确保JSON可解析"""
    if not content:
        return ""
    
    # 1. 移除HTML标签（包括Unicode编码）
    content = re.sub(r'\\u003c[^\\]+\\u003e', '', content)  # \u003c/p\u003e 等
    content = re.sub(r'<[^>]+>', '', content)  # <p>、<img>等标签
    
    # 2. 移除URL和特殊字符
    content = re.sub(r'https?://[^"]+', '', content)  # 移除图片URL
    content = content.replace('\\', '')  # 移除反斜杠
    content = content.replace('"', '')   # 移除双引号（避免JSON解析错误）
    
    # 3. 清理空白字符
    content = re.sub(r'\s+', ' ', content).strip()
    
    return content

def extract_replies_data(html):
    """精准提取props.pageProps.detail.replies数据"""
    # 第一步：提取__NEXT_DATA__完整内容
    next_data_pattern = r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>'
    next_data_match = re.search(next_data_pattern, html, re.DOTALL)
    
    if not next_data_match:
        return None
    
    next_data_str = next_data_match.group(1).strip()
    
    # 第二步：解析完整的NEXT_DATA（容错处理）
    try:
        next_data = json.loads(next_data_str)
        # 精准定位到replies数据
        replies_data = next_data.get("props", {}) \
                               .get("pageProps", {}) \
                               .get("detail", {}) \
                               .get("replies", None)
        return replies_data
    except:
        # JSON解析失败时，用正则精准提取replies部分
        replies_pattern = r'"replies"\s*:\s*({[^}]*?"count"\s*:\s*\d+[^}]*?"size"\s*:\s*\d+[^}]*?"current"\s*:\s*\d+[^}]*?"total"\s*:\s*\d+[^}]*?"list"\s*:\s*\[(.*?)\]\s*[^}]*})'
        replies_match = re.search(replies_pattern, next_data_str, re.DOTALL)
        
        if not replies_match:
            return None
        
        # 构建基础replies结构
        replies_raw = replies_match.group(1)
        replies_dict = {
            "count": 0,
            "size": 0,
            "current": 0,
            "total": 0,
            "list": []
        }
        
        # 提取基础信息
        count_match = re.search(r'"count"\s*:\s*(\d+)', replies_raw)
        size_match = re.search(r'"size"\s*:\s*(\d+)', replies_raw)
        current_match = re.search(r'"current"\s*:\s*(\d+)', replies_raw)
        total_match = re.search(r'"total"\s*:\s*(\d+)', replies_raw)
        
        if count_match: replies_dict["count"] = int(count_match.group(1))
        if size_match: replies_dict["size"] = int(size_match.group(1))
        if current_match: replies_dict["current"] = int(current_match.group(1))
        if total_match: replies_dict["total"] = int(total_match.group(1))
        
        # 提取并处理list数据（核心：仅处理list部分）
        list_pattern = r'"list"\s*:\s*\[(.*?)\]\s*[,}]'
        list_match = re.search(list_pattern, replies_raw, re.DOTALL)
        
        if list_match:
            list_str = list_match.group(1)
            # 分割每条回复
            reply_items = re.findall(r'\{[^}]*"pid"\s*:\s*"[^"]+"[^}]*\}', list_str)
            
            for item in reply_items:
                reply = {}
                # 提取核心字段
                pid_match = re.search(r'"pid"\s*:\s*"([^"]+)"', item)
                content_match = re.search(r'"content"\s*:\s*"([^"]+)"', item)
                time_match = re.search(r'"createdAtFormat"\s*:\s*"([^"]+)"', item)
                
                if pid_match: reply["pid"] = pid_match.group(1)
                if time_match: reply["createdAtFormat"] = time_match.group(1)
                if content_match: 
                    # 仅清理content字段，不影响其他内容
                    reply["content"] = clean_content_for_json(content_match.group(1))
                
                replies_dict["list"].append(reply)
        
        return replies_dict

def fetch_page_html(page_num):
    """获取指定页码的HTML内容"""
    curl_cmd = CURL_TEMPLATE.format(
        thread_id=CONFIG["thread_id"],
        euid=CONFIG["target_euid"],
        page_num=page_num
    )
    
    try:
        result = subprocess.run(
            curl_cmd,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8"
        )
        return result.stdout
    except Exception as e:
        print(f"❌ 获取第{page_num}页失败: {e}")
        return None

def push_reply(reply):
    """推送单条回复（可自定义推送逻辑）"""
    print(f"\n📤 推送回复 [{reply.get('pid', '未知')}]：")
    print(f"   时间: {reply.get('createdAtFormat', '未知')}")
    print(f"   内容: {reply.get('content', '无内容')}")
    # 这里可以添加实际的推送逻辑（如发送到微信、钉钉等）
    time.sleep(0.5)  # 模拟推送延迟

def main():
    """主逻辑：首次取最后3条，非首次逐条推送未推送内容"""
    print("🚀 开始提取并推送回复数据...")
    
    # 加载推送状态（修复KeyError的核心）
    state = load_push_state()
    # 安全获取字段，避免KeyError
    first_run = state.get("first_run", True)
    pushed_pids = state.get("pushed_pids", [])
    last_total_page = state.get("last_total_page", 0)
    
    # 第一步：获取第一页数据，拿到总页数
    first_page_html = fetch_page_html(CONFIG["page_num"])
    if not first_page_html:
        print("❌ 无法获取初始页面数据")
        return
    
    first_replies = extract_replies_data(first_page_html)
    if not first_replies:
        print("❌ 无法提取replies数据")
        return
    
    total_pages = first_replies.get("total", 0)
    print(f"📊 数据概览：总页数={total_pages}, 当前页={first_replies.get('current', 0)}, 总回复数={first_replies.get('count', 0)}")
    
    # 第二步：处理首次运行逻辑（获取最后一页的最后3条）
    all_replies = []
    if first_run:
        print("\n🔹 首次运行模式：获取最后一页的最后3条回复")
        
        # 获取最后一页数据
        if total_pages > 0:
            last_page_html = fetch_page_html(total_pages)
            if last_page_html:
                last_replies = extract_replies_data(last_page_html)
                if last_replies and last_replies.get("list", []):
                    # 取最后3条
                    reply_list = last_replies.get("list", [])
                    last_3_replies = reply_list[-3:] if len(reply_list) >=3 else reply_list
                    
                    print(f"\n✅ 找到最后一页的{len(last_3_replies)}条回复，开始推送：")
                    for reply in reversed(last_3_replies):  # 倒序推送（最新的最后推）
                        push_reply(reply)
                        pid = reply.get("pid")
                        if pid and pid not in pushed_pids:
                            pushed_pids.append(pid)
        
        # 更新状态：首次运行完成
        state["first_run"] = False
        state["last_total_page"] = total_pages
    
    # 第三步：非首次运行，逐条推送未推送内容
    else:
        print("\n🔹 常规运行模式：推送未推送的新回复")
        
        # 遍历所有页面（从最后记录的页数开始）
        start_page = last_total_page
        new_replies = []
        
        # 先检查最后一页（最新回复）
        if total_pages > 0:
            for page in range(total_pages, max(0, start_page-2), -1):
                page_html = fetch_page_html(page)
                if not page_html:
                    continue
                
                page_replies = extract_replies_data(page_html)
                if not page_replies or not page_replies.get("list", []):
                    continue
                
                # 筛选未推送的回复
                for reply in page_replies.get("list", []):
                    pid = reply.get("pid")
                    if pid and pid not in pushed_pids:
                        new_replies.append(reply)
        
        # 按时间正序推送（旧的先推）
        if new_replies:
            print(f"\n✅ 找到{len(new_replies)}条未推送的回复，开始逐条推送：")
            for reply in new_replies:
                push_reply(reply)
                pid = reply.get("pid")
                if pid and pid not in pushed_pids:
                    pushed_pids.append(pid)
                state["last_total_page"] = total_pages
        else:
            print("\n✅ 暂无新回复需要推送")
    
    # 保存最新状态
    state["pushed_pids"] = list(set(pushed_pids))  # 去重
    save_push_state(state)
    
    print(f"\n🎉 任务完成！累计推送{len(pushed_pids)}条回复")

if __name__ == "__main__":
    main()
