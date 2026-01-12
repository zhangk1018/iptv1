import re
import requests

TARGET_URL = "https://raw.githubusercontent.com/linyu345/2026/refs/heads/main/py/%E5%AE%89%E5%BE%BD%E7%BB%84%E6%92%AD/iptv_list.txt"
OUTPUT_FILE = "IPTV2.m3u"

LOGO_BASE = "https://gcore.jsdelivr.net/gh/kenye201/TVlog/img/"
EPG_URL = "https://live.fanmingming.cn/e.xml"

CHANNEL_CATEGORIES = {
    "央视频道": ["CCTV1","CCTV2","CCTV3","CCTV4","CCTV4欧洲","CCTV4美洲","CCTV5","CCTV5+","CCTV6","CCTV7","CCTV8","CCTV9","CCTV10","CCTV11","CCTV12","CCTV13","CCTV14","CCTV15","CCTV16","CCTV17","CCTV4K","CCTV8K"],
    "卫视频道": ["湖南卫视","浙江卫视","江苏卫视","东方卫视","安徽卫视","北京卫视","广东卫视","深圳卫视"],
    "数字频道": ["CHC动作电影","CHC家庭影院","凤凰卫视中文台","凤凰卫视资讯台"],
    "湖北区域": ["湖北公共新闻","湖北经视频道","湖北综合频道"],
    "安徽区域": ["安徽经济生活","安徽公共频道","安徽影视频道"],
    "大湾区": ["广东珠江","广东体育","广东新闻"]
}

def get_logo_url(name):
    n = name.strip()
    n = re.sub(r"[ -_]HD|高清|4K|8K|\+", "", n, flags=re.I)
    if n.upper().startswith("CCTV"):
        n = n.replace("-", "").replace(" ", "")
        if "欧洲" in n or "美洲" in n:
            n = "CCTV4"
    return f"{LOGO_BASE}{n.upper()}.png"

def match_group(name):
    for group, chans in CHANNEL_CATEGORIES.items():
        if name in chans:
            return group
    return "其他频道"

def main():
    print("📡 下载频道列表中...")
    res = requests.get(TARGET_URL, timeout=30)
    res.encoding = "utf-8"

    m3u = [f'#EXTM3U x-tvg-url="{EPG_URL}"\n']

    for line in res.text.splitlines():
        line = line.strip()
        if not line or ",#genre#" in line:
            continue

        if "," not in line:
            continue

        name, url = line.split(",", 1)
        name, url = name.strip(), url.strip()

        group = match_group(name)
        logo = get_logo_url(name)

        m3u.append(
            f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}\n{url}\n'
        )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u))

    print("✅ 所有分类频道已成功转换为 m3u")

if __name__ == "__main__":
    main()
