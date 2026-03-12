import json
import re
import subprocess
import os
import time
import requests
import sys

# ==================== 【核心配置：多帖子 + 多用户】 ====================
MONITOR_TARGETS = [
    {
        "thread_id": "636748637",       # 帖子ID
        "target_euid": "20829162237257", # 要监控的用户EUIN
        "name": "赫萝Horoo"                  # 备注名（推送时显示）
    },
    {
        "thread_id": "636748637",
        "target_euid": "197319743786161",
        "name": "二号机"
    }
]

# 通用配置
CONFIG = {
    "bark_key": os.environ.get("BARK_KEY", ""),
    "state_file": "reply_push_state.json",
    "state_save_path": "./"  # 确保状态文件保存路径可写
}

# 请求头模板
CURL_TEMPLATE = '''curl 'https://bbs.hupu.com/{thread_id}_{euid}-1.html' \
  -H 'accept: text/html,application/xhtml+xml,application/xml;q=0.9' \
  -H 'accept-language: zh-CN,zh;q=0.9,en;q=0.8' \
  -H 'sec-ch-ua: "Not:A-Brand";v="99","Google Chrome";v="145"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-platform: "macOS"' \
  -H 'sec-fetch-dest: document' \
  -H 'sec-fetch-mode: navigate' \
  -H 'sec-fetch-site: same-origin' \
  -H 'upgrade-insecure-requests: 1' \
  -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36' \
  --silent --show-error'''

# ==================== 状态管理（彻底修复保存问题） ====================
def get_state_file_path():
    """获取状态文件完整路径"""
    return os.path.join(CONFIG["state_save_path"], CONFIG["state_file"])

def load_push_state():
    """加载推送状态（增强容错+强制路径）"""
    default_state = {
        "pushed_pids": [],
        "first_run": True,
        "last_check_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "targets_last_page": {}  # 记录每个目标的最后页数
    }
    
    state_file = get_state_file_path()
    print(f"\n📂 状态文件路径: {state_file}")
    
    # 检查文件是否存在
    if os.path.exists(state_file):
        try:
            # 强制以UTF-8编码读取
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            
            # 补充缺失字段
            for key, value in default_state.items():
                if key not in state:
                    state[key] = value
            
            print(f"✅ 加载状态成功 | 已推送: {len(state['pushed_pids'])} 条 | 首次运行: {state['first_run']}")
            return state
            
        except json.JSONDecodeError:
            print(f"⚠️ 状态文件损坏，使用默认状态")
            return default_state
        except Exception as e:
            print(f"⚠️ 加载状态失败: {e}，使用默认状态")
            return default_state
    else:
        print(f"⚠️ 状态文件不存在，创建新状态")
        return default_state

