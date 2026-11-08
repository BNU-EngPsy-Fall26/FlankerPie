#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlankerPie · 数据下载脚本（仅项目所有者使用）
==========================================================
从课程服务器导出本项目的全部数据。下载密钥是保密的：
不要把它写进任何会被提交/分享的文件，推荐用环境变量传入。

用法
----
  # Windows PowerShell
  $env:HW2_KEY = "你的下载密钥"; python fetch_data.py

  # Windows CMD / Git Bash
  set HW2_KEY=你的下载密钥        (CMD)
  export HW2_KEY=你的下载密钥     (bash)

  # 或直接用参数（注意别截图/别 commit）
  python fetch_data.py --key kJFx... -o data/export_N2DRAL.json
  python fetch_data.py --format csv -o data/export_N2DRAL.csv

仅依赖标准库。
"""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

SERVER = "https://attention-lab-production.up.railway.app"


def main():
    ap = argparse.ArgumentParser(description="下载本项目的全部实验数据")
    ap.add_argument("--code", default="N2DRAL", help="项目码（公开，默认 N2DRAL）")
    ap.add_argument("--key", default=os.environ.get("HW2_KEY"), help="下载密钥（保密；默认读环境变量 HW2_KEY）")
    ap.add_argument("--format", choices=["json", "csv"], default="json", help="导出格式")
    ap.add_argument("-o", "--out", default=None, help="输出文件路径")
    args = ap.parse_args()

    if not args.key:
        sys.exit("未提供下载密钥：请设置环境变量 HW2_KEY 或用 --key 传入。\n"
                 "注意：密钥是保密的，不要写进任何会被 git 提交的文件。")

    url = f"{SERVER}/api/hw2/export?key={urllib.parse.quote(args.key)}&format={args.format}"
    out = Path(args.out) if args.out else Path(f"data/export_{args.code}.{args.format}")
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"正在下载 {args.code} 的数据（{args.format}）…")
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            body = r.read()
    except Exception as e:
        sys.exit(f"下载失败：{e}")

    out.write_bytes(body)
    size_kb = len(body) / 1024
    print(f"已保存：{out}（{size_kb:.1f} KB）")

    if args.format == "json":
        try:
            data = json.loads(body)
            records = data.get("records", [])
            print(f"项目 {data.get('project', '?')}：{len(records)} 条提交记录")
            if not records:
                print("（还没有被试提交数据；把实验链接发出去，做完后再来下载。）")
            for rec in records:
                n = len(rec.get("trials") or [])
                print(f"  · {rec.get('experiment', '?')} ｜ {rec.get('participant', '?')} ｜ {n} 试次")
        except json.JSONDecodeError:
            print("（返回内容不是合法 JSON，请检查密钥是否正确）")


if __name__ == "__main__":
    import urllib.parse  # noqa: E402  (放这里避免顶部 import 顺序困扰)

    main()
