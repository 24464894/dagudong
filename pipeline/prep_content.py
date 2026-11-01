"""白話日報 第 1 步：從 data.json 挑出今天值得寫的事件，準備好數字和素材。

用法（在 repo 根目錄）：python pipeline/prep_content.py
產生：
  pipeline/draft.json       每篇文章的固定欄位（id、公司、數字小卡、來源）＋範本文字（AI 寫壞時用）
  pipeline/draft_text.json  給 AI 填的檔案：summary 和每篇的 title / body（一開始是空的）
並在畫面印出每篇的素材，讓 AI 照著寫。

數字一律由這支程式從 data.json 算好放進 facts，AI 只負責寫白話文字。
"""
import datetime as dt
import glob
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "pipeline")
MAX_ITEMS = 10
NAMES = {"insider": "申報賣股", "control": "換老闆", "pledgeHigh": "高質押", "pledgeUp": "質押大增",
         "trade": "變更交易", "disposal": "處置", "fined": "被罰", "chain": "連環訊號"}


def zhang(shares):
    return f"{round(shares / 1000):,} 張"


def md(d):  # 2026-11-01 -> 11/1
    y, m, dd = d.split("-")
    return f"{int(m)}/{int(dd)}"


def days_between(a, b):
    return (dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days


def recent_ids(today, days=7):
    seen = set()
    for f in glob.glob(os.path.join(ROOT, "history", "content-*.json")):
        day = os.path.basename(f)[8:18]
        try:
            if 0 < days_between(today, day) <= days:
                for it in json.load(open(f, encoding="utf-8")).get("items", []):
                    seen.add(it["id"])
        except Exception:  # noqa: BLE001
            pass
    return seen


def build(D):
    today = D["today"]
    cos = {c["c"]: c for c in D["cos"]}
    mk = lambda c: cos.get(c, {}).get("m", "")  # noqa: E731
    items = []

    for x in D.get("insider", []):
        pct = x["sell"] / x["hold"] * 100 if x.get("hold") else None
        facts = [{"label": "申報賣出", "value": zhang(x["sell"])}]
        if x.get("hold"):
            facts.append({"label": "目前持有", "value": zhang(x["hold"])})
        if pct is not None:
            facts.append({"label": "占持股", "value": f"{pct:.1f}%"})
        a, b = (x.get("period") or "～").split("～")
        if a and b:
            facts.append({"label": "期間", "value": f"{md(a)}～{md(b)}"})
        items.append(dict(
            id=f"insider-{x['c']}-{x['d']}", type="insider", c=x["c"], n=x["n"], m=x.get("m") or mk(x["c"]),
            facts=facts, src="內部人持股轉讓申報", d=x["d"],
            material=f"申報人：{x['name']}（{x['who']}）；方式：{x['how']}；申報賣出 {zhang(x['sell'])}；"
                     f"目前持有 {zhang(x['hold'])}；期間 {x.get('period')}。提醒：申報不代表一定會賣完。",
            tpl_title=f"{x['n']}{x['who']}申報要賣 {zhang(x['sell'])}",
            tpl_body=f"{x['n']}的{x['who']}{x['name']}申報，{x.get('period')}之間要用{x['how']}賣出 {zhang(x['sell'])}"
                     + (f"，大約是手上持股的 {pct:.1f}%" if pct is not None else "") + "。申報轉讓不代表一定會賣完。"))

    for x in D.get("control", []):
        if days_between(today, x["d"]) <= 30:
            items.append(dict(
                id=f"control-{x['c']}-{x['d']}", type="control", c=x["c"], n=x["n"], m=x.get("m") or mk(x["c"]),
                facts=[{"label": "異動原因", "value": x["t"]}, {"label": "異動日", "value": md(x["d"])}],
                src="經營權異動", d=x["d"], material=f"類型：{x['t']}；原文：{x['x'][:220]}",
                tpl_title=f"{x['n']}經營權異動（{x['t']}）",
                tpl_body=f"{x['n']}在 {md(x['d'])} 被認定經營權異動，原因是{x['t']}。"))

    for x in D.get("fines", []):
        if days_between(today, x["d"]) <= 14:
            amt = x.get("amt")
            facts = [{"label": "開罰單位", "value": x["src"]}]
            if amt:
                facts.append({"label": "罰款", "value": f"{amt:g} 萬元"})
            items.append(dict(
                id=f"fined-{x['c']}-{x['d']}", type="fined", c=x["c"], n=x["n"], m=mk(x["c"]),
                facts=facts, src=x["src"], d=x["d"],
                material=f"事由：{x['why'][:200]}；罰款：{amt:g} 萬元" if amt else f"事由：{x['why'][:200]}",
                tpl_title=f"{x['n']}被{x['src']}開罰" + (f" {amt:g} 萬元" if amt else ""),
                tpl_body=f"{x['n']}在 {md(x['d'])} 被{x['src']}處分" + (f"，罰款 {amt:g} 萬元" if amt else "") + "。"))

    for x in D.get("disp", []):
        if x.get("d") == today:
            items.append(dict(
                id=f"disposal-{x['c']}-{x['from']}", type="disposal", c=x["c"], n=x["n"], m=mk(x["c"]) or "上櫃",
                facts=[{"label": "處置期間", "value": f"{md(x['from'])}～{md(x['to'])}"}],
                src="櫃買中心 處置有價證券", d=x["d"], material=f"原因：{x['why']}；期間 {x['from']}～{x['to']}",
                tpl_title=f"{x['n']}{md(x['from'])} 起被處置",
                tpl_body=f"{x['n']}因為{x['why']}，{md(x['from'])}～{md(x['to'])} 被列為處置股票，交易方式會受到限制。"))

    chains = [c for c in D["cos"] if len(c.get("k", [])) >= 2]
    chains.sort(key=lambda c: (len(c["k"]), max(s["d"] for s in c["s"])), reverse=True)
    for c in chains[:3]:
        last = max(s["d"] for s in c["s"])
        sig = "；".join(f"{s['d']} {s['x']}" for s in sorted(c["s"], key=lambda s: s["d"]))
        items.append(dict(
            id=f"chain-{c['c']}-{last}", type="chain", c=c["c"], n=c["n"], m=c.get("m", ""),
            facts=[{"label": "訊號種類", "value": f"{len(c['k'])} 種"}]
            + ([{"label": "董監質押", "value": f"{c['p']}%"}] if c.get("p") else []),
            src="多份資料交叉比對", d=last, material=f"{len(c['k'])} 種訊號：{sig}",
            tpl_title=f"{c['n']}同時出現 {len(c['k'])} 種訊號",
            tpl_body=f"{c['n']}最近一年出現在 {len(c['k'])} 份資料裡：{sig}。單看一份不稀奇，疊在一起值得多看一眼。"))

    week = D.get("weekDate", today)
    for x in sorted((w for w in D.get("weekly", []) if w["dv"] >= 1_000_000), key=lambda w: -w["dv"])[:3]:
        items.append(dict(
            id=f"pledgeUp-{x['c']}-{week}", type="pledgeUp", c=x["c"], n=x["n"], m=mk(x["c"]),
            facts=[{"label": "本週新增質押", "value": zhang(x["dv"])}, {"label": "增幅", "value": f"{x['r']}%"}],
            src="集保 設質交付週統計", d=week,
            material=f"本週設質增加 {zhang(x['dv'])}，比上週增加 {x['r']}%；設質占發行股數 {x['i']}%",
            tpl_title=f"{x['n']}本週質押增加 {zhang(x['dv'])}",
            tpl_body=f"{x['n']}這週在集保的設質股數增加 {zhang(x['dv'])}，比上週多 {x['r']}%。"))

    seen = recent_ids(today)
    caps = {"insider": 4, "control": 2, "fined": 2, "disposal": 2, "chain": 3, "pledgeUp": 2}
    picked, count = [], {}
    for i in items:
        if i["id"] in seen or i["c"] not in cos:  # 已寫過的、或不是股票（例如可轉債 5 碼代號）
            continue
        if count.get(i["type"], 0) >= caps.get(i["type"], 2):
            continue
        count[i["type"]] = count.get(i["type"], 0) + 1
        picked.append(i)
    items = picked[:MAX_ITEMS]
    for r, it in enumerate(items, 1):
        it["rank"] = r
    return today, items


def main():
    D = json.load(open(os.path.join(ROOT, "data.json"), encoding="utf-8"))
    today, items = build(D)
    json.dump({"date": today, "items": items}, open(os.path.join(HERE, "draft.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    text = {"summary": "", "items": {it["id"]: {"title": "", "body": ""} for it in items}}
    json.dump(text, open(os.path.join(HERE, "draft_text.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"資料日 {today}，挑出 {len(items)} 篇。素材如下（數字只能用這裡出現的）：\n")
    for it in items:
        print(f"[{it['id']}] {NAMES[it['type']]}｜{it['n']}（{it['c']}）")
        print(f"  素材：{it['material']}")
        print("  數字卡：" + "、".join(f"{f['label']} {f['value']}" for f in it["facts"]))
        print()
    print("請填寫 pipeline/draft_text.json，然後執行 python pipeline/check_content.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
