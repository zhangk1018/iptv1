import os
import re
import time
import requests
import concurrent.futures
import sys

# ===============================
# 配置区
# ===============================
INPUT_FILES = [
    "live.txt",
    "IPTV.txt"   
]
OUTPUT_FILE = "livezubo.txt"
CHECK_COUNT = 2
TEST_DURATION = 12

# 严格模式（推荐主力）
MIN_PEAK_REQUIRED   = 1.00
MIN_STABLE_REQUIRED = 0.90   # ← 谷底参考是关键，0.9+ 才真正稳

# 降级模式（自动触发时用）
FALLBACK_PEAK   = 0.95
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


import random  # ← 记得在脚本顶部添加这个导入

def test_ip_group(ip_port, channels):
    # 优先匹配 CCTV-4 / 湖南卫视 的常见写法（不区分大小写，兼容各种别名）
    keywords = [
        "CCTV4", "CCTV-4", "CCTV-04", "CCTV4中文国际", "CCTV-4中文国际", "中文国际", "CCTV4国际",
        "湖南卫视", "湖南", "HUNAN", "快乐大本营", "芒果"  # 芒果TV相关有时会带
    ]
    
    test_targets = []
    for name, url in channels:
        upper_name = name.upper()
        if any(kw.upper() in upper_name for kw in keywords):
            test_targets.append(url)
    
    # 如果找到的 >= CHECK_COUNT（默认2），就取前几个
    if len(test_targets) >= CHECK_COUNT:
        test_targets = test_targets[:CHECK_COUNT]
    
    # 如果不够或完全没找到，就随机补齐/全随机
    else:
        remaining = CHECK_COUNT - len(test_targets)
        other_channels = [url for n, url in channels if url not in test_targets]
        
        if other_channels:
            # 随机选 remaining 个不重复的
            random_selected = random.sample(other_channels, min(remaining, len(other_channels)))
            test_targets.extend(random_selected)
        else:
            # 极端情况：服务器只有一个频道，就全用它
            test_targets = [url for _, url in channels][:CHECK_COUNT]
    
    # 如果还是空（不可能，但防错），就跳过或用第一个
    if not test_targets:
        test_targets = [channels[0][1]] if channels else []
    
    # 下面继续原来的测试逻辑...
    best_peak = 0.0
    best_stable = 0.0
    best_overall = 0.0
    best_url = ""
    
    for url in test_targets:
        peak, stable, overall = get_realtime_speed(url)
        # 优先峰值，其次稳定性
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


# ... 其他配置不变

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

    # 继续原来的解析逻辑，使用 all_lines 代替 lines
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

    # 后面代码完全不变...

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
    # ...（前面的 for category 循环不变，收集 final_output）

    # ===================== 最终全局去重 =====================
    seen_lines = set()  # 用整行内容去重（最严格，适合你描述的重复整行情况）
    unique_output = []

    for line in final_output:
        stripped = line.strip()
        if not stripped:  # 空行保留
            unique_output.append(line)
            continue

        # 保留分类标题、头部信息（即使重复也无所谓，通常不会重复）
        if ",#genre#" in stripped or "更新时间" in stripped:
            unique_output.append(line)
            continue

        # 频道行：只添加没见过的
        if stripped not in seen_lines:
            seen_lines.add(stripped)
            unique_output.append(line)

    # 只写一次文件
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(unique_output).rstrip() + "\n")

    print(f"\n🎯 筛选完成！输出文件：{OUTPUT_FILE}")
    print(f"   已保留 {len(selected_ips)} 个服务器源，全局去重后无重复行")

if __name__ == "__main__":
    main()
