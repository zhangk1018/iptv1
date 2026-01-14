import os
import re

# ===============================
# 配置区
# ===============================
INPUT_FILE = "livezubo.txt"          # 输入文件
OUTPUT_FILE = "IPTV.m3u"             # 输出文件
LOGO_BASE = "https://gcore.jsdelivr.net/gh/kenye201/TVlog/img/"
EPG_URL = "https://live.fanmingming.cn/e.xml"

def get_logo_url(ch_name):
    name = ch_name.strip()
    name = re.sub(r"[ -_]?(HD|高清|4K|超清|超高清|8K|plus|\+|\s*Ⅰ|Ⅱ|Ⅲ|Ⅳ|Ⅴ)$", "", name, flags=re.IGNORECASE)
    name = name.replace(" ", "").replace("&", "")
    return f"{LOGO_BASE}{name}.png"

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 找不到 {INPUT_FILE}")
        return

    print(f"正在读取 {INPUT_FILE} 并完整保留 $ 后面的所有注释...")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        out.write(f'#EXTM3U x-tvg-url="{EPG_URL}"\n\n')

        for line in lines:
            line = line.strip()
            if not line or line.endswith(",#genre#"):
                continue

            # 公告行特殊处理
            if "更新时间" in line or "GitHub" in line or "作者" in line:
                parts = line.split(",", 1)
                if len(parts) == 2:
                    title, url = parts
                    out.write(f'#EXTINF:-1 group-title="公告说明",{title.strip()}\n{url.strip()}\n\n')
                continue

            if "," in line:
                try:
                    ch_name, full_url = line.split(",", 1)   # 关键：只按第一个逗号分
                    ch_name = ch_name.strip()
                    full_url = full_url.strip()               # 只去首尾空格，内部不动！

                    logo = get_logo_url(ch_name)

                    out.write(f'#EXTINF:-1 tvg-name="{ch_name}" tvg-logo="{logo}" group-title="全部频道",{ch_name}\n')
                    out.write(f"{full_url}\n\n")              # 完整写入，包括 $河南联通 $$上海电信 等全部内容

                except Exception as e:
                    print(f"跳过错误行: {line}")

    print(f"转换完成！已生成 {OUTPUT_FILE}，$ 后面的运营商注释已100%完整保留！")

if __name__ == "__main__":
    main()
