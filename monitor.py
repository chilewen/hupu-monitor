import json
import re
import subprocess
import os
import time
import requests
from datetime import datetime
import shutil

# ==================== 多帖子多用户配置 ====================
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

# 通用配置（双重缓存路径：tmp + 工作目录）
CONFIG = {
    "bark_key": os.environ.get("BARK_KEY", ""),
    "cache_file_tmp": "/tmp/hupu_monitor_cache.json",
    "cache_file_workdir": "./hupu_monitor_cache.json"  # 工作目录备份
}

# ==================== 缓存管理（双重备份 + 强制保存） ====================
def load_cache():
    """加载缓存：优先读tmp，其次读工作目录，最后默认值"""
    default_cache = {
        "first_run_time": None,
        "pushed_pids": [],
        "last_check_pages": {}
    }
    
    # 优先级1：读取tmp目录缓存
    if os.path.exists(CONFIG["cache_file_tmp"]):
        try:
            with open(CONFIG["cache_file_tmp"], "r", encoding="utf-8") as f:
                cache = json.load(f)
            # 验证缓存完整性
            if "first_run_time" in cache and "pushed_pids" in cache:
                print(f"✅ 从/tmp加载缓存 | 首次运行时间: {cache['first_run_time']} | 已推送: {len(cache['pushed_pids'])}")
                return cache
        except Exception as e:
            print(f"⚠️ /tmp缓存损坏: {e}")
    
    # 优先级2：读取工作目录备份缓存
    if os.path.exists(CONFIG["cache_file_workdir"]):
        try:
            with open(CONFIG["cache_file_workdir"], "r", encoding="utf-8") as f:
                cache = json.load(f)
            print(f"✅ 从工作目录加载缓存 | 首次运行时间: {cache['first_run_time']} | 已推送: {len(cache['pushed_pids'])}")
            return cache
        except Exception as e:
            print(f"⚠️ 工作目录缓存损坏: {e}")
    
    # 优先级3：默认缓存
    print("⚠️ 无有效缓存，使用默认值（首次运行）")
    return default_cache

