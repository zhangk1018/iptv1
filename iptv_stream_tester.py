import os
import re
import subprocess
import concurrent.futures
from datetime import datetime

INPUT_FILE = "IPTV.txt"
SMOOTH_FILE = "IPTV_smooth.txt"
BAD_FILE = "IPTV_bad.txt"

# 测试参数（可调整）
TEST_DURATION = 15       # 测试秒数（太长慢，太短不准）
MIN_DURATION = 5         # 至少读取到多少秒内容才算流畅
MIN_FPS = 20             # 最低平均帧率
THREADS = 10             # 并行线程数

def test_stream(url_with_operator):
    url = url_with_operator.split("$")[0].strip()  # 取纯 URL 测试
    try:
        # ffprobe 命令：静默读取指定时长，输出格式信息和错误
        cmd = [
            "ffprobe",
            "-v", "error",                     # 只输出错误
            "-rw_timeout", "15000000",         # 读超时 15秒
            "-analyzeduration", "30000000",    # 分析时长 30M 微秒
            "-probesize", "10000000",          # 探测大小 10M
            "-i", url,
            "-t", str(TEST_DURATION),          # 只读指定秒数
            "-show_entries", "format=duration;stream=avg_frame_rate,width,height",
            "-of", "default=noprint_wrappers=1:nokey=1"
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=TEST_DURATION + 10)

        stdout = result.stdout.decode(errors="ignore")
        stderr = result.stderr.decode(errors="ignore")

        # 检查严重错误
        if any(keyword in stderr.lower() for keyword in ["error", "invalid", "timeout", "packet loss", "failed"]):
            return False, url_with_operator, f"错误: {stderr.strip()[:100]}"

        lines = stdout.strip().split("\n")
        if len(lines) < 4:
            return False, url_with_operator, "无法获取流信息"

        duration_str = lines[0]
        fps_str = lines[1]
        width = lines[2]
        height = lines[3]

        if not duration_str or float(duration_str) < MIN_DURATION:
            return False, url_with_operator, f"读取时长不足 ({duration_str}s)"

        if "/" in fps_str:
            num, den = map(int, fps_str.split("/"))
            fps = num / den if den else 0
        else:
            fps = float(fps_str or 0)

        if fps < MIN_FPS:
            return False, url_with_operator, f"帧率太低 ({fps:.1f} fps)"

        if not width or not height or int(width) <= 0 or int(height) <= 0:
            return False, url_with_operator, "无有效视频分辨率"

        return True, url_with_operator, f"流畅 (≈{fps:.1f}fps, {width}x{height}, {duration_str}s)"

    except subprocess.TimeoutExpired:
        return False, url_with_operator, "超时"
    except Exception as e:
        return False, url_with_operator, f"异常: {str(e)}"

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 未找到 {INPUT_FILE}")
        return

    # 读取所有频道行（跳过分类、更新时间）
    lines = []
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or ",#genre#" in line or "更新时间" in line or "Disclaimer" in line:
                lines.append(line)  # 保留头部信息
                continue
            if "," in line and "$" in line:
                lines.append(line)

    # 只测试频道源
    stream_lines = [line for line in lines if "," in line and "$" in line]
    print(f"🔍 发现 {len(stream_lines)} 个源，开始多线程测试（{THREADS} 线程，每源 {TEST_DURATION} 秒）...")

    smooth_lines = [line for line in lines if not ("," in line and "$" in line)]  # 头部
    bad_lines = [line for line in lines if not ("," in line and "$" in line)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = {executor.submit(test_stream, line): line for line in stream_lines}
        for future in concurrent.futures.as_completed(futures):
            ok, url_line, reason = future.result()
            print(f"{'✅' if ok else '❌'} {url_line.split('$')[-1] if '$' in url_line else ''}: {reason}")
            if ok:
                smooth_lines.append(url_line)
            else:
                bad_lines.append(url_line)

    # 写入结果（保留原分类顺序，但只保留流畅源）
    with open(SMOOTH_FILE, "w", encoding="utf-8") as f:
        for line in lines:  # 先写原头部和分类
            if ",#genre#" in line or "更新时间" in line or "Disclaimer" in line:
                f.write(line + "\n")
        f.write("\n")
        for line in smooth_lines:
            if "," in line and "$" in line:
                f.write(line + "\n")

    with open(BAD_FILE, "w", encoding="utf-8") as f:
        for line in bad_lines:
            if "," in line and "$" in line:
                f.write(line + "\n")

    print(f"\n🎉 测试完成！")
    print(f"   流畅源保存到：{SMOOTH_FILE}（共 {len(smooth_lines)} 条）")
    print(f"   不流畅源保存到：{BAD_FILE}（共 {len(bad_lines)} 条）")
    print(f"   建议用 {SMOOTH_FILE} 替换原 IPTV.txt，或生成新 M3U 用它")

if __name__ == "__main__":
    main()
