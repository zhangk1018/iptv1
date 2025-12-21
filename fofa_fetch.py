import os
import re
import requests
import time
import concurrent.futures
from datetime import datetime, timezone, timedelta

# ===============================
# 配置区（酒店IPTV源专用）
FOFA_URLS = {
    # 主关键词：酒店系统最常见路径（2025年实测有效，命中率最高）
    "https://fofa.info/result?qbase64=aXB0di9saXZlL3poX2NuLmpzIiAmJiBjb3VudHJ5PSJDTiI=": "hotel_zh_cn.txt",
    # 可选备选关键词（取消注释可增加覆盖）
    # "https://fofa.info/result?qbase64=dGl0bGU9ImhvdGVsIOa0qOiouSIgJiYgY291bnRyeT0iQ04i": "hotel_title.txt",
    # "https://fofa.info/result?qbase64=IkpIR1hUViIgJiYgY291bnRyeT0iQ04i": "hotel_zhgxtv.txt",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

COUNTER_FILE = "计数.txt"
IP_DIR = "ip"
ZUBO_FILE = "zubo.txt"
IPTV_FILE = "IPTV.txt"

# 酒店源常见有效路径（实测可直接播放或出列表）
HOTEL_PATHS = [
    "",                          # 根路径（很多酒店直接打开就是播放器）
    "iptv/live/zh_cn.js",        # 频道列表JS（最常见）
    "playlist.m3u8",             # 直接M3U8
    "iptv/live/playlist.m3u8",
    "live.m3u8",
    "channellist.m3u8",
    "iptv/live/1000.json",       # JSON列表
    "iptv/live/100.ts",          # 示例TS流（用于快速检测存活）
]

# 分类（保持你原来的，便于后续扩展）
CHANNEL_CATEGORIES = {
    "央视频道": ["CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV5", "CCTV6", "CCTV7", "CCTV8", "CCTV9", "CCTV10",
                "CCTV11", "CCTV12", "CCTV13", "CCTV14", "CCTV15", "CCTV16", "CCTV17", "CCTV4K", "CCTV8K"],
    "卫视频道": ["湖南卫视", "浙江卫视", "江苏卫视", "东方卫视", "北京卫视", "广东卫视", "山东卫视", "安徽卫视"],
    "数字频道": ["CHC动作电影", "CHC家庭影院", "CHC影迷电影", "凤凰卫视中文台", "凤凰卫视香港台"],
    "湖北": ["湖北综合频道", "武汉新闻综合"],
}

# ===============================
# 计数逻辑
def get_run_count():
    if os.path.exists(COUNTER_FILE):
        try:
            return int(open(COUNTER_FILE).read().strip())
        except:
            return 0
    return 0

def save_run_count(count):
    open(COUNTER_FILE, "w").write(str(count))

def check_and_clear_files_by_run_count():
    os.makedirs(IP_DIR, exist_ok=True)
    count = get_run_count() + 1
    if count >= 73:
        print(f"第 {count} 次运行，清空 {IP_DIR} 下所有文件")
        for f in os.listdir(IP_DIR):
            if f.endswith(".txt"):
                os.remove(os.path.join(IP_DIR, f))
        save_run_count(1)
        return "w", 1
    else:
        save_run_count(count)
        return "a", count

# ===============================
# IP运营商判断（用于标注）
def get_isp(ip):
    telecom = re.match(r"^(1[0-9]{2}|2[0-3]{2}|42|43|58|59|60|61|110|111|112|113|114|115|116|117|118|119|120|121|122|123|124|125|126|127|175|180|182|183|184|185|186|187|188|189|223)\.", ip)
    if telecom:
        return "电信"
    unicom = re.match(r"^(42|43|58|59|60|61|110|111|112|113|114|115|116|117|118|119|120|121|122|123|124|125|126|127|175|180|182|183|184|185|186|187|188|189|223)\.", ip)
    if unicom:
        return "联通"
    mobile = re.match(r"^(36|37|38|39|100|101|102|103|104|105|106|107|108|109|134|135|136|137|138|139|150|151|152|157|158|159|170|178|182|183|184|187|188|189)\.", ip)
    if mobile:
        return "移动"
    return "未知"

# ===============================
# 第一阶段：爬取酒店IP
def first_stage():
    all_ips = set()
    for url, filename in FOFA_URLS.items():
        print(f"正在爬取 {filename} ...")
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            matches = re.findall(r'<a href="http://([^"]+)"', r.text)
            all_ips.update(m.strip().rstrip("/") for m in matches if ":" in m)
        except Exception as e:
            print(f"爬取失败：{e}")
        time.sleep(3)

    province_isp_dict = {}
    for ip_port in all_ips:
        try:
            ip = ip_port.split(":")[0]
            res = requests.get(f"http://ip-api.com/json/{ip}?lang=zh-CN", timeout=10)
            data = res.json()
            province = data.get("regionName", "未知")
            isp = get_isp(ip)
            if isp == "未知":
                continue
            fname = f"{province}{isp}.txt"
            province_isp_dict.setdefault(fname, set()).add(ip_port)
        except:
            continue

    mode, run_count = check_and_clear_files_by_run_count()
    for filename, ip_set in province_isp_dict.items():
        path = os.path.join(IP_DIR, filename)
        with open(path, mode, encoding="utf-8") as f:
            for ip_port in sorted(ip_set):
                f.write(ip_port + "\n")
        print(f"{path} 已{'覆盖' if mode=='w' else '追加'}写入 {len(ip_set)} 个 IP")
    print(f"第一阶段完成，当前轮次：{run_count}")
    return run_count

# ===============================
# 第二阶段：生成酒店源候选URL
def second_stage():
    print("第二阶段触发：生成酒店源 zubo.txt")
    combined_lines = []
    for ip_file in os.listdir(IP_DIR):
        if not ip_file.endswith(".txt"):
            continue
        ip_path = os.path.join(IP_DIR, ip_file)
        province_operator = ip_file.replace(".txt", "")
        with open(ip_path, encoding="utf-8") as f:
            ip_ports = [line.strip() for line in f if line.strip()]

        for ip_port in ip_ports:
            base = f"http://{ip_port}"
            for path in HOTEL_PATHS:
                url = base if not path else f"{base}/{path.lstrip('/')}"
                combined_lines.append(f"酒店直播源,{url}${province_operator}")

    # 去重
    unique = {line.split(",", 1)[1]: line for line in combined_lines if "," in line}
    with open(ZUBO_FILE, "w", encoding="utf-8") as f:
        for line in unique.values():
            f.write(line + "\n")
    print(f"第二阶段完成，共 {len(unique)} 条候选酒店源")

# ===============================
# 第三阶段：检测存活源
def third_stage():
    print("第三阶段：检测存活酒店源，生成 IPTV.txt")
    if not os.path.exists(ZUBO_FILE):
        print("zubo.txt 不存在，跳过")
        return

    def is_alive(url_with_operator):
        url = url_with_operator.split("$")[0].strip()
        try:
            r = requests.get(url, timeout=15, stream=True, headers=HEADERS)
            return r.status_code == 200 and len(r.content) > 100
        except:
            return False

    with open(ZUBO_FILE, "r", encoding="utf-8") as f:
        candidate_lines = [line.strip() for line in f if line.strip() and "," in line and "$" in line]

    print(f"启动多线程检测（共 {len(candidate_lines)} 个源）...")
    alive_lines = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(is_alive, line.split(",", 1)[1]) for line in candidate_lines]
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            if future.result():
                alive_lines.append(candidate_lines[i])

    beijing_now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    disclaimer_url = "https://kakaxi-1.asia/LOGO/Disclaimer.mp4"

    with open(IPTV_FILE, "w", encoding="utf-8") as f:
        f.write(f"更新时间: {beijing_now}（北京时间）\n\n")
        f.write("更新时间,#genre#\n")
        f.write(f"{beijing_now},{disclaimer_url}\n\n")
        for cat in CHANNEL_CATEGORIES:
            f.write(f"{cat},#genre#\n")
        f.write("\n")
        for line in alive_lines:
            f.write(line + "\n")

    print(f"IPTV.txt 生成完成，共 {len(alive_lines)} 条存活酒店源")

# ===============================
# 文件推送（无emoji，兼容Actions）
def push_all_files():
    print("推送所有更新文件到 GitHub...")
    os.system('git config --global user.name "github-actions"')
    os.system('git config --global user.email "github-actions@users.noreply.github.com"')
    os.system("git add 计数.txt")
    os.system("git add ip/*.txt || true")
    os.system("git add zubo.txt || true")
    os.system("git add IPTV.txt || true")
    os.system('git commit -m "自动更新：酒店IPTV源 IP + IPTV.txt" || echo "无变更，无需提交"')
    os.system("git push origin main || echo '推送失败（可能无变更）'")

# ===============================
# 主执行逻辑（每次运行都完整生成）
if __name__ == "__main__":
    run_count = first_stage()
    second_stage()    # 每次都执行
    third_stage()     # 每次都执行
    push_all_files()
