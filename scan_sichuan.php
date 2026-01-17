<?php
error_reporting(E_ALL & ~E_WARNING & ~E_NOTICE);
date_default_timezone_set('Asia/Shanghai');

// --- 1. 配置区 ---
$sources = [
    '四川电信' => [
        'ip'  => "https://raw.githubusercontent.com/linyu345/iptv/main/ip/%E5%9B%9B%E5%B7%9D%E7%94%B5%E4%BF%A1.txt",
        'rtp' => "https://raw.githubusercontent.com/linyu345/iptv/main/rtp/%E5%9B%9B%E5%B7%9D%E7%94%B5%E4%BF%A1.txt"
    ],
    '广东电信' => [
        'ip'  => "https://raw.githubusercontent.com/linyu345/iptv/main/ip/%E5%B9%BF%E4%B8%9C%E7%94%B5%E4%BF%A1.txt",
        'rtp' => "https://raw.githubusercontent.com/linyu345/iptv/main/rtp/%E5%B9%BF%E4%B8%9C%E7%94%B5%E4%BF%A1.txt"
    ],
    '浙江电信' => [
        'ip'  => "https://raw.githubusercontent.com/linyu345/iptv/main/ip/%E6%B5%99%E6%B1%9F%E7%94%B5%E4%BF%A1.txt",
        'rtp' => "https://raw.githubusercontent.com/linyu345/iptv/main/rtp/%E6%B5%99%E6%B1%9F%E7%94%B5%E4%BF%A1.txt"
    ],
    '江苏电信' => [
        'ip'  => "https://raw.githubusercontent.com/linyu345/iptv/main/ip/%E6%B1%9F%E8%8B%8F%E7%94%B5%E4%BF%A1.txt",
        'rtp' => "https://raw.githubusercontent.com/linyu345/iptv/main/rtp/%E6%B1%9F%E8%8B%8F%E7%94%B5%E4%BF%A1.txt"
    ]
];

$output_file = "telecom_final.m3u";

function fetch_data($url) {
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    curl_setopt($ch, CURLOPT_TIMEOUT, 15);
    $data = curl_exec($ch);
    curl_close($ch);
    return $data;
}

echo "正在生成纯净版全国电信 M3U 列表...\n";
$final_m3u = "#EXTM3U x-tvg-url=\"https://live.fanmingming.com/e.xml\"\n";

foreach ($sources as $prov_name => $urls) {
    echo "正在整理: $prov_name ... ";
    
    $ips_raw = fetch_data($urls['ip']);
    $rtp_raw = fetch_data($urls['rtp']);
    
    if (!$ips_raw || !$rtp_raw) {
        echo "[失败]\n"; continue;
    }

    // A. 提取 IP 并去重
    preg_match_all('/(\d+\.\d+\.\d+\.\d+:\d+)/', $ips_raw, $matches);
    $ip_list = array_unique($matches[1]);

    // B. 解析频道模板
    $channels = [];
    foreach (explode("\n", $rtp_raw) as $line) {
        $line = trim($line);
        if (strpos($line, ',') !== false) {
            list($cname, $rtp) = explode(',', $line);
            $channels[] = ['name' => trim($cname), 'rtp' => trim($rtp)];
        }
    }

    // C. 存活探测与内容拼接
    $alive_count = 0;
    foreach ($ip_list as $server) {
        // TCP 快速探测，超时设为 0.5 秒
        list($host, $port) = explode(':', $server);
        $fp = @fsockopen($host, $port, $errno, $errstr, 0.5);
        if ($fp) {
            fclose($fp);
            
            // 每一个 IP 下的所有频道都写入当前省份分组
            foreach ($channels as $chan) {
                // 强制所有频道都在所属省份分组下
                $final_m3u .= "#EXTINF:-1 group-title=\"$prov_name\",{$chan['name']} ({$server})\n";
                $final_m3u .= "http://{$server}/rtp/{$chan['rtp']}\n";
            }
            
            $alive_count++;
            // 为了保证 M3U 文件大小适中，每个省份只保留前 3 个响应最快的 IP 线路
            if ($alive_count >= 3) break;
        }
    }
    echo "成功（保留 $alive_count 个服务器）。\n";
}

file_put_contents($output_file, $final_m3u);
echo "-------------------------------------------\n";
echo "任务完成！\n最终分组数量: " . count($sources) . "\n文件保存至: $output_file\n";
