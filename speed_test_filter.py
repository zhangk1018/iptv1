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
CHECK_COUNT = 2          # 每个 IP 抽取几个频道做代表
TEST_DURATION = 5        # 每个频道测试时长
# 阶梯标准（从高到低尝试）
SPEED_LEVELS = [2.0, 1.0, 0.5, 0.1] 

def get_realtime_speed(url):
    """测试速度并实时返回数据量"""
    try:
        start_time = time.time()
        size = 0
        # 实时打印探测动作
        with requests.get(url, stream=True, timeout=8) as r:
            if r.status_code != 200:
                return 0
            for chunk in r.iter_content(chunk_size=512*1024): # 512KB 块
                size += len(chunk)
                if time.time() - start_time > TEST_DURATION:
                    break
        duration = time.time() - start_time
        speed = (size / 1024 / 1024) / duration if duration > 0 else 0
        return speed
    except:
        return 0

def test_ip_group(ip_port, channels):
    """测试组，增加实时日志打印"""
    test_targets = [u for n, u in channels if "CCTV1" in n or "CCTV5" in n][:CHECK_COUNT]
    if not test_targets:
        test_targets = [channels[0][1]]
    
    max_found_speed = 0
    for url in test_targets:
        speed = get_realtime_speed(url)
        if speed > max_found_speed:
            max_found_speed = speed
        # 实时在控制台输出进度
        sys.stdout.write(f"  - 探测 [{ip_port}] 实时速度: {speed:.2f} MB/s\n")
        sys.stdout.flush()
        
    return ip_port, max_found_speed

def main():
    if not os.path.exists(INPUT_FILE):
        print("❌ 找不到输入文件")
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

    print(f"🚀 开始对 {len(ip_groups)} 个服务器节点进行阶梯性能测速...")
    
    results = {}
    # 适当降低并发，方便实时观察日志，且避免被封 IP
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(test_ip_group, ip, chs): ip for ip, chs in ip_groups.items()}
        for future in concurrent.futures.as_completed(futures):
            ip_port, speed = future.result()
            results[ip_port] = speed

    # 阶梯选择逻辑
    selected_ips = []
    for level in SPEED_LEVELS:
        selected_ips = [ip for ip, s in results.items() if s >= level]
        if len(selected_ips) >= 3: # 如果在这个标准下能找到至少3个服务器，就以此标准为准
            print(f"✅ 最终采用达标线: {level} MB/s，共选取 {len(selected_ips)} 个服务器")
            break
    
    if not selected_ips and results:
        # 如果连最低标准都没达到，保底取速度最快的一个
        best_ip = max(results, key=results.get)
        selected_ips = [best_ip]
        print(f"⚠️ 所有服务器速度均未达标，仅保留最快的一个: {best_ip} ({results[best_ip]:.2f} MB/s)")

    # 重构输出
    final_output = []
    # 写入头部
    for info in other_info:
        if "#genre#" in info or "更新时间" in info:
            final_output.append(info)
    
    # 获取分类逻辑（此处假设你依然使用 fofa_fetch 里的分类）
    from fofa_fetch import CHANNEL_CATEGORIES
    
    for category, ch_list in CHANNEL_CATEGORIES.items():
        category_added = False
        for std_name in ch_list:
            for ip_port in selected_ips:
                for name, url_part in ip_groups[ip_port]:
                    if name == std_name:
                        if not category_added:
                            final_output.append(f"\n{category},#genre#")
                            category_added = True
                        final_output.append(f"{name},{url_part}")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(final_output))

    print(f"\n✨ 筛选完成！已从 {len(ip_groups)} 组服务器中精选出可用资源。")

if __name__ == "__main__":
    main()
