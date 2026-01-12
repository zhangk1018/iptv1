# -*- coding: utf-8 -*-
"""
将安徽组播源 zubo.txt 转换为只含安徽电信分组的 m3u 播放列表
自动添加台标和 EPG
"""

import requests
import re
import sys
import io
from datetime import datetime

# 强制 stdout 支持中文输出（GitHub Actions 日志需要）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ==================== 配置 ====================
INPUT_URL = "https://raw.githubusercontent.com/linyu345/2026/refs/heads/main/py/安徽组播/zubo.txt"

OUTPUT_FILE = "安徽电信组播.m3u"

LOGO_BASE = "https://gcore.jsdelivr.net/gh/kenye201/TVlog/img/"
EPG_URL = "https://live.fanmingming.cn/e.xml"

# 只保留以这些开头的分组
TARGET_GROUP_PREFIXES = ["安徽电信"]

# ==============================================

def download_txt(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        
        # 强制 UTF-8 解码，错误字符替换
        content = response.content.decode('utf-8', errors='replace')
        
        print("源文件下载成功，前 8 行预览：")
        print("\n".join(content.splitlines()[:8]))
        print("-" * 60)
        
        return content.splitlines()
    except Exception as e:
        print(f"下载源文件失败: {str(e)}")
        return []

def is_genre_line(line):
    line = line.strip()
    return line.endswith(',#genre#') or line == '#genre#'

def get_group_name(line):
    line = line.strip()
    if ',#genre#' in line:
        return line.split(',#genre#')[0].strip()
    return ""

def is_target_group(group_name):
    if not group_name:
        return False
    return any(group_name.startswith(prefix) for prefix in TARGET_GROUP_PREFIXES)

def clean_channel_name_for_logo(name):
    """简单清洗频道名用于匹配台标"""
    name = re.sub(r'(HD|高清|超清|标清|4K|\d+K|\(\d+\)|Ⅰ|Ⅱ|Ⅲ)', '', name, flags=re.I)
    name = name.replace("频道", "").replace("台", "").replace("卫视", "卫视").strip()
    return name

def make_logo_url(channel_name):
    clean_name = clean_channel_name_for_logo(channel_name)
    return f"{LOGO_BASE}{clean_name}.png"

def main():
    print(f"开始处理源文件: {INPUT_URL}\n")
    
    lines = download_txt(INPUT_URL)
    if not lines:
        print("源文件为空或下载失败，程序退出。")
        return

    current_group = ""
    in_target = False
    channels = []  # (group, name, url)

    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') and not is_genre_line(line):
            continue

        if is_genre_line(line):
            current_group = get_group_name(line)
            in_target = is_target_group(current_group)
            
            if in_target:
                print(f"发现目标分组：{current_group}")
            continue

        if in_target and ',' in line:
            try:
                name, url = [x.strip() for x in line.split(',', 1)]
                if url and any(url.startswith(p) for p in ['http', 'rtp', 'udp', 'rtmp', 'mitv', 'p2p']):
                    channels.append((current_group, name, url))
            except:
                pass

    if not channels:
        print("未找到任何符合条件的安徽电信频道，m3u 文件将为空。")
    
    # 生成 m3u
    m3u = [
        "#EXTM3U",
        f'#EXTM3U x-tvg-url="{EPG_URL}"',
        f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)",
        "# 来源: 安徽组播源 → 只保留安徽电信分组",
        "# 台标来源: https://github.com/kenye201/TVlog",
        "",
    ]

    for group, name, url in channels:
        logo = make_logo_url(name)
        m3u.append(f'#EXTINF:-1 tvg-logo="{logo}" tvg-name="{name}" group-title="{group}",{name}')
        m3u.append(url)
        m3u.append("")

    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write("\n".join(m3u))
        print(f"\n转换完成！共提取 {len(channels)} 个频道")
        print(f"输出文件: {OUTPUT_FILE}")
        print("请检查仓库是否已自动提交此文件。")
    except Exception as e:
        print(f"保存 m3u 文件失败: {str(e)}")

if __name__ == "__main__":
    main()
