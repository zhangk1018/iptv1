<?php
// 屏蔽错误输出
error_reporting(E_ALL & ~E_WARNING & ~E_NOTICE);

// --- 配置 ---
$ip_url = "https://raw.githubusercontent.com/linyu345/iptv/main/ip/%E5%9B%9B%E5%B7%9D%E7%94%B5%E4%BF%A1.txt";
$rtp_url = "https://raw.githubusercontent.com/linyu345/iptv/main/rtp/%E5%9B%9B%E5%B7%9D%E7%94%B5%E4%BF%A1.txt";
$output_file = "sc_telecom.m3u";

// --- 获取数据 ---
function fetch($url) {
    return file_get_contents($url);
}

$ips_raw = fetch($ip_url);
$rtps_raw = fetch($rtp_url);

// 1. 筛选带端口的有效 IP
preg_match_all('/(\d+\.\d+\.\d+\.\d+:\d+)/', $ips_raw, $matches);
$ip_list = array_unique($matches[1]);

// 2. 解析频道
$channels = [];
foreach (explode("\n", $rtps_raw) as $line) {
    if (strpos($line, ',') !== false) {
        list($name, $rtp) = explode(',', trim($line));
        $channels[] = ['name' => $name, 'rtp' => $rtp];
    }
}

// 3. 扫描探测 (由于 GitHub Actions 环境没有组播，我们只探测端口存活性)
echo "正在探测服务器存活状态...\n";
$alive_servers = [];
foreach ($ip_list as $server) {
    list($host, $port) = explode(':', $server);
    $connection = @fsockopen($host, $port, $errno, $errstr, 1);
    if ($connection) {
        echo "[√] $server 端口开放\n";
        $alive_servers[] = $server;
        fclose($connection);
    }
    if (count($alive_servers) >= 10) break; // 限制数量防止生成文件过大
}

// 4. 生成 M3U
$m3u = "#EXTM3U\n";
foreach ($alive_servers as $server) {
    foreach ($channels as $chan) {
        $m3u .= "#EXTINF:-1 group-title=\"四川电信\",{$chan['name']}-{$server}\n";
        $m3u .= "http://{$server}/rtp/{$chan['rtp']}\n";
    }
}

file_put_contents($output_file, $m3u);
echo "扫描完成，生成文件：$output_file\n";
