import os
import re
import time
import requests
import concurrent.futures

# ===============================
# 配置区
# ===============================
INPUT_FILE = "IPTV.txt"
OUTPUT_FILE = "IPTV.txt" # 过滤后覆盖原文件
CHECK_COUNT = 3          # 每个 IP 抽取几个频道做测试
SPEED_THRESHOLD = 2.0    # 达标线：平均速度需大于 2.0 MB/s
TEST_DURATION = 5        # 每个频道测试时长（秒）

def get_speed(url):
    """测试单个 URL 的下载速度 (MB/s)"""
    try:
        start_time = time.time()
        size = 0
        # 使用 stream=True 避免内存溢出
        with requests.get(url, stream=True, timeout=5) as r:
            if r.status_code != 200:
                return 0
            for chunk in r.iter_content(chunk_size=1024*1024): # 1MB 块
                size += len(chunk)
                if time.time() - start_time > TEST_DURATION:
                    break
        duration = time.time() - start_time
        return (size / 1024 / 1024) / duration if duration > 0 else 0
    except:
        return 0

def test_ip_group(ip_port, channels):
    """
    对同一个 IP 组进行抽样测试
    返回 (ip_port, 是否达标)
    """
    # 优先抽取央视做测试
    test_targets = []
    cctv_entries = [u for n, u in channels if "CCTV" in n]
    other_entries = [u for n, u in channels if "CCTV" not in n]
    
    test_targets = (cctv_entries[:2] + other_entries)[:CHECK_COUNT]
    
    if not test_targets:
        return ip_port, False

    speeds = []
    for url in test_targets:
        speed = get_speed(url)
        speeds.append(speed)
        if speed > SPEED_THRESHOLD: # 如果有一个频道表现极好，可以提前视为通过
            return ip_port, True
            
    avg_speed = sum(speeds) / len(speeds) if speeds else 0
    return ip_port, avg_speed >= SPEED_THRESHOLD

def main():
    if not os.path.exists(INPUT_FILE):
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 1. 解析与分组
    # ip_groups 结构: { "114.221.3.70:4022": [ (频道名, 完整URL$标记), ... ] }
    ip_groups = {}
    other_info = [] # 存储更新时间等非频道行
    
    for line in lines:
        line = line.strip()
        if "," in line and "$" in line:
            name, url_part = line.split(",", 1)
            # 提取 IP 和 Port
            match = re.search(r'http://(.*?)/', url_part)
            if match:
                ip_port = match.group(1)
                if ip_port not in ip_groups:
                    ip_groups[ip_port] = []
                ip_groups[ip_port].append((name, url_part))
        else:
            if line: other_info.append(line)

    # 2. 多线程测速
    print(f"🚀 开始对 {len(ip_groups)} 个服务器节点进行性能测速...")
    valid_ips = set()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(test_ip_group, ip, chs): ip for ip, chs in ip_groups.items()}
        for future in concurrent.futures.as_completed(futures):
            ip_port, is_ok = future.result()
            if is_ok:
                valid_ips.add(ip_port)
                print(f"✅ 服务器 [{ip_port}] 达标，保留该组频道")
            else:
                print(f"❌ 服务器 [{ip_port}] 速度太慢或离线，丢弃")

    # 3. 写回文件
    # 重新按原始逻辑组织，但只保留有效 IP 的频道
    final_output = []
    # 找回原本的分类逻辑
    from fofa_fetch import CHANNEL_CATEGORIES
    
    # 写入头部
    for info in other_info:
        if "#genre#" in info or "更新时间" in info:
            final_output.append(info)
    
    for category, ch_list in CHANNEL_CATEGORIES.items():
        category_added = False
        for std_name in ch_list:
            # 遍历所有分组，寻找属于该 IP 组且名字匹配的频道
            for ip_port in valid_ips:
                for name, url_part in ip_groups[ip_port]:
                    if name == std_name:
                        if not category_added:
                            final_output.append(f"\n{category},#genre#")
                            category_added = True
                        final_output.append(f"{name},{url_part}")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(final_output))

    print(f"\n✨ 测速筛选完成！有效服务器: {len(valid_ips)}，已更新 {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