def save_push_state(state):
    """保存推送状态（强制写入+权限检查）"""
    state_file = get_state_file_path()
    
    # 更新最后检查时间
    state["last_check_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        # 强制以UTF-8编码写入，确保兼容性
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        
        # 验证是否保存成功
        if os.path.exists(state_file):
            file_size = os.path.getsize(state_file)
            print(f"✅ 状态保存成功 | 文件大小: {file_size} 字节")
        else:
            print(f"❌ 状态文件创建失败")
            
    except PermissionError:
        print(f"❌ 没有写入权限，状态保存失败")
    except Exception as e:
        print(f"❌ 保存状态失败: {e}")

# ==================== 内容清理（彻底移除所有HTML标签） ====================
def clean_content(content):
    """超强清理：移除所有HTML标签、转义字符、特殊符号"""
    if not content or content.strip() == "":
        return "无内容"
    
    # 1. 移除所有HTML标签（包括<p>、</p>、<img>等）
    content = re.sub(r'<[^>]+>', '', content)
    
    # 2. 移除Unicode编码的HTML标签（\u003c = <, \u003e = >）
    content = re.sub(r'\\u003c[^\\]+\\u003e', '', content)
    
    # 3. 移除转义字符
    content = content.replace('\\n', '').replace('\\r', '').replace('\\t', '')
    
    # 4. 移除特殊符号
    content = content.replace('\\', '').replace('"', '').replace("'", '')
    content = content.replace('&nbsp;', '').replace('&amp;', '&')
    
    # 5. 移除URL链接
    content = re.sub(r'https?://\S+', '', content)
    
    # 6. 清理多余空格
    content = re.sub(r'\s+', ' ', content).strip()
    
    # 7. 兜底：如果清理后为空
    if not content:
        return "无内容"
    
    return content

# ==================== 提取 replies ====================
def extract_replies(html):
    """提取并解析replies数据"""
    if not html:
        return None
    
    try:
        # 提取__NEXT_DATA__
        match = re.search(r'<script id="__NEXT_DATA__".*?>(.*?)</script>', html, re.DOTALL)
        if not match:
            return None
        
        # 解析JSON
        next_data = json.loads(match.group(1))
        replies_data = next_data.get("props", {}) \
                               .get("pageProps", {}) \
                               .get("detail", {}) \
                               .get("replies", None)
        
        if replies_data and isinstance(replies_data, dict):
            return replies_data
            
    except Exception as e:
        print(f"⚠️ JSON解析失败: {str(e)[:50]}")

    # 降级方案：正则提取
    try:
        # 提取replies整体
        replies_match = re.search(r'"replies"\s*:\s*({.*?"list"\s*:\s*\[.*?\].*?})', html, re.DOTALL)
        if not replies_match:
            return None
        
        replies_raw = replies_match.group(1)
        replies_dict = {
            "current": 0,
            "total": 0,
            "list": []
        }
        
        # 提取分页信息
        current_match = re.search(r'"current"\s*:\s*(\d+)', replies_raw)
        total_match = re.search(r'"total"\s*:\s*(\d+)', replies_raw)
        
        if current_match:
            replies_dict["current"] = int(current_match.group(1))
        if total_match:
            replies_dict["total"] = int(total_match.group(1))
        
        # 提取list数据
        list_match = re.search(r'"list"\s*:\s*\[(.*?)\]', replies_raw, re.DOTALL)
        if list_match:
            list_items = re.findall(r'\{.*?"pid"\s*:\s*"[^"]+".*?\}', list_match.group(1))
            
            for item in list_items:
                # 提取核心字段
                pid_match = re.search(r'"pid"\s*:\s*"([^"]+)"', item)
                content_match = re.search(r'"content"\s*:\s*"([^"]+)"', item)
                time_match = re.search(r'"createdAtFormat"\s*:\s*"([^"]+)"', item)
                
                reply_item = {
                    "pid": pid_match.group(1) if pid_match else "",
                    "content": clean_content(content_match.group(1)) if content_match else "",
                    "createdAtFormat": time_match.group(1) if time_match else ""
                }
                
                replies_dict["list"].append(reply_item)
        
        return replies_dict
        
    except Exception as e:
        print(f"⚠️ 正则提取失败: {str(e)[:50]}")
        return None

# ==================== Bark 推送 ====================
def push_bark(title, body):
    """Bark推送（稳定版）"""
    bark_key = CONFIG["bark_key"]
    
    if not bark_key:
        print("⚠️ BARK_KEY 未配置，跳过推送")
        return
    
    try:
        # URL编码，支持中文和特殊字符
        title_encoded = requests.utils.quote(title)
        body_encoded = requests.utils.quote(body)
        
        # 构建推送URL
        push_url = f"https://api.day.app/{bark_key}/{title_encoded}/{body_encoded}"
        
        # 发送请求（超时10秒）
        response = requests.get(
            push_url,
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            }
        )
        
        if response.status_code == 200:
            print("✅ Bark推送成功")
        else:
            print(f"❌ Bark推送失败 | 状态码: {response.status_code}")
            
    except requests.exceptions.Timeout:
        print("❌ Bark推送超时")
    except requests.exceptions.ConnectionError:
        print("❌ Bark推送网络错误")
    except Exception as e:
        print(f"❌ Bark推送异常: {str(e)[:50]}")

