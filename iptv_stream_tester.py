import os
import subprocess
import concurrent.futures
import requests

INPUT_FILE = "IPTV.txt"
SMOOTH_FILE = "IPTV_smooth.txt"
BAD_FILE = "IPTV_bad.txt"

# 测试参数（针对公网 udpxy 优化）
TEST_DURATION = 20       # 给源更多时间响应（公网慢）
CONNECT_TIMEOUT = 8      # 初始连接超时
THREADS = 8              # 线程少一点，避免 runner 资源不足

def test_stream(url_with_operator):
    url = url_with_operator.split("$")[0].strip()

    # 第一步：快速 curl 测试是否能连通（避免完全死链）
    try:
        head = requests.head(url, timeout=CONNECT_TIMEOUT, allow_redirects=True, stream=True)
        if head.status_code >= 400:
            return False, url_with_operator, f"HTTP {head.status_code}"
    except:
        return False, url_with_operator, "连接失败"

    # 第二步：用 ffprobe 探测（宽松模式）
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",                     # 不输出任何日志，只看结果
            "-rw_timeout", "20000000",         # 20秒读超时
            "-timeout", "15000000",            # 连接超时
            "-i", url,
            "-t", str(TEST_DURATION),
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1"
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=TEST_DURATION + 15)

        stdout = result.stdout.decode(errors="ignore").strip()

        # 只要能输出 duration（哪怕是 0.5 秒），就算通过
        if stdout and float(stdout) > 0:
            return True, url_with_operator, f"通过 (duration={stdout}s)"

        # 如果没拿到 duration，但进程正常退出（returncode=0），也算勉强通过（很多源就这样）
        if result.returncode == 0:
            return True, url_with_operator, "可打开（无duration但正常）"

        return False, url_with_operator, "ffprobe 失败"

    except subprocess.TimeoutExpired:
        return False, url_with_operator, "ffprobe 超时"
    except Exception as e:
        return False, url_with_operator, f"异常: {str(e)}"

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 未找到 {INPUT_FILE}")
        return

    # 读取所有行
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        all_lines = [line.strip() for line in f]

    # 分离头部/分类 和 频道源
    header_lines = []
    stream_lines = []
    for line in all_lines:
        if not line or ",#genre#" in line or "更新时间" in line or "Disclaimer" in line:
            header_lines.append(line)
        elif "," in line and "$" in line:
            stream_lines.append(line)

    print(f"🔍 发现 {len(stream_lines)} 个源，开始宽松测试（{THREADS} 线程，每源最多 {TEST_DURATION+CONNECT_TIMEOUT}s）...")

    smooth_streams = []
    bad_streams = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = {executor.submit(test_stream, line): line for line in stream_lines}
        for future in concurrent.futures.as_completed(futures):
            ok, line, reason = future.result()
            operator = line.split("$")[-1] if "$" in line else ""
            print(f"{'✅' if ok else '❌'} {operator.ljust(10)} | {reason}")
            if ok:
                smooth_streams.append(line)
            else:
                bad_streams.append(line)

    # 写入 IPTV_smooth.txt（保留原格式：头部 + 分类 + 流畅源）
    with open(SMOOTH_FILE, "w", encoding="utf-8") as f:
        for line in header_lines:
            f.write(line + "\n")
        f.write("\n")
        for line in smooth_streams:
            f.write(line + "\n")

    # 写入坏源（可选）
    with open(BAD_FILE, "w", encoding="utf-8") as f:
        for line in bad_streams:
            f.write(line + "\n")

    print(f"\n🎉 测试完成！")
    print(f"   流畅源：{len(smooth_streams)} 条 → {SMOOTH_FILE}")
    print(f"   不通过源：{len(bad_streams)} 条 → {BAD_FILE}")
    print(f"   建议用 {SMOOTH_FILE} 替换 IPTV.txt，或用 txt_to_m3u.py 生成新 M3U")

if __name__ == "__main__":
    main()