def save_cache(cache):
    """保存缓存：同时写入tmp + 工作目录（双重备份）"""
    # 1. 写入tmp目录（供cache action读取）
    try:
        with open(CONFIG["cache_file_tmp"], "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        # 验证写入结果
        if os.path.exists(CONFIG["cache_file_tmp"]):
            file_size = os.path.getsize(CONFIG["cache_file_tmp"])
            print(f"✅ /tmp缓存保存成功 | 大小: {file_size} 字节")
        else:
            print("❌ /tmp缓存写入失败")
    except Exception as e:
        print(f"❌ /tmp缓存保存失败: {e}")
    
    # 2. 写入工作目录（备份，防止cache action失效）
    try:
        with open(CONFIG["cache_file_workdir"], "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        print(f"✅ 工作目录缓存备份成功")
        # 将备份文件加入git（可选，确保跨运行保留）
        if os.environ.get("GITHUB_ACTIONS") == "true":
            subprocess.run(["git", "add", CONFIG["cache_file_workdir"]], capture_output=True)
            subprocess.run(["git", "commit", "-m", "Update hupu monitor cache"], capture_output=True)
            subprocess.run(["git", "push", "origin", "main"], capture_output=True)
            print(f"✅ 缓存文件已提交到Git仓库")
    except Exception as e:
        print(f"⚠️ 工作目录缓存备份失败: {e}")

# ==================== 时间处理 ====================
def parse_reply_time(time_str):
    """解析回复时间字符串为时间戳"""
    if not time_str:
        return 0
    
    now = time.time()
    minute_pattern = re.search(r'(\d+)分钟前', time_str)
    hour_pattern = re.search(r'(\d+)小时前', time_str)
    
    if minute_pattern:
        minutes = int(minute_pattern.group(1))
        return now - minutes * 60
    elif hour_pattern:
        hours = int(hour_pattern.group(1))
        return now - hours * 3600
    elif "今天" in time_str:
        time_part = time_str.replace("今天", "").strip()
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            full_time = f"{today} {time_part}"
            return datetime.strptime(full_time, "%Y-%m-%d %H:%M").timestamp()
        except:
            return 0
    elif "昨天" in time_str:
        time_part = time_str.replace("昨天", "").strip()
        try:
            yesterday = (datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            full_time = f"{yesterday} {time_part}"
            return datetime.strptime(full_time, "%Y-%m-%d %H:%M").timestamp()
        except:
            return 0
    else:
        return 0

def is_new_reply(reply_time_ts, first_run_ts):
    """判断是否是首次运行后的新回复"""
    if not first_run_ts:
        return True
    return reply_time_ts > first_run_ts

# ==================== 内容清理 ====================
def clean_content(content):
    """彻底移除HTML标签和特殊字符"""
    if not content:
        return "无内容"
    content = re.sub(r'<[^>]+>', '', content)
    content = re.sub(r'\\u003c.*?\\u003e', '', content)
    content = re.sub(r'https?://\S+', '', content)
    content = content.replace('\\', '').replace('"', '').replace("'", "")
    content = re.sub(r'\s+', ' ', content).strip()
    return content if content else "无内容"

# ==================== 提取回复数据 ====================
def extract_replies(html):
    """提取回复数据"""
    try:
        match = re.search(r'<script id="__NEXT_DATA__".*?>(.*?)</script>', html, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            replies = data.get("props", {}).get("pageProps", {}).get("detail", {}).get("replies")
            if replies and isinstance(replies, dict):
                clean_list = []
                for item in replies.get("list", []):
                    clean_item = {
                        "pid": item.get("pid", ""),
                        "content": clean_content(item.get("content", "")),
                        "createdAtFormat": item.get("createdAtFormat", ""),
                        "time_ts": parse_reply_time(item.get("createdAtFormat", ""))
                    }
                    clean_list.append(clean_item)
                replies["list"] = clean_list
                return replies
    except:
        pass

    try:
        replies_match = re.search(r'"replies"\s*:\s*({.*?"list"\s*:\s*\[.*?\].*?})', html, re.DOTALL)
        if not replies_match:
            return None
        
        raw = replies_match.group(1)
        result = {
            "current": 0,
            "total": 0,
            "list": []
        }
        
        current_match = re.search(r'"current"\s*:\s*(\d+)', raw)
        total_match = re.search(r'"total"\s*:\s*(\d+)', raw)
        if current_match:
            result["current"] = int(current_match.group(1))
        if total_match:
            result["total"] = int(total_match.group(1))
        
        list_items = re.findall(r'\{.*?"pid"\s*:\s*"[^"]+".*?\}', raw)
        for item in list_items:
            pid = re.search(r'"pid"\s*:\s*"([^"]+)"', item)
            content = re.search(r'"content"\s*:\s*"([^"]+)"', item)
            time_str = re.search(r'"createdAtFormat"\s*:\s*"([^"]+)"', item)
            
            clean_item = {
                "pid": pid.group(1) if pid else "",
                "content": clean_content(content.group(1)) if content else "",
                "createdAtFormat": time_str.group(1) if time_str else "",
                "time_ts": parse_reply_time(time_str.group(1) if time_str else "")
            }
            result["list"].append(clean_item)
        
        return result
    except:
        return None

# ==================== Bark推送 ====================
def push_bark(title, content):
    """Bark推送"""
    if not CONFIG["bark_key"]:
        print("⚠️ BARK_KEY未配置")
        return
    try:
        title_enc = requests.utils.quote(title)
        content_enc = requests.utils.quote(content)
        url = f"https://api.day.app/{CONFIG['bark_key']}/{title_enc}/{content_enc}"
        requests.get(url, timeout=5)
        print("✅ Bark推送成功")
    except Exception as e:
        print(f"❌ Bark推送失败: {e}")

# ==================== 监控单个目标 ====================
def monitor_target(target, cache):
    """监控单个目标（只处理新回复）"""
    thread_id = target["thread_id"]
    euid = target["target_euid"]
    name = target["name"]
    target_key = f"{thread_id}_{euid}"
    
    print(f"\n{'='*50}")
    print(f"📌 监控目标: {name}")
    print(f"🔍 帖子ID: {thread_id}")
    print(f"{'='*50}")
    
    cmd = f'''curl 'https://bbs.hupu.com/{thread_id}_{euid}-1.html' \
      -H 'User-Agent: Mozilla/5.0' --silent --show-error'''
    try:
        html = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20).stdout
        replies_data = extract_replies(html)
        if not replies_data:
            print("❌ 未提取到回复数据")
            return
        
        total_pages = replies_data.get("total", 0)
        if total_pages == 0:
            print("ℹ️ 暂无回复")
            return
        
        # 强制验证首次运行状态（关键修复）
        first_run = cache["first_run_time"] is None or cache["first_run_time"] == ""
        print(f"📊 总页数: {total_pages} | 首次运行: {first_run}")
        print(f"📝 已推送ID数: {len(cache['pushed_pids'])}")
        if not first_run:
            print(f"⏰ 首次运行时间: {datetime.fromtimestamp(cache['first_run_time']).strftime('%Y-%m-%d %H:%M:%S')}")
        
        new_replies = []
        if first_run:
            print("\n🔹 首次运行：记录初始状态 + 推送最后3条")
            # 强制设置首次运行时间（当前时间戳，确保是数字）
            cache["first_run_time"] = float(time.time())
            print(f"⏰ 首次运行时间已记录: {datetime.fromtimestamp(cache['first_run_time']).strftime('%Y-%m-%d %H:%M:%S')}")
            
            last_page_cmd = f'''curl 'https://bbs.hupu.com/{thread_id}_{euid}-{total_pages}.html' \
              -H 'User-Agent: Mozilla/5.0' --silent --show-error'''
            last_page_html = subprocess.run(last_page_cmd, shell=True, capture_output=True, text=True, timeout=20).stdout
            last_page_replies = extract_replies(last_page_html)
            
            if last_page_replies and last_page_replies.get("list"):
                reply_list = last_page_replies["list"]
                init_replies = reply_list[-3:] if len(reply_list) >= 3 else reply_list
                
                for reply in reversed(init_replies):
                    pid = reply.get("pid")
                    if not pid or pid in cache["pushed_pids"]:
                        continue
                    push_title = f"【{name}】初始回复"
                    push_content = f"{reply['createdAtFormat']}\n{reply['content']}"
                    print(f"\n📤 推送初始回复:")
                    print(f"   时间: {reply['createdAtFormat']}")
                    print(f"   内容: {reply['content']}")
                    push_bark(push_title, push_content)
                    cache["pushed_pids"].append(pid)
            
            cache["last_check_pages"][target_key] = total_pages
            # 立即保存缓存（首次运行后强制保存）
            save_cache(cache)
            return
        
        # 非首次运行逻辑
        print("\n🔹 常规监控：只检查新回复")
        last_checked_page = cache["last_check_pages"].get(target_key, total_pages)
        pages_to_check = range(total_pages, last_checked_page, -1)
        
        if not pages_to_check:
            print("ℹ️ 无新增页数，检查最后一页是否有新回复")
            pages_to_check = [total_pages]
        
        for page_num in pages_to_check:
            print(f"\n📄 检查新增页数: {page_num}")
            page_cmd = f'''curl 'https://bbs.hupu.com/{thread_id}_{euid}-{page_num}.html' \
              -H 'User-Agent: Mozilla/5.0' --silent --show-error'''
            page_html = subprocess.run(page_cmd, shell=True, capture_output=True, text=True, timeout=20).stdout
            page_replies = extract_replies(page_html)
            
            if not page_replies or not page_replies.get("list"):
                continue
            
            for reply in page_replies["list"]:
                pid = reply.get("pid")
                if not pid:
                    continue
                if pid in cache["pushed_pids"]:
                    continue
                if not is_new_reply(reply["time_ts"], cache["first_run_time"]):
                    continue
                new_replies.append(reply)
        
        if new_replies:
            print(f"\n✅ 发现 {len(new_replies)} 条新回复（首次运行后发布）")
            for reply in new_replies:
                pid = reply.get("pid")
                push_title = f"【{name}】新回复"
                push_content = f"{reply['createdAtFormat']}\n{reply['content']}"
                print(f"\n📤 推送新回复:")
                print(f"   时间: {reply['createdAtFormat']}")
                print(f"   内容: {reply['content']}")
                push_bark(push_title, push_content)
                cache["pushed_pids"].append(pid)
                time.sleep(0.5)
        else:
            print("\n✅ 无首次运行后的新回复")
        
        cache["last_check_pages"][target_key] = total_pages
        
    except Exception as e:
        print(f"❌ 监控失败: {e}")
        import traceback
        traceback.print_exc()
    
    cache["pushed_pids"] = list(set(cache["pushed_pids"]))

# ==================== 主程序 ====================
def main():
    """主程序"""
    print(f"\n🚀 虎扑新回复监控启动")
    print(f"⏰ 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 监控目标数: {len(MONITOR_TARGETS)}")
    print(f"💻 GitHub Actions环境: {os.environ.get('GITHUB_ACTIONS', 'false')}")
    
    # 加载缓存
    cache = load_cache()
    
    # 遍历监控每个目标
    for target in MONITOR_TARGETS:
        monitor_target(target, cache)
    
    # 最终保存缓存
    save_cache(cache)
    
    # 最终统计
    print(f"\n{'='*50}")
    print(f"🎉 监控完成")
    print(f"📊 累计推送: {len(cache['pushed_pids'])} 条")
    first_run = cache["first_run_time"] is None or cache["first_run_time"] == ""
    if not first_run:
        print(f"⏰ 首次运行时间: {datetime.fromtimestamp(cache['first_run_time']).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
