import os
import re

# ===============================
# 配置区
# ===============================
INPUT_FILE = "livezubo.txt"          # 输入文件
OUTPUT_FILE = "IPTV.m3u"             # 输出 M3U 文件
LOGO_BASE = "https://gcore.jsdelivr.net/gh/kenye201/TVlog/img/"
EPG_URL = "https://live.fanmingming.cn/e.xml"

def get_logo_url(ch_name):
    """
    根据频道名称生成台标 URL
    清理规则：去掉常见后缀，保持原始名称主体
    """
    name = ch_name.strip()
    # 移除常见高清/分辨率标识
    name = re.sub(r"[ -_]?(HD|高清|4K|超清|超高清|8K|plus|\+|\s*Ⅰ|Ⅱ|Ⅲ|Ⅳ|Ⅴ)$", "", name, flags=re.IGNORECASE)
    name = name.replace(" ", "").replace("&", "")
    
    return f"{LOGO_BASE}{name}.png"

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 错误: 找不到本地文件 {INPUT_FILE}")
        return

    print(f"📂 正在读取本地文件: {INPUT_FILE}")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 收集所有有效行（只过滤掉明显无效的行）
    valid_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 跳过纯 #genre# 行（通常是分组标记）
        if line.endswith(",#genre#"):
            continue
        # 保留公告/更新时间行
        if "更新时间" in line:
            valid_lines.append(line)
            continue
        # 保留频道行（包含逗号和 URL）
        if "," in line:
            valid_lines.append(line)

    if not valid_lines:
        print("⚠️ 未发现有效内容，取消生成 M3U")
        return

    # 生成 M3U 文件
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        out.write(f'#EXTM3U x-tvg-url="{EPG_URL}"\n\n')

        for line in valid_lines:
            # 处理公告/更新时间行
            if "更新时间" in line:
                parts = line.split(",", 1)
                if len(parts) == 2:
                    title, url = parts
                    stream_url = url.strip()
                    out.write(f'#EXTINF:-1 group-title="公告说明",{title.strip()}\n{stream_url}\n\n')
                continue

            # 处理频道行
            try:
                ch_name, stream_url = line.split(",", 1)
                ch_name = ch_name.strip()
                stream_url = stream_url.strip()  # 只去首尾空格，保留 $$ 等注释

                # 直接用原始频道名生成台标
                logo = get_logo_url(ch_name)

                # 默认分组（可以全部放“全部频道”或留空）
                group_title = "全部频道"  # 或 ""（不分组）

                # 写入 M3U
                out.write(f'#EXTINF:-1 tvg-name="{ch_name}" tvg-logo="{logo}" group-title="{group_title}",{ch_name}\n')
                out.write(f"{stream_url}\n\n")

            except Exception as e:
                print(f"⚠️ 跳过错误行: {line} -> {e}")

    print(f"✅ {OUTPUT_FILE} 生成成功（基于 {INPUT_FILE}），共处理 {len(valid_lines)} 行。")

if __name__ == "__main__":
    main()
