import os
import re
import time
import requests
import concurrent.futures
import sys

# ===============================
# 配置区
# ===============================
INPUT_FILE = "live.txt"
OUTPUT_FILE = "livezubo.txt"
CHECK_COUNT = 2
TEST_DURATION = 12

# 筛选标准（可自行调整）
MIN_PEAK_REQUIRED   = 0.80
MIN_STABLE_REQUIRED = 0.40

# 降级标准
FALLBACK_PEAK   = 0.60
FALLBACK_STABLE = 0.25

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
    test_targets = [u for n, u in channels if "CCTV1" in n or "CCTV5" in n][:CHECK_COUNT]
    if len(test_targets) < CHECK_COUNT:
        test_targets = [c[1] for c in channels[:CHECK_COUNT]]

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
        f"峰值:{best_peak:5.2f}  谷底参考:{best_stable:5.2f}  整体:{best_overall:5.2f} MB/s   {best_url[:70]}\n"
    )
    sys.stdout.flush()

    return ip_port, best_peak, best_stable, best_overall


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

    # 筛选服务器
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

    # ===================== 输出部分 - 增加去重 =====================
    try:
        from fofa_fetch import CHANNEL_CATEGORIES
    except ImportError:
        print("❌ 无法导入 CHANNEL_CATEGORIES，请检查 fofa_fetch.py")
        return

    final_output = [l for l in other_info if "#genre#" in l or "更新时间" in l]
    final_output.append("")

    for category, ch_list in CHANNEL_CATEGORIES.items():
        category_added = False

        for std_name in ch_list:
            # 用 dict 存储 url → (peak, stable) ，天然去重
            url_info = {}

            for ip in selected_ips:
                for name, url_part in ip_groups.get(ip, []):
                    if name == std_name:
                        peak, stable, _ = results[ip]
                        # 如果已有相同url，取更好的评分
                        if url_part not in url_info or (peak, stable) > url_info[url_part]:
                            url_info[url_part] = (peak, stable)

            if not url_info:
                continue

            # 按 (峰值, 谷底) 降序排序
            sorted_entries = sorted(
                url_info.items(),
                key=lambda x: (x[1][0], x[1][1]),
                reverse=True
            )

            # 只取最好的那一个（已去重）
            if sorted_entries:
                if not category_added:
                    final_output.append(f"{category},#genre#")
                    category_added = True
                
                best_url, _ = sorted_entries[0]
                final_output.append(f"{std_name},{best_url}")

        if category_added:
            final_output.append("")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(final_output).rstrip() + "\n")

    print(f"\n🎯 筛选完成！输出文件：{OUTPUT_FILE}")
    print(f"   已保留 {len(selected_ips)} 个服务器源，同频道链接已去重")


if __name__ == "__main__":
    main()
