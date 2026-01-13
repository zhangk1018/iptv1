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
    "IPTV.txt"
    # 可以继续添加更多文件，例如 "backup.txt", "new_sources.txt"
]

OUTPUT_FILE = "livezubo.txt"
CHECK_COUNT = 2
TEST_DURATION = 12

# 严格模式（主力推荐，根据实际源池可调）
MIN_PEAK_REQUIRED = 1.10
MIN_STABLE_REQUIRED = 1.03   # 谷底参考 ≥0.9 才真正稳

# 降级模式
FALLBACK_PEAK = 0.95
FALLBACK_STABLE = 0.75

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
    keywords = [
        "CCTV4", "CCTV-4", "CCTV-04", "CCTV4中文国际", "CCTV-4中文国际", "中文国际", "CCTV4国际", "国际频道", "四套",
        "湖南卫视", "湖南", "HUNAN", "快乐大本营", "芒果", "芒果TV", "金鹰", "卫视湖南", "湖南一套"
    ]

    test_targets = []
    for name, url in channels:
        upper_name = name.upper()
        if any(kw.upper() in upper_name for kw in keywords):
            test_targets.append(url)

    if len(test_targets) >= CHECK_COUNT:
        test_targets = test_targets[:CHECK_COUNT]
    else:
        remaining = CHECK_COUNT - len(test_targets)
        other_channels = [url for n, url in channels if url not in test_targets]

        if other_channels:
            random_selected = random.sample(other_channels, min(remaining, len(other_channels)))
            test_targets.extend(random_selected)
        else:
            test_targets = [url for _, url in channels][:CHECK_COUNT]

    if not test_targets and channels:
        test_targets = [channels[0][1]]

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
        f"峰值:{best_peak:5.2f}  谷底参考:{best_stable:5.2f}  整体:{best_overall:5.2f} MB/s   测试用: {best_url[:70]}\n"
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

    ip_groups = {}
    other_info = []
    for line in all_lines:
        line = line.strip()
        if "," in line and "$" in line:
            name, url_part = line.split(",", 1)
            match = re.search(r'http://(.*?)/', url_part)
            if match:
                ip_port = match.group(1)
                ip_groups.setdefault(ip_port, []).append((name, url_part))
        elif line:
            other_info.append(line)

    print(f"\n🚀 启动筛选 | 候选服务器: {len(ip_groups)} 个 | 测试时长: {TEST_DURATION}s\n")

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(test_ip_group, ip, chs): ip for ip, chs in ip_groups.items()}
        for future in concurrent.futures.as_completed(futures):
            ip_port, peak, stable, overall = future.result()
            results[ip_port] = (peak, stable, overall)

    print("\n" + "="*70)

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

    # ===================== 输出所有入选服务器的全部频道（不重组，不限类别） =====================
    final_output = [line for line in other_info if line.strip()]  # 保留头部信息
    final_output.append("")  # 加空行

    # 收集入选服务器的所有原始频道行
    all_selected_lines = []
    for ip in selected_ips:
        for name, url_part in ip_groups.get(ip, []):
            all_selected_lines.append(f"{name},{url_part}")

    # 全局去重整行（防止源文件本身有完全相同的重复行）
    seen_lines = set()
    unique_lines = []
    for line in all_selected_lines:
        stripped = line.strip()
        if stripped and stripped not in seen_lines:
            seen_lines.add(stripped)
            unique_lines.append(line)

    final_output.extend(unique_lines)

    # 写文件
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(final_output).rstrip() + "\n")

    print(f"\n🎯 筛选完成！输出文件：{OUTPUT_FILE}")
    print(f"   已保留 {len(selected_ips)} 个服务器的所有频道（去重后共 {len(unique_lines)} 条唯一行）")


if __name__ == "__main__":
    main()
