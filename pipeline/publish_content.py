"""白話日報 第 4 步：把 content.json 推上 GitHub。

用法（在 repo 根目錄）：python pipeline/publish_content.py
"""
import json
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(*args, check=True):
    print("> git " + " ".join(args))
    r = subprocess.run(["git", *args], cwd=ROOT)
    if check and r.returncode != 0:
        print("失敗了，請看上面的訊息。")
        sys.exit(1)
    return r.returncode


def main():
    day = json.load(open(os.path.join(ROOT, "content.json"), encoding="utf-8"))["date"]
    git("add", "content.json", "history")
    git("commit", "-m", f"content {day}", check=False)  # 沒有變更時 commit 會失敗，沒關係
    git("pull", "--rebase", "-X", "theirs", "origin", "main")
    git("push", "origin", "main")
    print(f"完成：{day} 的白話日報已發布。")


if __name__ == "__main__":
    main()
