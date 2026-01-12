import os
import re
import time
import requests
import concurrent.futures
import sys

# ===============================
# 配置区
# ===============================
INPUT_FILE = "live.txt"          # 修改：输入文件改为 live.txt
OUTPUT_FILE = "livezubo.txt"     # 修改：输出文件改为 livezubo.txt
CHECK_COUNT = 2
TEST_DURATION = 8
# 阶梯标准：只要达到这一层，该层所有符合条件的 IP 都要
SPEED_STEPS = [ 0.90, 0.85, 0.80, 0.50]

def get_realtime_speed(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PotPlayer/23.9.22",
        "Accept": "*/*"
    }
    try:
        start_time = time.time()
        size = 0
        with requests.get(url, stream=True, timeout=10, headers=headers) as r:
            if r.status_code != 200: return 0
            for chunk in r.iter_content(chunk_size=1024*1024):
                size += len(chunk)
                if time.time() - start_time > TEST_DURATION: break
        duration = time.time() - start_time
        return (size / 1024 / 1024) / duration if duration > 0 else 0
    except:
        return 0

def test_ip_group(ip_port, channels):
    test_targets = [u for n, u in channels if "CCTV1" in n or "CCTV5" in n][:CHECK_COUNT]
    if len(test_targets) < CHECK_COUNT:
        test_targets = [c[1] for c in channels[:CHECK_COUNT]]
   
    max_speed = 0
    for url in test_targets:
        speed = get_realtime_speed(url)
        if speed > max_speed: max_speed = speed
       
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    sys.stdout.write(f"[{timestamp}] 探测服务器 [{ip_port}] -> 峰值速度: {max_speed:.2f} MB/s\n")
    sys.stdout.flush()
    return ip_port, max_speed

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"⚠️ 输入文件 {INPUT_FILE} 不存在，脚本退出。")
        return
    
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    ip_groups = {}
    other_info = []
    for line in lines:
        line = line.strip()
        if "," in line and "$" in line:
            name, url_part = line.split(",", 1)
            match = re.search(r'http://(.*?)/', url_part)
            if match:
                ip_port = match.group(1)
                ip_groups.setdefault(ip_port, []).append((name, url_part))
        else:
            if line:
                other_info.append(line)
    
    print(f"🚀 启动阶梯全量筛选。候选服务器: {len(ip_groups)} 个。")
   
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(test_ip_group, ip, chs): ip for ip, chs in ip_groups.items()}
        for future in concurrent.futures.as_completed(futures):
            ip_port, speed = future.result()
            results[ip_port] = speed
    
    # --- 核心逻辑：获取符合条件的全部组 ---
    selected_ips = []
    final_step = 0
   
    for step in SPEED_STEPS:
        eligible_ips = [ip for ip, s in results.items() if s >= step]
        if eligible_ips:
            selected_ips = eligible_ips
            final_step = step
            print(f"\n✅ 找到符合 {step} MB/s 标准的精英组，共 {len(selected_ips)} 个服务器。")
            break
    
    if not selected_ips:
        best_ip = max(results, key=results.get)
        selected_ips = [best_ip]
        print(f"\n⚠️ 无达标源，保底取最快: {best_ip} ({results[best_ip]:.2f} MB/s)")
    
    # 重构输出文件
    # 注意：这里仍需从 fofa_fetch 导入 CHANNEL_CATEGORIES（假设在同一仓库/环境中可用）
    try:
        from fofa_fetch import CHANNEL_CATEGORIES
    except ImportError:
        print("❌ 无法导入 CHANNEL_CATEGORIES，请确保 fofa_fetch.py 在同一目录或已安装。")
        return
    
    final_output = [l for l in other_info if "#genre#" in l or "更新时间" in l]
    final_output.append("\n")  # 确保分类前有空行
    
    for category, ch_list in CHANNEL_CATEGORIES.items():
        category_added = False
        for std_name in ch_list:
            channel_entries = []
            for ip in selected_ips:
                for name, url_part in ip_groups.get(ip, []):
                    if name == std_name:
                        channel_entries.append((url_part, results[ip]))
           
            # 同一频道按速度降序排列
            channel_entries.sort(key=lambda x: x[1], reverse=True)
           
            for url_part, _ in channel_entries:
                if not category_added:
                    final_output.append(f"{category},#genre#")
                    category_added = True
                final_output.append(f"{std_name},{url_part}")
        
        if category_added:
            final_output.append("")  # 分类间空行
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(final_output) + "\n")
    
    print(f"🎯 筛选完成！输出文件：{OUTPUT_FILE}，已保留所有速度 >= {final_step} MB/s 的服务器频道。")

if __name__ == "__main__":
    main()
