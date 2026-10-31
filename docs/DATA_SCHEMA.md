# data/data.json 欄位說明

日期一律是西元 `YYYY-MM-DD`。股數單位是「股」，畫面上除以 1,000 顯示成「張」。

```
{
  today:      "2026-10-30",   // 資料日
  pledgeDate: "2026-08-19",   // 董監質押資料的出表日（每月）
  weekDate:   "2026-10-22",   // 集保設質週統計的資料日
  cos:     [Company],         // 1,978 家公司
  control: [Control],         // 經營權異動 34 筆，新到舊
  weekly:  [Weekly],          // 本週設質有增減的股票（4 碼代號），依增加量大到小
  trade:   [Trade],           // 上櫃變更交易（全額交割等）
  disp:    [Disposal],        // 上櫃處置中
  fines:   [Fine],            // 罰款，新到舊
  insider: [Insider],         // 今天的內部人持股轉讓申報
  ann:     {"上市":182,"上櫃":74},          // 今天重大訊息則數
  clause:  [["20",51],["31",39],...]        // 重大訊息依「第幾款」計數；31=財報通過、12=法說會（例行）
}
```

### Company
| 欄位 | 說明 |
|---|---|
| `c` | 代號，例 `"3041"` |
| `n` | 簡稱，例 `"揚智"` |
| `m` | `"上市"` 或 `"上櫃"` |
| `i` | 產業別，例 `"半導體業"` |
| `p` | 董監持股質押比例（%），可能是 `null` |
| `k` | 這家公司有的訊號代碼陣列，例 `["control","fined","pledgeHigh"]`（代碼見 SPEC 第 5 節） |
| `s` | 訊號明細陣列：`{k: 代碼, d: 日期, x: 一句話說明}` |

### Control（經營權異動）
`c` 代號、`n` 名稱、`m` 市場、`d` 異動日、`t` 類型（公開收購／股權轉讓／私募入主／母公司易主／法人董事易主／解任董事／董事辭任／董事改選）、`x` 原文。

### Weekly（集保設質週統計）
`c`、`n`、`dv` 本週設質增減股數（正＝多押、負＝贖回）、`r` 增減比率 %、`i` 已設質佔發行股數 %。

### Trade
`c`、`n`、`k` 類型文字（全額交割、分盤交易、管理股票、停止交易）。

### Disposal（處置）
`c`、`n`、`d` 公布日、`from`/`to` 處置起訖日、`why` 原因。

### Fine（罰款）
`c`、`n`、`d` 發函日、`src`（「金管會證期局」或「證交所（重訊）」）、`why` 違規事由、`amt` 金額（萬元，可能 null）、`raw` 裁處原文。

### Insider（持股轉讓申報）
`c`、`n`、`m`、`d` 出表日、`who` 申請人身分、`name` 申請人、`how` 轉讓方式、`sell` 預定轉讓股數、`hold` 目前持股、`period` 有效期間（`起～迄`）。

### 怎麼算時間軸上的事件（給前端）
對某家公司 code：
- `insider`：`insider` 裡 c=code 的每筆，標在 `d`，並用 `period` 畫一段區間。
- `control`：`control` 裡 c=code，標在 `d`。
- `pledgeUp`：`weekly` 裡 c=code 且 `dv ≥ 1,000,000`，標在 `weekDate`。
- `disposal`：`disp` 裡 c=code，用 `from`～`to` 畫橘色橫條。
- `fined`：`fines` 裡 c=code，標在 `d`。
- `trade`：`trade` 裡 c=code，標在 `today`。
- 董監質押比例不是事件，放在列的右邊。

## content.json（白話日報）

網址：`CONTENT_URL = https://raw.githubusercontent.com/24464894/dagudong/main/content.json`；每天另存一份到 `history/content-YYYY-MM-DD.json`。

```
{
  date:        "2026-10-30",          // 對應 data.json 的 today
  generatedAt: "2026-10-30T21:05:00+08:00",
  model:       "ChatPlayground.ai",   // 顯示用，可不顯示
  summary:     "今天最值得注意的是…",   // 今日導讀，2～4 句
  items: [{
    id:    "insider-2460-2026-10-29", // 種類-代號-日期，唯一；分享連結 #daily-<id>
    rank:  1,                         // 顯示順序，1 最前面
    type:  "insider",                 // insider | control | pledgeHigh | pledgeUp | trade | disposal | fined | chain（連環訊號）
    c:     "2460", n: "建通", m: "上市",
    title: "建通大股東申報 11 月要賣 3,500 張",   // 一句話，30 字內
    body:  "白話說明，80～200 字，只講事實",
    facts: [{label:"申報賣出", value:"3,500 張"}, {label:"占持股", value:"18%"}],  // 0～4 個，數字都和 data.json 核對過
    src:   "證交所 內部人持股轉讓申報",
    d:     "2026-10-29"               // 事件日期
  }]
}
```

`items` 可能是空陣列（今天還沒產生），前端要顯示「還在整理中」。
