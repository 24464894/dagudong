"""跟昨天比：把今天的 data.json 和上一份快照 history/YYYY-MM-DD.json 比對，產生 diff.json。

用法（在 repo 根目錄或 pipeline 資料夾都可以）：python pipeline/make_diff.py
輸出 diff.json（repo 根目錄），格式見 docs/DATA_SCHEMA.md。
沒有上一份快照時（第一次跑），prev 是 null、items 是空的。
"""
import glob
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def sig_key(s):
    return (s.get("k"), s.get("d"), s.get("x"))


def find_prev(today):
    snaps = []
    for f in glob.glob(os.path.join(ROOT, "history", "????-??-??.json")):
        day = os.path.basename(f)[:10]
        if day < today:
            snaps.append((day, f))
    return max(snaps) if snaps else (None, None)


def main():
    cur = load(os.path.join(ROOT, "data.json"))
    today = cur["today"]
    prev_day, prev_file = find_prev(today)
    out = {"today": today, "prev": prev_day, "summary": {}, "items": []}

    if prev_file:
        old = load(prev_file)
        old_cos = {c["c"]: c for c in old.get("cos", [])}
        for c in cur.get("cos", []):
            o = old_cos.get(c["c"], {"s": [], "p": None})
            old_keys = {sig_key(s) for s in o.get("s", [])}
            new_keys = {sig_key(s) for s in c.get("s", [])}
            added = [s for s in c.get("s", []) if sig_key(s) not in old_keys]
            gone = [s for s in o.get("s", []) if sig_key(s) not in new_keys]
            p_old, p_new = o.get("p"), c.get("p")
            p_changed = p_old is not None and p_new is not None and abs(p_new - p_old) >= 0.01
            k_old, k_new = len(set(o.get("k", []))), len(set(c.get("k", [])))
            if added or gone or p_changed or (p_old is None) != (p_new is None):
                item = {"c": c["c"], "n": c["n"], "m": c.get("m", "")}
                if added:
                    item["new"] = added
                if gone:
                    item["gone"] = gone
                if p_changed or (p_old is None) != (p_new is None):
                    item["p"] = [p_old, p_new]
                if k_old < 2 <= k_new:
                    item["chain"] = True  # 今天起同時亮兩個燈以上
                out["items"].append(item)
                for s in added:
                    out["summary"][s["k"]] = out["summary"].get(s["k"], 0) + 1
        out["items"].sort(key=lambda i: (-len(i.get("new", [])), i["c"]))

    with open(os.path.join(ROOT, "diff.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    if prev_day:
        print(f"跟 {prev_day} 比：{len(out['items'])} 家有變化，新訊號 {sum(out['summary'].values())} 筆")
    else:
        print("還沒有上一份快照，diff.json 先留空；明天起就會有「跟昨天比」")
    return 0


if __name__ == "__main__":
    sys.exit(main())
