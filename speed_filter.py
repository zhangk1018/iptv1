import os
import re
import time
import requests
import concurrent.futures
import sys
import random

# ===============================
# 配置区
# ===============================
INPUT_FILES = [
    "live.txt",
    "IPTV2.txt"
    # 可以继续添加更多文件，例如 "backup.txt", "new_sources.txt"
]

OUTPUT_FILE = "livezubo.txt"

CHECK_COUNT = 3               # 目标测试频道数量
TEST_DURATION = 12            # 每个测试时长（秒）

# 严格模式
MIN_PEAK_REQUIRED = 1.15
MIN_STABLE_REQUIRED = 1.11

# 降级模式
FALLBACK_PEAK = 1.10
FALLBACK_STABLE = 0.95


def get_realtime_speed(url):
    """返回：峰值速度, 后半段平均速度(谷底参考), 整体平均速度"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PotPlayer/23.9.22",
        "Accept": "*/*"
    }
    try:
        start_time = time.time()
        total_size = 0
        speed_samples = []
        last_size = 0
        last_check = start_time

        with requests.get(url, stream=True, timeout=15, headers=headers) as r:
            if r.status_code != 200:
                return 0.0, 0.0, 0.0

            for chunk in r.iter_content(chunk_size=1024*256):
                if chunk:
                    total_size += len(chunk)
                    now = time.time()
                    if now - last_check >= 0.8:
                        interval = now - last_check
                        current_speed = (total_size - last_size) / interval / 1024 / 1024
                        speed_samples.append(current_speed)
                        last_size = total_size
                        last_check = now

                    if now - start_time > TEST_DURATION:
                        break

        duration = time.time() - start_time
        if duration < 3 or total_size == 0:
            return 0.0, 0.0, 0.0

        overall_avg = (total_size / 1024 / 1024) / duration

        if not speed_samples:
            return overall_avg, overall_avg, overall_avg

        peak_speed = max(speed_samples)
        split_idx = max(2, len(speed_samples) * 4 // 10)
        stable_avg = sum(speed_samples[split_idx:]) / len(speed_samples[split_idx:]) if len(speed_samples) > 4 else overall_avg

        return peak_speed, stable_avg, overall_avg

    except Exception:
        return 0.0, 0.0, 0.0


def test_ip_group(ip_port, channels):
    all_urls = [url for _, url in channels]
    
    if not all_urls:
        return ip_port, 0.0, 0.0, 0.0

    if len(all_urls) >= CHECK_COUNT:
        test_targets = random.sample(all_urls, CHECK_COUNT)
    else:
        test_targets = all_urls[:]

    best_peak = 0.0
    best_stable = 0.0
    best_overall = 0.0
    best_url = ""

    for url in test_targets:
        peak, stable, overall = get_realtime_speed(url)
        
        if (peak > best_peak) or (peak == best_peak and stable > best_stable):
            best_peak = peak
            best_stable = stable
            best_overall = overall
            best_url = url

    timestamp = time.strftime("%H:%M:%S", time.localtime())
    sys.stdout.write(
        f"[{timestamp}] {ip_port:21} → "
        f"峰值:{best_peak:5.2f} 谷底参考:{best_stable:5.2f} 整体:{best_overall:5.2f} MB/s "
        f"测试 {len(test_targets)}/{len(all_urls)} 条 示例:{best_url[:68]}\n"
    )
    sys.stdout.flush()

    return ip_port, best_peak, best_stable, best_overall


def main():
    if not INPUT_FILES:
        print("⚠️ 没有配置任何输入文件，脚本退出。")
        return

    all_lines = []
    for input_file in INPUT_FILES:
        if not os.path.exists(input_file):
            print(f"⚠️ 输入文件 {input_file} 不存在，跳过。")
            continue
        with open(input_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            all_lines.extend(lines)
        print(f"已读取 {input_file}，共 {len(lines)} 行")

    # 建立 IP → 频道列表 的映射（用于后续判断）
    ip_groups = {}
    for line in all_lines:
        line = line.strip()
        if "," in line and "http://" in line:
            name, url_part = line.split(",", 1)
            match = re.search(r'http://(.*?)/', url_part)
            if match:
                ip_port = match.group(1)
                ip_groups.setdefault(ip_port, []).append((name, url_part))

    print(f"\n🚀 启动筛选 | 候选服务器: {len(ip_groups)} 个 | 每组目标测试: {CHECK_COUNT}个频道 | 时长: {TEST_DURATION}s\n")

    # 测试所有服务器
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(test_ip_group, ip, chs): ip for ip, chs in ip_groups.items()}
        for future in concurrent.futures.as_completed(futures):
            ip_port, peak, stable, overall = future.result()
            results[ip_port] = (peak, stable, overall)

    print("\n" + "="*80)

    # 决定入选服务器
    selected_ips = [
        ip for ip, (peak, stable, _) in results.items()
        if peak >= MIN_PEAK_REQUIRED and stable >= MIN_STABLE_REQUIRED
    ]
    final_step = f"峰值≥{MIN_PEAK_REQUIRED} & 谷底≥{MIN_STABLE_REQUIRED}"

    if not selected_ips:
        print("❌ 没有完全达标服务器，进入降级模式...")
        selected_ips = [
            ip for ip, (peak, stable, _) in results.items()
            if peak >= FALLBACK_PEAK and stable >= FALLBACK_STABLE
        ]
        final_step = f"降级模式：峰值≥{FALLBACK_PEAK} & 谷底≥{FALLBACK_STABLE}"

    if not selected_ips:
        best_ip = max(results, key=lambda x: results[x][0])
        selected_ips = [best_ip]
        peak, stable, _ = results[best_ip]
        final_step = f"保底最快：峰值 {peak:.2f} / 谷底 {stable:.2f}"

    print(f"✅ 最终入选 {len(selected_ips)} 个服务器（标准：{final_step}）\n")

    # 核心：按原始文件顺序处理，只保留达标服务器的频道行
    final_output = []
    selected_set = set(selected_ips)  # 快速查找用 set

    for original_line in all_lines:
        line = original_line.strip()

        # 非频道行全部保留（标题、分组、空行、公告等）
        if not ("," in line and "http://" in line):
            final_output.append(original_line.rstrip())
            continue

        # 是频道行，判断所属 IP 是否入选
        try:
            _, url_part = line.split(",", 1)
            match = re.search(r'http://(.*?)/', url_part)
            if match:
                ip_port = match.group(1)
                if ip_port in selected_set:
                    final_output.append(original_line.rstrip())  # 保留原始完整行
        except:
            # 解析失败的行也保留（安全起见）
            final_output.append(original_line.rstrip())

    # 写入输出文件
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(final_output).rstrip() + "\n")

    print(f"\n🎯 筛选完成！输出文件：{OUTPUT_FILE}")
    print(f" 已按原始分类结构和顺序保留达标服务器的频道")


if __name__ == "__main__":
    main()
