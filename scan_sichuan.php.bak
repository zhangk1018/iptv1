<?php
error_reporting(E_ALL & ~E_WARNING & ~E_NOTICE);
date_default_timezone_set('Asia/Shanghai');

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

$output_file = "all_telecom_list.m3u";
$logo_base = "https://gcore.jsdelivr.net/gh/taksssss/tv/icon/";

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

echo "--- 开始深度扫描 (全量不限服务器数量) ---\n";
$final_m3u = "#EXTM3U x-tvg-url=\"https://live.fanmingming.com/e.xml\"\n";

foreach ($sources as $prov_name => $urls) {
    echo "\n[整理省份: $prov_name]\n";
    
    $ips_raw = fetch_data($urls['ip']);
    $rtps_raw = fetch_data($urls['rtp']);
    
    if (!$ips_raw || !$rtps_raw) {
        echo "  [Error] 无法获取源数据\n"; continue;
    }

    preg_match_all('/(\d+\.\d+\.\d+\.\d+:\d+)/', $ips_raw, $matches);
    $ip_list = array_unique($matches[1]);
    echo "  待测 IP 总数: " . count($ip_list) . "\n";

    $channels = [];
    foreach (explode("\n", $rtps_raw) as $line) {
        $line = trim($line);
        if (strpos($line, ',') !== false) {
            list($cname, $rtp) = explode(',', $line);
            $channels[] = ['name' => trim($cname), 'rtp' => trim($rtp)];
        }
    }

    foreach ($ip_list as $server) {
        echo "  探测服务器: $server ... ";
        list($host, $port) = explode(':', $server);
        
        $fp = @fsockopen($host, $port, $errno, $errstr, 0.8);
        if ($fp) {
            fclose($fp);
            echo "[√]\n";
            
            foreach ($channels as $chan) {
                $name = $chan['name'];
                $logo = $logo_base . $name . ".png";
                $raw_url = "http://{$server}/rtp/{$chan['rtp']}";
                
                // 构造 M3U 结构
                $final_m3u .= "#EXTINF:-1 tvg-id=\"$name\" tvg-logo=\"$logo\" group-title=\"$prov_name\",$name\n";
                // 关键：对整个 URL 进行编码
                $final_m3u .= urlencode($raw_url) . "\n";
            }
        } else {
            echo "[x]\n";
        }
    }
}

file_put_contents($output_file, $final_m3u);
echo "\n--- 扫描结束，结果已存至 $output_file ---\n";
