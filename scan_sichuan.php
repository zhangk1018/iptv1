<?php
error_reporting(E_ALL & ~E_WARNING & ~E_NOTICE);
date_default_timezone_set('Asia/Shanghai');

// --- 1. 配置区：多省份列表 ---
$provinces = [
    '四川电信' => 'sichuan',
    '广东电信' => 'guangdong',
    '浙江电信' => 'zhejiang',
    '江苏电信' => 'jiangsu'
];

$base_ip_url  = "https://raw.githubusercontent.com/linyu345/iptv/main/ip/";
$base_rtp_url = "https://raw.githubusercontent.com/linyu345/iptv/main/rtp/";
$output_file  = "all_telecom_list.m3u";

// --- 2. 核心函数 ---
function fetch_data($url) {
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    curl_setopt($ch, CURLOPT_TIMEOUT, 30);
    $data = curl_exec($ch);
    curl_close($ch);
    return $data;
}

$final_m3u = "#EXTM3U x-tvg-url=\"https://live.fanmingming.com/e.xml\"\n";

foreach ($provinces as $name => $file_part) {
    echo "--- 正在处理: $name ---\n";
    
    // 构造编码后的 URL (处理中文路径)
    $ip_url  = $base_ip_url  . urlencode($name) . ".txt";
    $rtp_url = $base_rtp_url . urlencode($name) . ".txt";
    
    $ips_raw  = fetch_data($ip_url);
    $rtps_raw = fetch_data($rtp_url);
    
    if (!$ips_raw || !$rtps_raw) {
        echo "  [跳过] $name 数据抓取失败。\n";
        continue;
    }

    // 解析 IP
    preg_match_all('/(\d+\.\d+\.\d+\.\d+:\d+)/', $ips_raw, $matches);
    $ip_list = array_unique($matches[1]);
    
    // 解析频道
    $channels = [];
    foreach (explode("\n", $rtps_raw) as $line) {
        if (strpos($line, ',') !== false) {
            list($cname, $rtp) = explode(',', trim($line));
            $channels[] = ['name' => $name . "-" . trim($cname), 'rtp' => trim($rtp)];
        }
    }

    // 探测服务器存活 (每个省份探测前 10 个)
    $alive_count = 0;
    foreach ($ip_list as $server) {
        list($host, $port) = explode(':', $server);
        $connection = @fsockopen($host, $port, $errno, $errstr, 1); 
        if ($connection) {
            echo "  [√] 在线服务器: $server\n";
            fclose($connection);
            
            // 写入 M3U 逻辑
            foreach ($channels as $chan) {
                $group = (stripos($chan['name'], '4K') !== false) ? "全国4K" : $name;
                $final_m3u .= "#EXTINF:-1 group-title=\"$group\",{$chan['name']} ({$server})\n";
                $final_m3u .= "http://{$server}/rtp/{$chan['rtp']}\n";
            }
            
            $alive_count++;
            if ($alive_count >= 5) break; // 每个省份保留 5 个最稳的服务器，防止文件太大
        }
    }
}

file_put_contents($output_file, $final_m3u);
echo "扫描结束，全国汇总文件已写入 $output_file\n";
