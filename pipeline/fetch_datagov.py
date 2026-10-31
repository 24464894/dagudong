"""大股東在幹嘛：從政府資料開放平臺抓取需要的資料集。

用法：python fetch_datagov.py
只用 Python 內建模組，不用另外安裝套件。
結果存到同一層的 raw/YYYY-MM-DD/ 資料夾，並產生 fields_summary.md（各檔欄位和前幾筆資料）。
"""
import datetime
import json
import re
import ssl
import sys
import time
import urllib.request
from pathlib import Path

# 資料集編號 → 名稱（名稱只用來命名檔案）
DATASETS = {
    # 每日公告事件
    18415: "上市_每日重大訊息",
    18418: "上櫃_每日重大訊息",
    22813: "上市_內部人持股轉讓申報",
    22814: "上櫃_內部人持股轉讓申報",
    22815: "上市_內部人持股未轉讓",
    22816: "上櫃_內部人持股未轉讓",
    31613: "上市_經營權異動",
    44112: "上櫃_經營權異動",
    36818: "上市_營業範圍重大變更",
    44113: "上櫃_營業範圍重大變更",
    11760: "上市_變更交易",
    11736: "上櫃_變更交易分盤管理停止交易",
    11395: "上櫃_注意股票",
    11396: "上櫃_處置有價證券",
    11397: "上櫃_注意累計次數異常",
    48664: "上櫃_當日暫停恢復交易",
    20760: "上市_財測差異",
    20761: "上櫃_財測差異",
    # 內部人與籌碼
    22811: "上市_董監持股餘額",
    22812: "上櫃_董監持股餘額",
    43532: "上市_董監質權設定",
    43533: "上櫃_董監質權設定",
    20610: "集保_設質交付個股週統計",
    20767: "上市_董監持股不足",
    20768: "上櫃_董監持股不足",
    30919: "上市_董監持股不足連續3月",
    43534: "上櫃_董監持股不足連續3月",
    # 違規與風險
    22817: "上市_證期局裁罰",
    22818: "上櫃_證期局裁罰",
    24280: "上市_違反重訊規定",
    24281: "上櫃_違反重訊規定",
    10292: "金管會_重大裁罰",
    # 每月、每季
    18420: "上市_每月營收",
    56510: "上櫃_每月營收",
    25037: "上櫃_營收創新高",
    31612: "上市_股利分派",
    58285: "上櫃_股利分派",
    24272: "上市_董事酬金",
    24276: "上櫃_董事酬金",
    # 串接用
    18419: "上市_公司基本資料",
    25036: "上櫃_公司基本資料",
}

API = "https://data.gov.tw/api/v2/rest/dataset/{id}"
PAGE = "https://data.gov.tw/dataset/{id}"
UA = {"User-Agent": "Mozilla/5.0 (dagudong-fetch)"}
WANTED = ("csv", "json")

# Python 3.13 起預設嚴格檢查憑證格式，證交所、櫃買中心的憑證缺少
# Subject Key Identifier 會被擋。這裡只關掉這個「嚴格格式」檢查，
# 憑證鏈和網域名稱照樣驗證，不是關掉 SSL 驗證。
SSL_CTX = ssl.create_default_context()
if hasattr(ssl, "VERIFY_X509_STRICT"):
    SSL_CTX.verify_flags &= ~ssl.VERIFY_X509_STRICT


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
        return r.read(), r.headers.get("Content-Type", "")


def find_resources(ds_id):
    """回傳 [(格式, 下載網址)]。先用 API，失敗就從網頁抓連結。"""
    out = []
    try:
        body, _ = get(API.format(id=ds_id))
        data = json.loads(body.decode("utf-8"))
        for d in (data.get("result") or {}).get("distribution") or []:
            url = d.get("resourceDownloadUrl") or d.get("resourceAccessUrl")
            fmt = (d.get("resourceFormat") or "").lower()
            if url:
                out.append((fmt, url))
    except Exception as e:  # noqa: BLE001
        print(f"  API 失敗，改讀網頁：{e}")
    if not out:
        try:
            body, _ = get(PAGE.format(id=ds_id))
            html = body.decode("utf-8", "ignore")
            for url in re.findall(r'href="(https?://[^"]+)"', html):
                low = url.lower()
                if any(k in low for k in ("csv", "json", "openapi", "download")) and "data.gov.tw/dataset" not in low:
                    fmt = "csv" if "csv" in low else "json" if "json" in low else ""
                    out.append((fmt, url))
        except Exception as e:  # noqa: BLE001
            print(f"  網頁也失敗：{e}")
    # 同一個資料集常有 CSV、JSON 兩份，優先 CSV
    out.sort(key=lambda x: 0 if x[0] == "csv" else 1 if x[0] == "json" else 2)
    seen, uniq = set(), []
    for fmt, url in out:
        if url not in seen:
            seen.add(url)
            uniq.append((fmt, url))
    return uniq


def decode(raw):
    for enc in ("utf-8-sig", "cp950", "big5hkscs"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


def summarize(name, fmt, text, limit=5):
    lines = [f"## {name}（{fmt}）", ""]
    try:
        if fmt == "json" or text.lstrip().startswith(("[", "{")):
            data = json.loads(text)
            rows = data if isinstance(data, list) else next((v for v in data.values() if isinstance(v, list)), [data])
            lines.append(f"筆數：{len(rows)}")
            if rows and isinstance(rows[0], dict):
                lines.append("欄位：" + "、".join(rows[0].keys()))
                lines.append("")
                for r in rows[:limit]:
                    lines.append("- " + json.dumps(r, ensure_ascii=False)[:400])
        else:
            rows = text.splitlines()
            lines.append(f"行數：{len(rows)}")
            lines.append("")
            lines.append("```")
            lines.extend(r[:400] for r in rows[: limit + 1])
            lines.append("```")
    except Exception as e:  # noqa: BLE001
        lines.append(f"（無法解析：{e}）")
    lines.append("")
    return "\n".join(lines)


def main():
    here = Path(__file__).resolve().parent
    day = datetime.date.today().isoformat()
    outdir = here / "raw" / day
    outdir.mkdir(parents=True, exist_ok=True)
    summary = [f"# 資料集欄位摘要（{day}）", ""]
    failed = []

    for ds_id, name in DATASETS.items():
        print(f"[{ds_id}] {name}")
        res = [r for r in find_resources(ds_id) if r[0] in WANTED or not r[0]]
        if not res:
            print("  找不到下載連結")
            failed.append(f"{ds_id} {name}：找不到下載連結")
            continue
        fmt, url = res[0]
        try:
            raw, ctype = get(url, timeout=120)
            if not fmt:
                fmt = "json" if "json" in ctype else "csv"
            text = decode(raw)
            path = outdir / f"{ds_id}_{name}.{fmt}"
            path.write_text(text, encoding="utf-8")
            print(f"  OK  {len(raw):,} bytes → {path.name}")
            summary.append(f"來源：{url}\n")
            summary.append(summarize(f"{ds_id} {name}", fmt, text))
        except Exception as e:  # noqa: BLE001
            print(f"  下載失敗：{e}")
            failed.append(f"{ds_id} {name}：{e}")
        time.sleep(1)  # 不要打太快

    if failed:
        summary += ["# 失敗清單", ""] + [f"- {f}" for f in failed]
    (outdir / "fields_summary.md").write_text("\n".join(summary), encoding="utf-8")
    print()
    print(f"完成：成功 {len(DATASETS) - len(failed)}，失敗 {len(failed)}")
    print(f"資料夾：{outdir}")


if __name__ == "__main__":
    sys.exit(main())
