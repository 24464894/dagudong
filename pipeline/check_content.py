"""白話日報 第 3 步：檢查 AI 寫的文字，合併成 content.json。

用法（在 repo 根目錄）：python pipeline/check_content.py
讀 pipeline/draft.json＋pipeline/draft_text.json，檢查每篇：
  - title、body 不能是空的，長度合理
  - 不能出現買賣建議用語
  - 文字裡的每個數字都必須出現在這篇的素材或數字卡裡（防止 AI 編數字）
沒通過的那篇改用範本文字，不會擋住發布。
輸出：content.json 和 history/content-日期.json
"""
import datetime as dt
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "pipeline")
BANNED = ["利空", "利多", "快逃", "該賣", "該買", "看好", "看壞", "看衰", "買進", "進場", "出場", "目標價",
          "飆", "暴跌", "崩盤", "抄底", "停損", "停利", "建議買", "建議賣", "穩賺", "必漲", "必跌", "明牌"]
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def nums(text):
    out = set()
    for m in NUM.findall(text or ""):
        v = m.replace(",", "")
        try:
            f = float(v)
        except ValueError:
            continue
        out.add(f)
    return out


def allowed_numbers(*texts):
    ok = set()
    for t in texts:
        for f in nums(t):
            ok |= {f, float(round(f)), round(f, 1)}
            if f >= 1000:  # 股 -> 張
                ok |= {float(round(f / 1000)), round(f / 1000, 1)}
    for t in texts:  # 日期 2026-11-01 -> 2026, 11, 1
        for y, m, d in re.findall(r"(\d{4})-(\d{2})-(\d{2})", t or ""):
            ok |= {float(y), float(int(m)), float(int(d))}
    return ok


def check(text, ok, maxlen):
    if not text or not text.strip():
        return "空白"
    if len(text) > maxlen:
        return f"太長（{len(text)} 字）"
    bad = [w for w in BANNED if w in text]
    if bad:
        return "用了禁用詞：" + "、".join(bad)
    extra = [f for f in nums(text) if f not in ok]
    if extra:
        return "出現素材裡沒有的數字：" + "、".join(f"{x:g}" for x in sorted(extra))
    return None


def main():
    draft = json.load(open(os.path.join(HERE, "draft.json"), encoding="utf-8"))
    text = json.load(open(os.path.join(HERE, "draft_text.json"), encoding="utf-8"))
    tx = text.get("items", {})
    out, all_ok, problems = [], set(), 0
    for it in draft["items"]:
        facts_txt = " ".join(f["value"] for f in it["facts"])
        ok = allowed_numbers(it["material"], facts_txt, it["d"], it["tpl_title"], it["tpl_body"])
        all_ok |= ok
        t = tx.get(it["id"], {})
        title, body = (t.get("title") or "").strip(), (t.get("body") or "").strip()
        e1, e2 = check(title, ok, 40), check(body, ok, 300)
        if e1 or e2:
            problems += 1
            print(f"✗ {it['id']}：" + "；".join(x for x in (e1 and f"標題{e1}", e2 and f"內文{e2}") if x) + " → 改用範本")
            title, body = it["tpl_title"], it["tpl_body"]
        else:
            print(f"✓ {it['id']}：{title}")
        out.append({k: it[k] for k in ("id", "rank", "type", "c", "n", "m", "facts", "src", "d")}
                   | {"title": title, "body": body})

    summary = (text.get("summary") or "").strip()
    e = check(summary, all_ok, 200)
    if e:
        print(f"✗ 今日導讀：{e} → 改用範本")
        summary = "今天整理了 " + str(len(out)) + " 件事：" + "、".join(i["title"] for i in out[:3]) + "。" if out else ""
        problems += 1

    content = {"date": draft["date"], "generatedAt": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
               "model": "ChatPlayground.ai", "summary": summary, "items": out}
    os.makedirs(os.path.join(ROOT, "history"), exist_ok=True)
    for p in (os.path.join(ROOT, "content.json"), os.path.join(ROOT, "history", f"content-{draft['date']}.json")):
        json.dump(content, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n完成：{len(out)} 篇，{problems} 處改用範本。已寫入 content.json 和 history/content-{draft['date']}.json")
    print("下一步：python pipeline/publish_content.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
