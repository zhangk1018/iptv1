import os
import re
import time
import requests
import concurrent.futures
import sys

# ===============================
# 配置区
# ===============================
INPUT_FILE = "IPTV.txt"
OUTPUT_FILE = "IPTV.txt"
CHECK_COUNT = 2          # 每个 IP 抽取几个频道
TEST_DURATION = 10       # 延长测试时间到 10 秒，让速度跑起来
SPEED_LEVELS = [4.0, 2.0, 1.0, 0.5, 0.1] # 提高门槛

def get_realtime_speed(url):
    """采用更大块的读取方式，尝试突破限速"""
    try:
        start_time = time.time()
        size = 0
        # 增加 headers 模拟真实播放器，有些源对纯 python 请求限速
        headers = {
            "User-Agent": "PotPlayer",
            "Accept": "*/*",
            "Connection": "keep-alive"
        }
        with requests.get(url, stream=True, timeout=10, headers=headers) as r:
            if r.status_code != 200:
                return 0
            # 使用 2MB 的大块，减少循环次数
            for chunk in r.iter_content(chunk_size=2*1024*1024): 
                size += len(chunk)
                if time.time() - start_time > TEST_DURATION:
                    break
        duration = time.time() - start_time
        speed = (size / 1024 / 1024) / duration if duration > 0 else 0
        return speed
    except:
        return 0

def test_ip_group(ip_port, channels):
    # 选出该服务器下的代表频道
    test_targets = [u for n, u in channels if "CCTV1" in n or "CCTV5" in n][:CHECK_COUNT]
    if not test_targets:
        test_targets = [channels[0][1]]
    
    max_found_speed = 0
    for url in test_targets:
        speed = get_realtime_speed(url)
        if speed > max_found_speed:
            max_found_speed = speed
        
        # 实时日志输出（带时间戳，方便观察是否卡顿）
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        sys.stdout.write(f"[{timestamp}] 服务器 [{ip_port}] 峰值速度: {speed:.2f} MB/s\n")
        sys.stdout.flush()
        
    return ip_port, max_found_speed

def main():
    if not os.path.exists(INPUT_FILE):
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
            if line: other_info.append(line)

    print(f"🚀 开始压力测速。共 {len(ip_groups)} 组服务器。")
    print(f"注意：若速度普遍在 0.8MB/s，说明受到 GitHub 网络限制，脚本将自动根据相对值排序。")
    
    results = {}
    # 并发降到 2，确保每个测试线程能分到足够的 GitHub 宿主机带宽
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(test_ip_group, ip, chs): ip for ip, chs in ip_groups.items()}
        for future in concurrent.futures.as_completed(futures):
            ip_port, speed = future.result()
            results[ip_port] = speed

    # 排序：找出真正的“快源”
    # 即使由于限速大家都只有 0.8，我们也要选出 0.88 而不是 0.81 的
    sorted_ips = sorted(results.items(), key=lambda x: x[1], reverse=True)
    
    selected_ips = []
    # 阶梯逻辑优化：如果大家都差不多，取前 30% 的优胜者
    top_threshold = len(sorted_ips) // 3 if len(sorted_ips) > 3 else len(sorted_ips)
    
    for level in SPEED_LEVELS:
        current_level_ips = [ip for ip, s in results.items() if s >= level]
        if len(current_level_ips) >= 5: # 找到 5 个以上的优质源
            selected_ips = current_level_ips
            print(f"✅ 达标线 {level} MB/s，保留 {len(selected_ips)} 个节点")
            break
    
    if not selected_ips:
        selected_ips = [ip for ip, s in sorted_ips[:10]] # 保底取最快的前10个
        print(f"⚠️ 无法达到理想阈值，按相对排名保留前 10 名服务器")

    # 写回文件... (保持之前的逻辑)
    from fofa_fetch import CHANNEL_CATEGORIES
    final_output = [l for l in other_info if "#genre#" in l or "更新时间" in l]
    
    for category, ch_list in CHANNEL_CATEGORIES.items():
        category_added = False
        for std_name in ch_list:
            for ip_port in selected_ips:
                for name, url_part in ip_groups.get(ip_port, []):
                    if name == std_name:
                        if not category_added:
                            final_output.append(f"\n{category},#genre#")
                            category_added = True
                        final_output.append(f"{name},{url_part}")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(final_output))

    print(f"✨ 筛选完成！")

if __name__ == "__main__":
    main()
