import json
import re
import subprocess
import os
import time
import requests

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

CONFIG = {
    "bark_key": os.environ.get("BARK_KEY", ""),
}

# ==================== 缓存读取（从 cache 读，不从文件） ====================
def load_pushed_pids():
    try:
        with open("/tmp/pushed_pids.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_pushed_pids(pids):
    try:
        with open("/tmp/pushed_pids.json", "w", encoding="utf-8") as f:
            json.dump(pids, f, ensure_ascii=False)
    except:
        pass

# ==================== 清理 HTML 标签 ====================
def clean_content(s):
    if not s:
        return ""
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'\\u003c.*?\\u003e', '', s)
    s = re.sub(r'\\n|\\r|\\t', ' ', s)
    s = re.sub(r'https?://\S+', '', s)
    s = s.replace('\\', '').replace('"', '').replace("'", "")
    return s.strip() or "无内容"

# ==================== 提取回复 ====================
def extract_replies(html):
    try:
        match = re.search(r'<script id="__NEXT_DATA__".*?>(.*?)</script>', html, re.DOTALL)
        data = json.loads(match.group(1))
        return data["props"]["pageProps"]["detail"]["replies"]
    except:
        return None

# ==================== Bark 推送 ====================
def push_bark(title, body):
    key = CONFIG["bark_key"]
    if not key:
        print("⚠️ 未配置 BARK_KEY")
        return
    try:
        t = requests.utils.quote(title)
        b = requests.utils.quote(body)
        requests.get(f"https://api.day.app/{key}/{t}/{b}", timeout=5)
        print("✅ Bark 推送成功")
    except:
        print("❌ Bark 推送失败")

# ==================== 监控单个 ====================
def monitor(target, pushed_pids):
    tid = target["thread_id"]
    euid = target["target_euid"]
    name = target["name"]

    print(f"\n📌 监控：{name}")

    cmd = f'''curl 'https://bbs.hupu.com/{tid}_{euid}-1.html' \
      -H 'user-agent: Mozilla/5.0' --silent --show-error'''
    html = subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout
    rep = extract_replies(html)
    if not rep:
        return

    total = rep.get("total", 0)
    first_run = len(pushed_pids) == 0

    if first_run:
        print("🔹 首次运行：取最后3条")
        cmd_last = f'''curl 'https://bbs.hupu.com/{tid}_{euid}-{total}.html' \
          -H 'user-agent: Mozilla/5.0' --silent --show-error'''
        html_last = subprocess.run(cmd_last, shell=True, capture_output=True, text=True).stdout
        rep_last = extract_replies(html_last)
        if rep_last and rep_last.get("list"):
            lst = rep_last["list"]
            take = lst[-3:] if len(lst) >= 3 else lst
            for item in reversed(take):
                pid = item.get("pid")
                if not pid or pid in pushed_pids:
                    continue
                title = f"【{name}】新回复"
                body = f"{item.get('createdAtFormat')}\n{item.get('content')}"
                print(f"📤 {body}")
                push_bark(title, body)
                pushed_pids.append(pid)
        return

    # 非首次
    new_items = []
    for p in range(total, max(0, total-2), -1):
        cmd_p = f'''curl 'https://bbs.hupu.com/{tid}_{euid}-{p}.html' \
          -H 'user-agent: Mozilla/5.0' --silent --show-error'''
        html_p = subprocess.run(cmd_p, shell=True, capture_output=True, text=True).stdout
        rp = extract_replies(html_p)
        if not rp or not rp.get("list"):
            continue
        for it in rp["list"]:
            pid = it.get("pid")
            if pid and pid not in pushed_pids:
                new_items.append(it)

    if new_items:
        print(f"✅ 发现 {len(new_items)} 条新回复")
        for it in new_items:
            pid = it.get("pid")
            title = f"【{name}】新回复"
            body = f"{it.get('createdAtFormat')}\n{clean_content(it.get('content'))}"
            print(f"📤 {body}")
            push_bark(title, body)
            pushed_pids.append(pid)
    else:
        print("✅ 暂无新回复")

# ==================== 主函数 ====================
def main():
    pushed_pids = load_pushed_pids()
    print(f"🚀 已推送记录数：{len(pushed_pids)}")

    for t in MONITOR_TARGETS:
        monitor(t, pushed_pids)

    save_pushed_pids(list(set(pushed_pids)))
    print(f"\n🎉 完成，累计已推送：{len(pushed_pids)}")

if __name__ == "__main__":
    main()
