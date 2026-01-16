<?php
// 屏蔽不必要的警告
error_reporting(E_ALL & ~E_WARNING & ~E_NOTICE);
date_default_timezone_set('Asia/Shanghai');

// --- 配置区 ---
$ip_url = "https://raw.githubusercontent.com/linyu345/iptv/refs/heads/main/ip/%E9%87%8D%E5%BA%86%E5%B8%82%E8%81%94%E9%80%9A.txt";
$rtp_url = "https://raw.githubusercontent.com/linyu345/iptv/main/rtp/%E5%9B%9B%E5%B7%9D%E7%94%B5%E4%BF%A1.txt";
$output_file = "sc_telecom.m3u";

// --- 1. 下载源数据 ---
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

echo "开始下载四川电信资源...\n";
$ips_raw = fetch_data($ip_url);
$rtps_raw = fetch_data($rtp_url);

if (!$ips_raw || !$rtps_raw) die("数据源获取失败，检查 GitHub 网络。\n");

// --- 2. 筛选带端口的有效 IP ---
preg_match_all('/(\d+\.\d+\.\d+\.\d+:\d+)/', $ips_raw, $matches);
$ip_list = array_unique($matches[1]);
echo "找到有效格式服务器: " . count($ip_list) . " 个\n";

// --- 3. 解析频道列表 (处理 4K 逻辑) ---
$channels = [];
$lines = explode("\n", $rtps_raw);
foreach ($lines as $line) {
    if (strpos($line, ',') !== false) {
        list($name, $rtp) = explode(',', trim($line));
        $channels[] = [
            'name' => trim($name),
            'rtp' => trim($rtp),
            'is_4k' => (stripos($name, '4K') !== false)
        ];
    }
}

// --- 4. 探测服务器端口存活 ---
echo "正在执行服务器端口扫描...\n";
$alive_servers = [];
foreach ($ip_list as $server) {
    list($host, $port) = explode(':', $server);
    $connection = @fsockopen($host, $port, $errno, $errstr, 1.5); // 1.5秒超时
    if ($connection) {
        echo "[√] 服务器在线: $server\n";
        $alive_servers[] = $server;
        fclose($connection);
    }
    // 限制扫描出的服务器数量，防止 M3U 文件由于重复路径变得巨大
    if (count($alive_servers) >= 15) break; 
}

// --- 5. 生成 M3U 列表 ---
$m3u_content = "#EXTM3U x-tvg-url=\"https://live.fanmingming.com/e.xml\"\n";

foreach ($alive_servers as $server) {
    foreach ($channels as $chan) {
        $group = $chan['is_4k'] ? "四川4K" : "四川电信";
        $m3u_content .= "#EXTINF:-1 group-title=\"$group\",{$chan['name']} ({$server})\n";
        // 拼接 udpxy 常用格式 /rtp/
        $m3u_content .= "http://{$server}/rtp/{$chan['rtp']}\n";
    }
}

file_put_contents($output_file, $m3u_content);
echo "扫描结束，存活服务器 " . count($alive_servers) . " 个，结果已写入 $output_file\n";