# ==================== 监控单个目标 ====================
def monitor_one_target(target, global_state):
    """监控单个目标（帖子+用户）"""
    # 提取目标信息
    thread_id = target["thread_id"]
    euid = target["target_euid"]
    target_name = target["name"]
    target_key = f"{thread_id}_{euid}"  # 唯一标识
    
    print(f"\n{'='*60}")
    print(f"📌 监控目标: {target_name}")
    print(f"🔍 帖子ID: {thread_id} | 用户ID: {euid}")
    print(f"{'='*60}")
    
    # 1. 获取首页数据（获取总页数）
    try:
        curl_cmd = CURL_TEMPLATE.format(thread_id=thread_id, euid=euid)
        result = subprocess.run(
            curl_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        html_content = result.stdout
    except subprocess.TimeoutExpired:
        print("❌ 请求超时，跳过该目标")
        return
    except Exception as e:
        print(f"❌ 请求失败: {str(e)[:50]}")
        return
    
    if not html_content:
        print("❌ 页面内容为空，跳过该目标")
        return
    
    # 2. 提取replies数据
    replies_data = extract_replies(html_content)
    if not replies_data:
        print("❌ 未提取到有效回复数据")
        return
    
    total_pages = replies_data.get("total", 0)
    if total_pages == 0:
        print("ℹ️ 暂无回复数据")
        return
    
    print(f"📊 总页数: {total_pages} | 首次运行: {global_state['first_run']}")
    
    # 3. 处理首次运行逻辑
    if global_state["first_run"]:
        print("\n🔹 首次运行模式：获取最后一页最后3条回复")
        
        # 获取最后一页数据
        try:
            last_page_cmd = CURL_TEMPLATE.format(thread_id=thread_id, euid=euid)
            last_page_cmd = last_page_cmd.replace("-1.html", f"-{total_pages}.html")
            
            last_page_result = subprocess.run(
                last_page_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            last_page_html = last_page_result.stdout
        except Exception as e:
            print(f"❌ 获取最后一页失败: {str(e)[:50]}")
            return
        
        # 提取最后一页回复
        last_page_replies = extract_replies(last_page_html)
        if not last_page_replies or not last_page_replies.get("list"):
            print("ℹ️ 最后一页无回复数据")
            return
        
        reply_list = last_page_replies["list"]
        # 取最后3条
        push_replies = reply_list[-3:] if len(reply_list) >= 3 else reply_list
        
        if push_replies:
            print(f"\n✅ 找到 {len(push_replies)} 条初始回复，开始推送")
            
            # 倒序推送（最新的最后推）
            for reply in reversed(push_replies):
                reply_pid = reply.get("pid")
                if not reply_pid:
                    continue
                
                # 避免重复推送（双重保险）
                if reply_pid in global_state["pushed_pids"]:
                    print(f"ℹ️ 回复 {reply_pid} 已推送，跳过")
                    continue
                
                # 构建推送内容
                push_title = f"【{target_name}】初始回复"
                push_content = f"{reply.get('createdAtFormat', '未知时间')}\n{reply.get('content', '无内容')}"
                
                # 控制台输出
                print(f"\n📤 推送回复 [{reply_pid}]:")
                print(f"   时间: {reply.get('createdAtFormat', '未知时间')}")
                print(f"   内容: {reply.get('content', '无内容')}")
                
                # 推送
                push_bark(push_title, push_content)
                
                # 记录已推送ID（立即添加）
                global_state["pushed_pids"].append(reply_pid)
                
                # 推送间隔，避免限流
                time.sleep(1)
        
        # 记录该目标的最后页数
        global_state["targets_last_page"][target_key] = total_pages
        
    # 4. 非首次运行：检查新回复
    else:
        print("\n🔹 常规监控模式：检查新回复")
        
        # 获取该目标上次的最后页数
        last_checked_page = global_state["targets_last_page"].get(target_key, total_pages)
        # 检查最近3页（防止漏刷）
        check_page_numbers = list(range(total_pages, max(0, total_pages - 3), -1))
        
        new_replies = []
        pushed_pids = global_state["pushed_pids"]
        
        # 遍历检查页面
        for page_num in check_page_numbers:
            print(f"\n📄 检查第 {page_num} 页...")
            
            try:
                # 构建分页请求
                page_cmd = CURL_TEMPLATE.format(thread_id=thread_id, euid=euid)
                page_cmd = page_cmd.replace("-1.html", f"-{page_num}.html")
                
                page_result = subprocess.run(
                    page_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                page_html = page_result.stdout
                
                if not page_html:
                    continue
                
                # 提取该页回复
                page_replies = extract_replies(page_html)
                if not page_replies or not page_replies.get("list"):
                    continue
                
                # 筛选新回复
                for reply in page_replies["list"]:
                    reply_pid = reply.get("pid")
                    if reply_pid and reply_pid not in pushed_pids:
                        new_replies.append(reply)
                        
            except Exception as e:
                print(f"⚠️ 检查第 {page_num} 页失败: {str(e)[:50]}")
                continue
        
        # 推送新回复
        if new_replies:
            print(f"\n✅ 发现 {len(new_replies)} 条新回复")
            
            for reply in new_replies:
                reply_pid = reply.get("pid")
                if not reply_pid:
                    continue
                
                # 构建推送内容
                push_title = f"【{target_name}】新回复"
                push_content = f"{reply.get('createdAtFormat', '未知时间')}\n{reply.get('content', '无内容')}"
                
                # 控制台输出
                print(f"\n📤 推送新回复 [{reply_pid}]:")
                print(f"   时间: {reply.get('createdAtFormat', '未知时间')}")
                print(f"   内容: {reply.get('content', '无内容')}")
                
                # 推送
                push_bark(push_title, push_content)
                
                # 记录已推送
                global_state["pushed_pids"].append(reply_pid)
                
                # 推送间隔
                time.sleep(1)
            
            # 更新该目标的最后页数
            global_state["targets_last_page"][target_key] = total_pages
        else:
            print("\n✅ 暂无新回复")
    
    # 去重已推送ID
    global_state["pushed_pids"] = list(set(global_state["pushed_pids"]))

# ==================== 主程序 ====================
def main():
    """主程序入口"""
    print(f"\n🚀 虎扑多目标监控脚本启动")
    print(f"⏰ 启动时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 监控目标数: {len(MONITOR_TARGETS)}")
    
    # 1. 加载全局状态
    global_state = load_push_state()
    
    # 2. 遍历监控每个目标
    for target in MONITOR_TARGETS:
        monitor_one_target(target, global_state)
    
    # 3. 更新全局状态（首次运行标记改为False）
    if global_state["first_run"]:
        global_state["first_run"] = False
        print(f"\n🔄 首次运行完成，下次将进入常规监控模式")
    
    # 4. 保存状态（关键：确保推送记录被保存）
    save_push_state(global_state)
    
    # 5. 最终统计
    total_pushed = len(global_state["pushed_pids"])
    print(f"\n{'='*60}")
    print(f"🎉 监控任务完成")
    print(f"📊 累计推送回复: {total_pushed} 条")
    print(f"⏰ 下次检查时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + 60))}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
