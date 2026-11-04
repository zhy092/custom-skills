#!/usr/bin/env python3
"""ima 知识库 OpenAPI 轻客户端（只读 + 建文件夹 + 移动）。

凭证：~/.config/ima/{client_id,api_key}，或环境变量 IMA_OPENAPI_CLIENTID/IMA_OPENAPI_APIKEY。
凭证绝不打印、绝不写入日志。

用法：
  python3 ima_openapi.py list                       # 列根目录（文件夹 + 条目）
  python3 ima_openapi.py folders                    # 只列文件夹
  python3 ima_openapi.py find "书名"                 # 归一化查重
  python3 ima_openapi.py create "《书名》"            # 建文件夹（不可逆！先 find）
  python3 ima_openapi.py create "《书名》" --apply    # 同上，不带 --apply 只预演
"""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request

BASE = "https://ima.qq.com"
KB_ID_DEFAULT = "ima_kb_xpWetnzE"   # 书籍播客
CONF_DIR = os.path.expanduser("~/.config/ima")


def _cred():
    cid = os.environ.get("IMA_OPENAPI_CLIENTID", "")
    aky = os.environ.get("IMA_OPENAPI_APIKEY", "")
    # 环境变量里的 key 可能是旧的；配置文件优先
    try:
        c = open(os.path.join(CONF_DIR, "client_id")).read().strip()
        a = open(os.path.join(CONF_DIR, "api_key")).read().strip()
        if c and a:
            return c, a
    except OSError:
        pass
    if not (cid and aky):
        sys.exit("缺少 ima 凭证：~/.config/ima/{client_id,api_key} 或 IMA_OPENAPI_*")
    return cid, aky


def post(path, payload, retry=3):
    cid, aky = _cred()
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last = None
    for i in range(retry):
        req = urllib.request.Request(
            BASE + path, data=body,
            headers={"Content-Type": "application/json",
                     "ima-openapi-clientid": cid,
                     "ima-openapi-apikey": aky})
        try:
            op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            d = json.loads(op.open(req, timeout=30).read().decode())
            if d.get("code") not in (0, None):
                raise RuntimeError(f"ima code={d.get('code')} msg={d.get('msg')}")
            return d.get("data") or {}
        except Exception as e:                     # 限流 / 超时重试
            last = e
            if i < retry - 1:
                time.sleep(0.6)
    raise last


def norm(s):
    """书名归一化：去书名号/标点/空白，全半角统一，用于查重。"""
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"[《》〈〉「」【】\[\]（）()：:·,，、.。!！?？\-—_/\\\s]", "", s)
    return s.lower()


def list_dir(folder_id=None, kb_id=KB_ID_DEFAULT):
    """返回 (items, is_end)。首屏为空按 README 重试 2 次防「假空」。"""
    items, cursor = [], ""
    for page in range(100):
        p = {"knowledge_base_id": kb_id, "limit": 50, "cursor": cursor}
        if folder_id:
            p["folder_id"] = folder_id
        d = post("/openapi/wiki/v1/get_knowledge_list", p)
        batch = d.get("knowledge_list") or d.get("info_list") or []
        if not batch and not items:            # 「假空」保护
            time.sleep(0.4)
            d = post("/openapi/wiki/v1/get_knowledge_list", p)
            batch = d.get("knowledge_list") or d.get("info_list") or []
        items += batch
        cursor = d.get("next_cursor") or ""
        if d.get("is_end") or not cursor:
            break
    return items


def folders(kb_id=KB_ID_DEFAULT):
    """根目录下的文件夹：[{name, folder_id, count}]"""
    out = []
    for it in list_dir(None, kb_id):
        mid = it.get("media_id") or ""
        if str(it.get("media_type")) == "99" or mid.startswith("folder_"):
            out.append({"name": it.get("name") or it.get("title") or "",
                        "folder_id": mid,
                        "count": it.get("content_count") or ""})
    return out


def create_folder(name, kb_id=KB_ID_DEFAULT):
    d = post("/openapi/wiki/v1/create_folder",
             {"knowledge_base_id": kb_id, "kb_name": "书籍播客", "name": name})
    return d.get("media_id") or ""


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd = args[0]
    if cmd == "list":
        for it in list_dir(None):
            kind = "DIR " if str(it.get("media_type")) == "99" else "FILE"
            print(f'{kind} {it.get("media_id")}  {it.get("name") or it.get("title")}')
    elif cmd == "folders":
        fs = folders()
        print(f"共 {len(fs)} 个文件夹")
        for f in fs:
            print(f'  {f["folder_id"]}  {f["name"]}')
    elif cmd == "find":
        target = norm(args[1])
        hits = [f for f in folders() if target and (target in norm(f["name"]) or norm(f["name"]) in target)]
        print("查重结果:", "已存在" if hits else "未找到")
        for h in hits:
            print(f'  {h["folder_id"]}  {h["name"]}')
    elif cmd == "create":
        name = args[1]
        apply = "--apply" in args
        target = norm(name)
        hits = [f for f in folders() if target and (target in norm(f["name"]) or norm(f["name"]) in target)]
        if hits:
            print("已存在同名/近名文件夹，拒绝创建：")
            for h in hits:
                print(f'  {h["folder_id"]}  {h["name"]}')
            return
        if not apply:
            print(f"[预演] 将在「书籍播客」根目录创建：{name}")
            print("确认无误后加 --apply 执行（不可删除）")
            return
        mid = create_folder(name)
        print(f"已创建 {name} -> {mid}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
