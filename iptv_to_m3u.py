import re
import requests

TARGET_URL = "https://raw.githubusercontent.com/linyu345/2026/refs/heads/main/py/安微组播/iptv_list.txt"
OUTPUT_FILE = "IPTV2.m3u"

LOGO_BASE = "https://gcore.jsdelivr.net/gh/kenye201/TVlog/img/"
EPG_URL = "https://live.fanmingming.cn/e.xml"

def get_logo_url(name):
    n = name.strip()
    # 去掉常见高清标识
    n = re.sub(r"[ -_]HD|高清|4K|8K|\+", "", n, flags=re.I)
    # CCTV 专门处理
    if n.upper().startswith("CCTV"):
        n = n.replace("-", "").replace(" ", "")
        if "欧洲" in n or "美洲" in n:
            n = "CCTV4"
    return f"{LOGO_BASE}{n.upper()}.png"

def parse_line(line):
    """
    拆分出频道名、分类、链接
    假设是: 名称,分类,链接
    若没有分类，则归为“未分类”
    """
    parts = [p.strip() for p in line.split(",")]
    if len(parts) == 3:
        name, group, url = parts
    elif len(parts) == 2:
        # 没有显式分类
        name = parts[0]
        # 判断第二个是不是 url
        if re.match(r"^https?://", parts[1], re.I):
            group = "未分类"
            url = parts[1]
        else:
            group = parts[1]
            url = ""
    else:
        # 不标准
        return None
    return name, group, url

def main():
    print(f"🌐 正在下载: {TARGET_URL}")
    try:
        res = requests.get(TARGET_URL, timeout=30)
        res.encoding = "utf-8"
        txt = res.text
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        return

    lines = txt.splitlines()
    m3u_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"\n']

    for line in lines:
        line = line.strip()
        if not line:
            continue

        parsed = parse_line(line)
        if not parsed:
            continue

        name, group, url = parsed
        logo = get_logo_url(name)

        # 生成 m3u 条目
        m3u_lines.append(
            f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}\n{url}\n'
        )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print("✅ 转换完成 — 分类来源于源文件！")

if __name__ == "__main__":
    main()
