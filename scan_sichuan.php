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

// 统一文件名，建议用这个名字
$output_file = "all_telecom_list.m3u";

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

echo "--- 准备生成 M3U 列表 ---\n";
$final_m3u = "#EXTM3U x-tvg-url=\"https://live.fanmingming.com/e.xml\"\n";

foreach ($sources as $prov_name => $urls) {
    echo "\n[省份分类: $prov_name]\n";
    
    $ips_raw = fetch_data($urls['ip']);
    $rtp_raw = fetch_data($urls['rtp']);
    
    if (!$ips_raw || !$rtp_raw) {
        echo "  x 获取源数据失败，跳过。\n"; continue;
    }

    preg_match_all('/(\d+\.\d+\.\d+\.\d+:\d+)/', $ips_raw, $matches);
    $ip_list = array_unique($matches[1]);
    echo "  找到 " . count($ip_list) . " 个待测服务器\n";

    $channels = [];
    foreach (explode("\n", $rtp_raw) as $line) {
        $line = trim($line);
        if (strpos($line, ',') !== false) {
            list($cname, $rtp) = explode(',', $line);
            $channels[] = ['name' => trim($cname), 'rtp' => trim($rtp)];
        }
    }

    $alive_count = 0;
    foreach ($ip_list as $server) {
        list($host, $port) = explode(':', $server);
        // 增加详细过程显示
        echo "  正在探测 -> $server ... ";
        
        $fp = @fsockopen($host, $port, $errno, $errstr, 1.0); // 稍微延长探测时间保证准确性
        if ($fp) {
            fclose($fp);
            echo " [√ 在线]\n";
            
            foreach ($channels as $chan) {
                $final_m3u .= "#EXTINF:-1 group-title=\"$prov_name\",{$chan['name']} ({$server})\n";
                $final_m3u .= "http://{$server}/rtp/{$chan['rtp']}\n";
            }
            
            $alive_count++;
            if ($alive_count >= 3) {
                echo "  (该省份已找齐 3 个可用服务器，停止继续探测)\n";
                break;
            }
        } else {
            echo " [x 离线]\n";
        }
    }
}

file_put_contents($output_file, $final_m3u);
echo "\n--- 任务完成，结果保存至 $output_file ---\n";
