# 大股東在幹嘛

把政府公開資料（證交所、櫃買中心、集保、金管會）整理成「我關心的公司，大股東最近有沒有動作」的儀表板。只整理公開事實，不提供買賣建議。

## 結構

| 路徑 | 用途 |
|---|---|
| `index.html` | 網站本體（單一檔案，不用建置）。打開時讀 `DATA_URL`，失敗就讀同資料夾的 `data.json` |
| `data.json` | 最新資料，由 `pipeline/run_daily.bat` 更新 |
| `history/` | 每天的資料備份，之後做「跟昨天比」 |
| `docs/SPEC.md` | 產品規格：頁面、互動、配色、文案規則 |
| `docs/DATA_SCHEMA.md` | data.json 欄位說明 |
| `pipeline/` | `fetch_datagov.py` 下載 → `build_data.py` 整理 → `run_daily.bat` 一鍵跑完並 push |

資料網址：`https://raw.githubusercontent.com/24464894/dagudong/main/data.json`

## 更新資料

在本機 clone 這個 repo，雙擊 `pipeline/run_daily.bat`。網站下次被打開就會讀到新資料，不用重新發布。

## 給 AI Studio

匯入這個 repo 後，請以 `docs/SPEC.md` 為準改寫或優化；資料一律從 `DATA_URL` 讀，不要自己編資料。
