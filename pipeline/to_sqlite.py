r"""大股東在幹嘛：把每天抓下來的 CSV 匯進本機資料庫 history.db（SQLite）。

用法：
  python to_sqlite.py                 匯入 raw\ 底下所有還沒匯過的日期
  python to_sqlite.py raw\2026-10-31  只匯這一天
  python to_sqlite.py --all           全部重新匯入（不會重複，只會更新「最後抓到」）

只用 Python 內建模組。資料庫在同一層的 history.db，用 DB Browser (SQLite) 打開就能看。

資料表：
  - 每個資料集一張表，表名就是檔名，例如「22813_上市_內部人持股轉讓申報」。
    欄位 = CSV 原本的欄位，再加上：
      代號      統一後的公司代號（原本叫公司代號 / 證券代號 / 股票代號）
      首次抓到  第一次在哪天的資料裡出現（YYYY-MM-DD）
      最後抓到  最後一次在哪天的資料裡出現
    同一筆資料每天都會重複出現在 CSV 裡，這裡只存一次，用「首次抓到 / 最後抓到」記錄期間。
  - 合併查詢用的檢視表（view）：內部人申報、經營權異動、重大訊息、董監質權設定、證期局裁罰、
    違反重訊規定、每月營收，上市和上櫃合在一起，多一欄「市場」。
  - 匯入紀錄：哪天的資料匯過、各匯了幾筆。
"""
import csv
import hashlib
import io
import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / "history.db"
RAW = HERE / "raw"

CODE_COLS = ("公司代號", "證券代號", "股票代號")
# 「出表日期」是政府平台每天產生檔案的日期，同一筆資料每天都會變。
# 判斷是不是同一筆時不看它，否則每天都會多一份重複資料。
# 例外：董監質權設定的出表日期就是資料月份，要保留。
KEEP_SNAPSHOT_DATE = {"43532", "43533"}
SNAPSHOT_COL = "出表日期"

# 檢視表：名稱 → 要合併的資料集編號
VIEWS = {
    "內部人申報": ["22813", "22814"],
    "內部人持股未轉讓": ["22815", "22816"],
    "經營權異動": ["31613", "44112"],
    "重大訊息": ["18415", "18418"],
    "董監質權設定": ["43532", "43533"],
    "董監持股餘額": ["22811", "22812"],
    "證期局裁罰": ["22817", "22818"],
    "違反重訊規定": ["24280", "24281"],
    "每月營收": ["18420", "56510"],
    "營業範圍重大變更": ["36818", "44113"],
}


def q(name):
    return '"' + name.replace('"', '""') + '"'


