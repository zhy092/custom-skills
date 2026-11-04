#!/usr/bin/env python3
"""从本机 Chrome 解出微信读书登录态，写成 /tmp/wr_cookies3.json 供脚本使用。

原理：Chrome cookie 用 keychain「Chrome Safe Storage」派生 AES-128-CBC key 加密；
meta.version >= 24 时明文前 32 字节是 SHA256(host_key)，要丢掉。

用法: python3 wr_session.py
"""
import json
import shutil
import sqlite3
import subprocess
import hashlib
import os

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

CHROME = os.path.expanduser("~/Library/Application Support/Google/Chrome/Default/Cookies")
OUT = "/tmp/wr_cookies3.json"


def load_key():
    pw = subprocess.check_output(
        ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage", "-a", "Chrome"],
        text=True).strip()
    return hashlib.pbkdf2_hmac("sha1", pw.encode(), b"saltysalt", 1003, 16)


def decrypt(host, ev, key):
    if not ev:
        return ""
    if ev[:3] not in (b"v10", b"v11"):
        return ev.decode("utf-8", "ignore")
    d = Cipher(algorithms.AES(key), modes.CBC(b" " * 16)).decryptor().update(ev[3:])
    d = d[: -d[-1]]
    if d[:32] == hashlib.sha256(host.encode()).digest():
        d = d[32:]
    return d.decode("utf-8", "ignore")


def main():
    shutil.copy(CHROME, "/tmp/ck_live.db")      # 避免锁库
    key = load_key()
    rows = sqlite3.connect("/tmp/ck_live.db").execute(
        "select host_key,name,encrypted_value,value from cookies "
        "where host_key like '%weread%'").fetchall()
    ck = {n: decrypt(h, ev, key) for h, n, ev, v in rows}
    if "wr_skey" not in ck or not ck["wr_skey"]:
        raise SystemExit("缺 wr_skey：请先在 Chrome 里登录 weread.qq.com（扫码），再重跑本脚本")
    json.dump([{"name": k, "value": v, "domain": ".weread.qq.com",
                "path": "/", "secure": True, "httpOnly": False}
               for k, v in ck.items()], open(OUT, "w"))
    print(f"OK {len(ck)} 个 cookie -> {OUT}（wr_vid={ck.get('wr_vid')} skey长度={len(ck['wr_skey'])}）")


if __name__ == "__main__":
    main()
