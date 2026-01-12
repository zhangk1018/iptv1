import os
import re
import requests
import time
import concurrent.futures
import subprocess
import socket
import shutil
from datetime import datetime, timezone, timedelta

# ===============================
# 配置区
# ===============================
FOFA_URLS = {
    "https://fofa.info/result?qbase64=InVkcHh5IiAmJiBjb3VudHJ5PSJDTiI%3D": "ip.txt",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

COUNTER_FILE = "计数.txt"
IP_DIR = "ip"
RTP_DIR = "rtp"
ZUBO_FILE = "zubo.txt"
IPTV_FILE = "IPTV.txt"
LIVE_BACKUP_FILE = "live.txt"  

# ===============================
# 分类与映射配置
# ===============================
CHANNEL_CATEGORIES = {
    "央视频道": [
        "CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV4欧洲", "CCTV4美洲", "CCTV5", "CCTV5+", "CCTV6", "CCTV7",
        "CCTV8", "CCTV9", "CCTV10", "CCTV11", "CCTV12", "CCTV13", "CCTV14", "CCTV15", "CCTV16", "CCTV17", "CCTV4K", "CCTV8K",
        "兵器科技", "风云音乐", "风云足球", "风云剧场", "怀旧剧场", "第一剧场", "女性时尚", "世界地理", "央视台球", "高尔夫网球",
        "央视文化精品", "卫生健康", "电视指南", "中学生", "发现之旅", "书法频道", "国学频道", "环球奇观"
    ],
    "卫视频道": [
        "湖南卫视", "浙江卫视", "江苏卫视", "东方卫视", "深圳卫视", "北京卫视", "广东卫视", "广西卫视", "东南卫视", "海南卫视",
        "河北卫视", "河南卫视", "湖北卫视", "江西卫视", "四川卫视", "重庆卫视", "贵州卫视", "云南卫视", "天津卫视", "安徽卫视",
        "山东卫视", "辽宁卫视", "黑龙江卫视", "吉林卫视", "内蒙古卫视", "宁夏卫视", "山西卫视", "陕西卫视", "甘肃卫视", "青海卫视",
        "新疆卫视", "西藏卫视", "三沙卫视", "兵团卫视", "延边卫视", "安多卫视", "康巴卫视", "农林卫视", "山东教育卫视",
        "中国教育1台", "中国教育2台", "中国教育3台", "中国教育4台", "早期教育"
    ],
    "数字频道": [
        "CHC动作电影", "CHC家庭影院", "CHC影迷电影", "淘电影", "淘精彩", "淘剧场", "淘4K", "淘娱乐", "淘BABY", "淘萌宠", "重温经典",
        "星空卫视", "CHANNEL[V]", "凤凰卫视中文台", "凤凰卫视资讯台", "凤凰卫视香港台", "凤凰卫视电影台", "求索纪录", "求索科学",
        "求索生活", "求索动物", "纪实人文", "金鹰纪实", "纪实科教", "睛彩青少", "睛彩竞技", "睛彩篮球", "睛彩广场舞", "魅力足球", "五星体育",
        "劲爆体育", "快乐垂钓", "茶频道", "先锋乒羽", "天元围棋", "汽摩", "梨园频道", "文物宝库", "武术世界", "哒啵赛事", "哒啵电竞", "黑莓电影", "黑莓动画", 
        "乐游", "生活时尚", "都市剧场", "欢笑剧场", "游戏风云", "金色学堂", "动漫秀场", "新动漫", "卡酷少儿", "金鹰卡通", "优漫卡通", "哈哈炫动", "嘉佳卡通", 
        "中国交通", "中国天气", "华数4K", "华数星影", "华数动作影院", "华数喜剧影院", "华数家庭影院", "华数经典电影", "华数热播剧场", "华数碟战剧场",
        "华数军旅剧场", "华数城市剧场", "华数武侠剧场", "华数古装剧场", "华数魅力时尚", "华数少儿动画", "华数动画"
    ],
    "湖北": [
        "湖北公共新闻", "湖北经视频道", "湖北综合频道", "湖北垄上频道", "湖北影视频道", "湖北生活频道", "湖北教育频道", "武汉新闻综合", "武汉电视剧", "武汉科技生活",
        "武汉文体频道", "武汉教育频道", "阳新综合", "房县综合", "蔡甸综合",
    ],
    "山西": [
        "山西黄河HD", "山西经济与科技HD", "山西影视HD", "山西社会与法治HD", "山西文体生活HD",
    ],
    "福建": [
        "福建综合", "福建新闻", "福建经济", "福建电视剧", "福建公共", "福建少儿", "泉州电视台", "福州电视台",
    ],
     "大湾区": [
         "广东珠江","广东体育","广东新闻","广东民生","广东影视","广东综艺","岭南戏曲","广东经济科教", "广州综合","广州新闻","广州影视","广州竞赛","广州法治","广州南国都市","佛山综合",
    ],
}

# ===============================
# 核心函数
# ===============================

def get_run_count():
    if os.path.exists(COUNTER_FILE):
        try:
            with open(COUNTER_FILE, "r", encoding="utf-8") as f:
                return int(f.read().strip() or "0")
        except:
            return 0
    return 0

def save_run_count(count):
    with open(COUNTER_FILE, "w", encoding="utf-8") as f:
        f.write(str(count))

def get_isp_from_api(data):
    isp_raw = (data.get("isp") or "").lower()
    if any(x in isp_raw for x in ["telecom", "ct", "chinatelecom"]): return "电信"
    if any(x in isp_raw for x in ["unicom", "cu", "chinaunicom"]): return "联通"
    if any(x in isp_raw for x in ["mobile", "cm", "chinamobile"]): return "移动"
    return "未知"

def first_stage():
    os.makedirs(IP_DIR, exist_ok=True)
    all_ips = set()
    for url, filename in FOFA_URLS.items():
        print(f"Fetch {filename} ...")
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            urls_all = re.findall(r'<a href="http://(.*?)"', r.text)
            all_ips.update(u.strip() for u in urls_all if u.strip())
        except Exception as e:
            print(f"Error crawling: {e}")
    
    province_isp_dict = {}
    print(f"Analyzing {len(all_ips)} IPs...")
    for ip_port in all_ips:
        try:
            host = ip_port.split(":")[0]
            res = requests.get(f"http://ip-api.com/json/{host}?lang=zh-CN", timeout=5)
            data = res.json()
            province = data.get("regionName", "未知")
            isp = get_isp_from_api(data)
            
            fname = f"{province}{isp}.txt"
            province_isp_dict.setdefault(fname, set()).add(ip_port)
        except:
            continue

    count = get_run_count() + 1
    save_run_count(count)

    for filename, ip_set in province_isp_dict.items():
        path = os.path.join(IP_DIR, filename)
        with open(path, "a", encoding="utf-8") as f:
            for ip in sorted(ip_set): f.write(ip + "\n")
    
    print(f"Stage 1 finished. Round: {count}")
    return count

def second_stage():
    print("Stage 2: Combining IP and RTP...")
    if not os.path.exists(RTP_DIR):
        print(f"Warning: {RTP_DIR} directory not found.")
        return
        
    combined_lines = []
    for ip_file in os.listdir(IP_DIR):
        if not ip_file.endswith(".txt"): continue
        ip_path = os.path.join(IP_DIR, ip_file)
        rtp_path = os.path.join(RTP_DIR, ip_file)
        
        if not os.path.exists(rtp_path): continue
        
        try:
            with open(ip_path, "r", encoding="utf-8") as f1, open(rtp_path, "r", encoding="utf-8") as f2:
                ips = [x.strip() for x in f1 if x.strip()]
                rtps = [x.strip() for x in f2 if x.strip()]
                for ip in ips:
                    for rtp in rtps:
                        if "," not in rtp: continue
                        name, url = rtp.split(",", 1)
                        if "://" not in url: continue
                        
                        proto = "rtp" if "rtp://" in url else "udp"
                        part = url.split("://")[1]
                        combined_lines.append(f"{name},http://{ip}/{proto}/{part}")
        except Exception as e:
            print(f"Error processing {ip_file}: {e}")

    with open(ZUBO_FILE, "w", encoding="utf-8") as f:
        for line in set(combined_lines): f.write(line + "\n")
    print(f"zubo.txt generated: {len(combined_lines)} lines.")

def third_stage():
    print("Stage 3: Testing and generating IPTV.txt...")
    if not os.path.exists(ZUBO_FILE): return
    
    def check_stream(url):
        try:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=format_name", "-of", "default=noprint_wrappers=1:nokey=1", url]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            return res.returncode == 0
        except: return False

    groups = {}
    with open(ZUBO_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if "," in line:
                name, url = line.strip().split(",", 1)
                m = re.match(r"http://(.*?)/", url)
                if m: groups.setdefault(m.group(1), []).append((name, url))

    playable_ips = set()
    print(f"Testing {len(groups)} server groups...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_stream, chs[0][1]): ip for ip, chs in groups.items() if chs}
        for f in concurrent.futures.as_completed(futures):
            if f.result(): playable_ips.add(futures[f])

    beijing_now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    with open(IPTV_FILE, "w", encoding="utf-8") as f:
        f.write(f"Update: {beijing_now}\n\n更新时间,#genre#\n{beijing_now},#\n\n")
        for cat, ch_list in CHANNEL_CATEGORIES.items():
            f.write(f"{cat},#genre#\n")
            for std_name in ch_list:
                for ip in playable_ips:
                    for name, url in groups[ip]:
                        if name == std_name or any(alias == name for alias in CHANNEL_MAPPING.get(std_name, [])):
                            f.write(f"{std_name},{url}\n")
            f.write("\n")
    print("IPTV.txt generated.")

def push_all_files():
    print("Pushing to GitHub...")
    os.system('git config --global user.name "github-actions"')
    os.system('git config --global user.email "actions@github.com"')
    os.system(f"git add 计数.txt {IPTV_FILE} {LIVE_BACKUP_FILE} {IP_DIR}/*.txt {ZUBO_FILE} || true")
    os.system('git commit -m "Auto Update: IP pool and full backup" || echo "No changes"')
    os.system("git push origin main")

# ===============================
# 执行入口
# ===============================
if __name__ == "__main__":
    run_count = first_stage()
    
    if run_count % 10 == 0:
        second_stage()
        third_stage()
        
        if os.path.exists(IPTV_FILE):
            shutil.copy(IPTV_FILE, LIVE_BACKUP_FILE)
            print(f"Full backup saved to {LIVE_BACKUP_FILE}")
    else:
        print(f"Round {run_count}, skipping Stage 2 and 3.")

    push_all_files()
