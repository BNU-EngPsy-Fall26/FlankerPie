#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地静态服务器：用于在 http://localhost 下测试（摄像头眼动需要 http/https，不能 file:// 直开）。

用法：
    python serve.py            # 默认 8765 端口
    python serve.py 9000       # 指定端口
然后浏览器打开 http://127.0.0.1:8765/
"""
import http.server
import socketserver
import sys
import os

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
os.chdir(os.path.dirname(os.path.abspath(__file__)))


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".wasm": "application/wasm",
        ".json": "application/json",
    }

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass  # 静默


if __name__ == "__main__":
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"FlankerPie 本地服务器已启动： http://127.0.0.1:{PORT}/")
        print("按 Ctrl+C 停止")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")
