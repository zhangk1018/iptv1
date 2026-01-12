import re
import requests

# ===============================
# 配置区
# ===============================
TARGET_URL = "https://raw.githubusercontent.com/linyu345/2026/refs/heads/main/py/%E5%AE%89%E5%BE%BD%E7%BB%84%E6%92%AD/iptv_list.txt"
OUTPUT_FILE = "IPTV2.m3u"

LOGO_BASE = "https://gcore.jsdelivr.net/gh/kenye201/TVlog/img/"
EPG_URL = "https://live.fanmingming.cn/e.xml"


# ===============================
# 工具函数
# ===============================
def clean_group_name(text: str) -> str:
    """
    清洗分类名：
    - 去掉首尾空格
    - 去掉末尾 : ：
    """
    return text.strip().rstrip(":：")


def get_logo_url(name: str) -> str:
    """
    生成台标 URL
    - 去除 HD / 高清 / 4K / 8K 等
    - CCTV 不带横杠
    """
    n = name.strip()

    # 去掉清晰度等标识
    n = re.sub(
        r"[ -_]HD|高清|超清|4K|8K|\+|PLUS|Ⅰ|Ⅱ|Ⅲ|Ⅳ|Ⅴ",
        "",
        n,
        flags=re.IGNORECASE,
    )

    # CCTV 特殊处理
    if n.upper().startswith("CCTV"):
        n = n.replace("-", "").replace(" ", "")
        if "欧洲" in n or "美洲" in n:
            n = "CCTV4"

    return f"{LOGO_BASE}{n.upper()}.png"


def is_valid_url(url: str) -> bool:
    """
    判断是否是合法播放地址
    """
    return bool(
        re.match(r"^(https?|rtp|udp)://", url, re.IGNORECASE)
    )


# ===============================
# 主逻辑
# ===============================
def main():
    print(f"🌐 正在下载: {TARGET_URL}")

    try:
        res = requests.get(TARGET_URL, timeout=30)
        res.encoding = "utf-8"
        lines = res.text.splitlines()
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        return

    current_group = "未分类"
    m3u_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"\n']

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # ========= 分类行 =========
        if "#genre#" in line:
            raw_group = line.split(",", 1)[0]
            current_group = clean_group_name(raw_group)
            continue

        # ========= 频道行 =========
        if "," not in line:
            continue

        name, url = line.split(",", 1)
        name = name.strip()
        url = url.strip()

        if not name or not is_valid_url(url):
            continue

        logo = get_logo_url(name)

        m3u_lines.append(
            f'#EXTINF:-1 tvg-name="{name}" '
            f'tvg-logo="{logo}" '
            f'group-title="{current_group}",{name}\n'
            f'{url}\n'
        )

    # 写入文件
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print("✅ 转换完成：分类完全来自源文件，格式已清洗")


# ===============================
# 入口
# ===============================
if __name__ == "__main__":
    main()
