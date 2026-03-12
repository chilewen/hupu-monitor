import json
import re
import subprocess
import os
import time
import requests
from datetime import datetime

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

# 通用配置
CONFIG = {
    "bark_key": os.environ.get("BARK_KEY", ""),
    "cache_file": "/tmp/hupu_monitor_cache.json"
}

# ==================== 缓存管理（记录首次运行时间+已推送ID） ====================
def load_cache():
    """加载缓存：首次运行时间 + 已推送ID"""
    default_cache = {
        "first_run_time": None,  # 首次运行时间戳
        "pushed_pids": [],       # 已推送的回复ID
        "last_check_pages": {}   # 每个目标最后检查到的页数
    }
    
    if os.path.exists(CONFIG["cache_file"]):
        try:
            with open(CONFIG["cache_file"], "r", encoding="utf-8") as f:
                cache = json.load(f)
            # 补充缺失字段
            for key, value in default_cache.items():
                if key not in cache:
                    cache[key] = value
            return cache
        except:
            return default_cache
    return default_cache

def save_cache(cache):
    """保存缓存"""
    try:
        with open(CONFIG["cache_file"], "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        print(f"✅ 缓存保存成功 | 已推送ID数: {len(cache['pushed_pids'])}")
    except Exception as e:
        print(f"❌ 缓存保存失败: {e}")

# ==================== 时间处理（判断是否是新回复） ====================
def parse_reply_time(time_str):
    """解析回复时间字符串为时间戳"""
    if not time_str:
        return 0
    
    # 虎扑时间格式：X分钟前、X小时前、今天 X:XX、昨天 X:XX
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
        # 今天 X:XX → 转换为今天的时间戳
        time_part = time_str.replace("今天", "").strip()
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            full_time = f"{today} {time_part}"
            return datetime.strptime(full_time, "%Y-%m-%d %H:%M").timestamp()
        except:
            return 0
    elif "昨天" in time_str:
        # 昨天 X:XX → 转换为昨天的时间戳
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
        return True  # 首次运行时所有回复都算新的
    # 回复时间在首次运行时间之后 → 新回复
    return reply_time_ts > first_run_ts

# ==================== 内容清理 ====================
def clean_content(content):
    """彻底移除HTML标签和特殊字符"""
    if not content:
        return "无内容"
    content = re.sub(r'<[^>]+>', '', content)       # 移除HTML标签
    content = re.sub(r'\\u003c.*?\\u003e', '', content)  # 移除Unicode编码标签
    content = re.sub(r'https?://\S+', '', content)  # 移除URL
    content = content.replace('\\', '').replace('"', '').replace("'", "")
    content = re.sub(r'\s+', ' ', content).strip()
    return content if content else "无内容"

# ==================== 提取回复数据 ====================
def extract_replies(html):
    """提取回复数据"""
    try:
        # 提取NEXT_DATA
        match = re.search(r'<script id="__NEXT_DATA__".*?>(.*?)</script>', html, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            replies = data.get("props", {}).get("pageProps", {}).get("detail", {}).get("replies")
            if replies and isinstance(replies, dict):
                # 处理回复列表
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

    # 降级正则提取
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
        
        # 提取分页信息
        current_match = re.search(r'"current"\s*:\s*(\d+)', raw)
        total_match = re.search(r'"total"\s*:\s*(\d+)', raw)
        if current_match:
            result["current"] = int(current_match.group(1))
        if total_match:
            result["total"] = int(total_match.group(1))
        
        # 提取回复列表
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
    
    # 1. 获取首页数据（总页数）
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
        
        first_run = cache["first_run_time"] is None
        print(f"📊 总页数: {total_pages} | 首次运行: {first_run}")
        
        # 2. 首次运行初始化
        new_replies = []
        if first_run:
            print("\n🔹 首次运行：记录初始状态 + 推送最后3条")
            # 记录首次运行时间（当前时间）
            cache["first_run_time"] = time.time()
            print(f"⏰ 首次运行时间: {datetime.fromtimestamp(cache['first_run_time']).strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 获取最后一页数据
            last_page_cmd = f'''curl 'https://bbs.hupu.com/{thread_id}_{euid}-{total_pages}.html' \
              -H 'User-Agent: Mozilla/5.0' --silent --show-error'''
            last_page_html = subprocess.run(last_page_cmd, shell=True, capture_output=True, text=True, timeout=20).stdout
            last_page_replies = extract_replies(last_page_html)
            
            if last_page_replies and last_page_replies.get("list"):
                reply_list = last_page_replies["list"]
                # 取最后3条作为初始推送
                init_replies = reply_list[-3:] if len(reply_list) >= 3 else reply_list
                
                for reply in reversed(init_replies):
                    pid = reply.get("pid")
                    if not pid or pid in cache["pushed_pids"]:
                        continue
                    # 推送初始回复
                    push_title = f"【{name}】初始回复"
                    push_content = f"{reply['createdAtFormat']}\n{reply['content']}"
                    print(f"\n📤 推送初始回复:")
                    print(f"   时间: {reply['createdAtFormat']}")
                    print(f"   内容: {reply['content']}")
                    push_bark(push_title, push_content)
                    # 记录已推送
                    cache["pushed_pids"].append(pid)
            
            # 记录最后检查页数
            cache["last_check_pages"][target_key] = total_pages
            return
        
        # 3. 非首次运行：只检查新增页数 + 新时间回复
        print("\n🔹 常规监控：只检查新回复")
        last_checked_page = cache["last_check_pages"].get(target_key, total_pages)
        # 只检查新增的页数（当前总页数 - 上次检查页数）
        pages_to_check = range(total_pages, last_checked_page, -1)
        
        if not pages_to_check:
            print("ℹ️ 无新增页数，检查最后一页是否有新回复")
            pages_to_check = [total_pages]
        
        # 遍历需要检查的页数
        for page_num in pages_to_check:
            print(f"\n📄 检查新增页数: {page_num}")
            page_cmd = f'''curl 'https://bbs.hupu.com/{thread_id}_{euid}-{page_num}.html' \
              -H 'User-Agent: Mozilla/5.0' --silent --show-error'''
            page_html = subprocess.run(page_cmd, shell=True, capture_output=True, text=True, timeout=20).stdout
            page_replies = extract_replies(page_html)
            
            if not page_replies or not page_replies.get("list"):
                continue
            
            # 筛选：1. 未推送过 2. 首次运行后发布的
            for reply in page_replies["list"]:
                pid = reply.get("pid")
                if not pid:
                    continue
                # 条件1：未推送过
                if pid in cache["pushed_pids"]:
                    continue
                # 条件2：是首次运行后的新回复
                if not is_new_reply(reply["time_ts"], cache["first_run_time"]):
                    continue
                # 符合条件的新回复
                new_replies.append(reply)
        
        # 推送新回复
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
                # 记录已推送
                cache["pushed_pids"].append(pid)
                time.sleep(0.5)
        else:
            print("\n✅ 无首次运行后的新回复")
        
        # 更新最后检查页数
        cache["last_check_pages"][target_key] = total_pages
        
    except Exception as e:
        print(f"❌ 监控失败: {e}")
    
    # 去重已推送ID
    cache["pushed_pids"] = list(set(cache["pushed_pids"]))

# ==================== 主程序 ====================
def main():
    """主程序"""
    print(f"\n🚀 虎扑新回复监控启动")
    print(f"⏰ 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 监控目标数: {len(MONITOR_TARGETS)}")
    
    # 加载缓存
    cache = load_cache()
    
    # 遍历监控每个目标
    for target in MONITOR_TARGETS:
        monitor_target(target, cache)
    
    # 保存缓存
    save_cache(cache)
    
    # 最终统计
    print(f"\n{'='*50}")
    print(f"🎉 监控完成")
    print(f"📊 累计推送: {len(cache['pushed_pids'])} 条")
    print(f"⏰ 首次运行时间: {datetime.fromtimestamp(cache['first_run_time']).strftime('%Y-%m-%d %H:%M:%S') if cache['first_run_time'] else '未初始化'}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
