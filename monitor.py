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
    "state_file": "reply_push_state.json"
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

# ==================== 状态管理 ====================
def load_push_state():
    default_state = {
        "pushed_pids": [],
        "first_run": True,
        "last_check": {}
    }
    if os.path.exists(CONFIG["state_file"]):
        try:
            with open(CONFIG["state_file"], "r", encoding="utf-8") as f:
                state = json.load(f)
            for k, v in default_state.items():
                if k not in state:
                    state[k] = v
            return state
        except:
            return default_state
    return default_state

def save_push_state(state):
    try:
        with open(CONFIG["state_file"], "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except:
        pass

# ==================== 内容清理 ====================
def clean_content(s):
    if not s:
        return ""
    s = re.sub(r'\\u003c.*?\\u003e', '', s)
    s = re.sub(r'<.*?>', '', s)
    s = re.sub(r'https?://\S+', '', s)
    s = s.replace('\\', '').replace('"', '').replace("'", "")
    s = re.sub(r'\s+', ' ', s).strip()
    return s

# ==================== 提取 replies ====================
def extract_replies(html):
    try:
        match = re.search(r'<script id="__NEXT_DATA__".*?>(.*?)</script>', html, re.DOTALL)
        if not match:
            return None
        data = json.loads(match.group(1))
        return data["props"]["pageProps"]["detail"]["replies"]
    except:
        pass

    match = re.search(r'"replies"\s*:\s*({.*?"list"\s*:\s*\[.*?\].*?})', html, re.DOTALL)
    if not match:
        return None

    raw = match.group(1)
    res = {
        "current": 0,
        "total": 0,
        "list": []
    }
    cur = re.search(r'"current"\s*:\s*(\d+)', raw)
    tot = re.search(r'"total"\s*:\s*(\d+)', raw)
    if cur: res["current"] = int(cur.group(1))
    if tot: res["total"] = int(tot.group(1))

    items = re.findall(r'\{.*?"pid"\s*:\s*"[^"]+".*?\}', raw)
    for it in items:
        pid = re.search(r'"pid"\s*:\s*"([^"]+)"', it)
        ct = re.search(r'"content"\s*:\s*"([^"]+)"', it)
        tm = re.search(r'"createdAtFormat"\s*:\s*"([^"]+)"', it)
        res["list"].append({
            "pid": pid.group(1) if pid else "",
            "content": clean_content(ct.group(1)) if ct else "",
            "createdAtFormat": tm.group(1) if tm else ""
        })
    return res

# ==================== Bark 推送 ====================
def push_bark(title, body):
    key = CONFIG["bark_key"]
    if not key:
        print("⚠️ 未配置 BARK_KEY")
        return
    try:
        t = requests.utils.quote(title)
        b = requests.utils.quote(body)
        u = f"https://api.day.app/{key}/{t}/{b}"
        requests.get(u, timeout=5)
        print("✅ Bark 推送成功")
    except:
        print("❌ Bark 推送失败")

# ==================== 监控单个目标 ====================
def monitor_one(target, state):
    thread_id = target["thread_id"]
    euid = target["target_euid"]
    name = target["name"]
    key = f"{thread_id}_{euid}"

    print(f"\n==================================================")
    print(f"📌 正在监控：{name} | 帖子 {thread_id} | 用户 {euid}")

    # 获取首页（拿总页数）
    cmd = CURL_TEMPLATE.format(thread_id=thread_id, euid=euid)
    html = subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout
    if not html:
        print("❌ 获取页面失败")
        return

    rep = extract_replies(html)
    if not rep:
        print("❌ 未获取到 replies")
        return

    total = rep.get("total", 0)
    print(f"📊 总页数：{total}")

    # 首次运行：取最后一页最后3条
    if state.get("first_run", True):
        if total <= 0:
            return
        cmd_last = CURL_TEMPLATE.format(thread_id=thread_id, euid=euid).replace("-1.html", f"-{total}.html")
        html_last = subprocess.run(cmd_last, shell=True, capture_output=True, text=True).stdout
        rep_last = extract_replies(html_last)
        if rep_last and rep_last.get("list"):
            lst = rep_last["list"]
            take = lst[-3:] if len(lst) >=3 else lst
            for item in reversed(take):
                pid = item.get("pid")
                if not pid:
                    continue
                title = f"【{name}】新回复"
                body = f"{item.get('createdAtFormat')}\n{item.get('content')}"
                print(f"\n📤 首次推送：{body}")
                push_bark(title, body)
                state["pushed_pids"].append(pid)
        return

    # 非首次：检查最新页，只推新的
    check_pages = list(range(total, max(0, total-2), -1))
    new_items = []
    for p in check_pages:
        cmd_p = CURL_TEMPLATE.format(thread_id=thread_id, euid=euid).replace("-1.html", f"-{p}.html")
        html_p = subprocess.run(cmd_p, shell=True, capture_output=True, text=True).stdout
        rp = extract_replies(html_p)
        if not rp or not rp.get("list"):
            continue
        for it in rp["list"]:
            pid = it.get("pid")
            if pid and pid not in state["pushed_pids"]:
                new_items.append(it)

    if new_items:
        print(f"✅ 发现 {len(new_items)} 条新回复")
        for it in new_items:
            title = f"【{name}】新回复"
            body = f"{it.get('createdAtFormat')}\n{it.get('content')}"
            print(f"\n📤 {body}")
            push_bark(title, body)
            state["pushed_pids"].append(it.get("pid"))
    else:
        print("✅ 暂无新回复")

# ==================== 主入口 ====================
def main():
    print("🚀 多帖子多用户监控启动")
    state = load_push_state()

    for target in MONITOR_TARGETS:
        monitor_one(target, state)

    state["pushed_pids"] = list(set(state["pushed_pids"]))
    state["first_run"] = False
    save_push_state(state)
    print(f"\n🎉 全部监控完成，已推送 {len(state['pushed_pids'])} 条")

if __name__ == "__main__":
    main()