def read_rows(path):
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json" or text.lstrip().startswith(("[", "{")):
        data = json.loads(text)
        rows = data if isinstance(data, list) else next(
            (v for v in data.values() if isinstance(v, list)), [data])
        rows = [r for r in rows if isinstance(r, dict)]
        header = list(rows[0].keys()) if rows else []
        return header, [[str(r.get(h, "") if r.get(h) is not None else "") for h in header] for r in rows]
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        return [], []
    header = [h.strip() or f"欄位{i+1}" for i, h in enumerate(rows[0])]
    # 欄位名稱重複時加編號
    seen = {}
    for i, h in enumerate(header):
        if h in seen:
            seen[h] += 1
            header[i] = f"{h}_{seen[h]}"
        else:
            seen[h] = 1
    body = []
    for r in rows[1:]:
        r = [c.strip() for c in r] + [""] * (len(header) - len(r))
        body.append(r[: len(header)])
    return header, body


def code_of(header, row, ds_id):
    for c in CODE_COLS:
        if c in header:
            return row[header.index(c)]
    if ds_id in ("43532", "43533") and "公司名稱" in header:
        m = re.match(r"\s*([0-9A-Z]{4,6})\s", row[header.index("公司名稱")])
        return m.group(1) if m else ""
    return ""


def split_pledge(header, rows):
    """董監質權設定的「公司名稱」一格塞了好幾家（「3040  遠見  99.36」一行一家），拆成一家一列。"""
    if "公司名稱" not in header:
        return header, rows
    i = header.index("公司名稱")
    out_header = header + ["質押比率"]
    out = []
    for r in rows:
        for line in r[i].splitlines():
            m = re.match(r"\s*([0-9A-Z]{4,6})\s+(.+?)\s+([0-9.]+)\s*$", line)
            if m:
                nr = list(r)
                nr[i] = f"{m.group(1)} {m.group(2)}"
                out.append(nr + [m.group(3)])
    return out_header, out


def ensure_table(con, table, header):
    cols = {r[1] for r in con.execute(f"PRAGMA table_info({q(table)})")}
    if not cols:
        defs = ", ".join(f"{q(h)} TEXT" for h in header)
        con.execute(
            f"CREATE TABLE {q(table)} (_id TEXT PRIMARY KEY, 代號 TEXT, {defs}, "
            f"首次抓到 TEXT, 最後抓到 TEXT)")
        con.execute(f"CREATE INDEX {q('ix_' + table + '_代號')} ON {q(table)}(代號)")
        return
    for h in header:  # 政府偶爾會加欄位
        if h not in cols:
            con.execute(f"ALTER TABLE {q(table)} ADD COLUMN {q(h)} TEXT")


def import_file(con, path, day):
    ds_id = path.name.split("_", 1)[0]
    table = path.stem
    header, rows = read_rows(path)
    if ds_id in ("43532", "43533"):
        header, rows = split_pledge(header, rows)
    if not header:
        return 0, 0
    ensure_table(con, table, header)
    skip = SNAPSHOT_COL if ds_id not in KEEP_SNAPSHOT_DATE else None
    key_idx = [i for i, h in enumerate(header) if h != skip]
    names = ["_id", "代號"] + header + ["首次抓到", "最後抓到"]
    sql = (f"INSERT INTO {q(table)} ({', '.join(q(n) for n in names)}) "
           f"VALUES ({', '.join('?' * len(names))}) "
           f"ON CONFLICT(_id) DO UPDATE SET "
           f"首次抓到 = MIN(首次抓到, excluded.首次抓到), "
           f"最後抓到 = MAX(最後抓到, excluded.最後抓到), "
           + ", ".join(f"{q(h)} = excluded.{q(h)}" for h in header if h == SNAPSHOT_COL))
    if not any(h == SNAPSHOT_COL for h in header):
        sql = sql.rstrip(", ")
    before = con.execute(f"SELECT COUNT(*) FROM {q(table)}").fetchone()[0]
    for r in rows:
        key = "\x1f".join(r[i] for i in key_idx)
        _id = hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
        con.execute(sql, [_id, code_of(header, r, ds_id)] + r + [day, day])
    after = con.execute(f"SELECT COUNT(*) FROM {q(table)}").fetchone()[0]
    new = after - before
    return len(rows), new


def build_views(con):
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for view, ids in VIEWS.items():
        parts = [t for i in ids for t in tables if t.startswith(i + "_")]
        con.execute(f"DROP VIEW IF EXISTS {q(view)}")
        if not parts:
            continue
        colsets = [[r[1] for r in con.execute(f"PRAGMA table_info({q(t)})") if r[1] != "_id"] for t in parts]
        common = [c for c in colsets[0] if all(c in s for s in colsets[1:])]
        selects = []
        for t in parts:
            market = t.split("_")[1] if t.count("_") >= 2 else ""
            selects.append(f"SELECT '{market}' AS 市場, {', '.join(q(c) for c in common)} FROM {q(t)}")
        con.execute(f"CREATE VIEW {q(view)} AS " + " UNION ALL ".join(selects))


def main(argv):
    redo = "--all" in argv
    args = [a for a in argv if not a.startswith("--")]
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS 匯入紀錄 (日期 TEXT, 檔案 TEXT, 筆數 INTEGER, 新增 INTEGER, "
                "PRIMARY KEY (日期, 檔案))")
    if args:
        days = [Path(a) for a in args]
    else:
        done = {r[0] for r in con.execute("SELECT DISTINCT 日期 FROM 匯入紀錄")}
        days = sorted(p for p in RAW.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name)
                      and (redo or p.name not in done)) if RAW.exists() else []
    if not days:
        print("沒有新的日期要匯入。")
    for d in days:
        day = d.name
        print(f"[{day}]")
        files = sorted(list(d.glob("*.csv")) + list(d.glob("*.json")))
        for f in files:
            if not re.match(r"\d+_", f.name):
                continue
            try:
                total, new = import_file(con, f, day)
                con.execute("INSERT INTO 匯入紀錄 VALUES (?,?,?,?) ON CONFLICT(日期, 檔案) "
                            "DO UPDATE SET 筆數 = excluded.筆數", (day, f.name, total, new))
                print(f"  {f.stem}：{total} 筆，新增 {new}")
            except Exception as e:  # noqa: BLE001
                print(f"  {f.name} 匯入失敗：{e}")
        con.commit()
    build_views(con)
    con.commit()
    if redo:
        con.execute("VACUUM")
    con.close()
    print(f"資料庫：{DB}")


if __name__ == "__main__":
    main(sys.argv[1:])
