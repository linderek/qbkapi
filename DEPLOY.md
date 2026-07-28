# 部署指南:Vercel + Vercel Cron + Google Sheets

本專案的 `/sync-invoices` endpoint 會:驗證請求來自 Vercel Cron → 讀取 Upstash 裡的 QuickBooks
refresh token → 換發新的 access token → 撈取所有 Invoice → 整批覆蓋寫入指定的 Google Sheet →
把新的 token 存回 Upstash。

排程完全交給 Vercel Cron Jobs（`vercel.json` 裡的 `crons` 設定),不需要 GCP、不需要 gcloud
CLI、也不需要信用卡。Vercel Cron 觸發時會自動帶 `Authorization: Bearer $CRON_SECRET` header,
app 會檢查這個值是否吻合;**沒有設定 `CRON_SECRET` 的話,這支 API 會拒絕所有請求**
(fail-closed),避免部署後忘記設定就變成任何人都能觸發。

唯一還是需要 GCP 的地方,是 Google Sheets 要靠一個 GCP service account 才能寫入——但這步只需要
一個免費的 GCP 專案(不用綁信用卡/帳單帳戶),跟排程本身無關。

以下假設你已安裝 `npm i -g vercel` 並執行過 `vercel login`。

## 1. 建立 Google Sheets 用的 Service Account

到 [console.cloud.google.com/iam-admin/serviceaccounts](https://console.cloud.google.com/iam-admin/serviceaccounts)
(需要一個 GCP 專案,免費建立即可,不用開通帳單):

1. 「+ 建立服務帳戶」→ 名稱填 `qbk-sheets-writer` → 建立並繼續 → 不用給任何角色 → 完成
2. 點剛建立好的帳戶 →「金鑰」分頁 →「新增金鑰」→「建立新的金鑰」→ 選 **JSON** → 下載

打開下載的 JSON,複製 `client_email`(格式類似
`qbk-sheets-writer@YOUR_PROJECT_ID.iam.gserviceaccount.com`)。

打開目標 Google Sheet → 右上角「共用」→ 把這個 email 加為 **編輯者**。

從 Sheet 網址取得 `GOOGLE_SHEET_ID`:

```
https://docs.google.com/spreadsheets/d/<這一段就是 GOOGLE_SHEET_ID>/edit
```

把下載的 JSON 壓成單行,準備放進環境變數(假設檔名是 `sa-key.json`):

```bash
python3 -c "import json;print(json.dumps(json.load(open('sa-key.json'))))"
```

輸出的內容就是 `GOOGLE_SERVICE_ACCOUNT_JSON` 的值。填完後把本地的 `sa-key.json` 刪掉,不需要
留在硬碟上。

## 2. 產生 CRON_SECRET

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```
0FtEdv9ieaopS_3u2HkzEspFebm2gI1STKe2JggwUaQ

## 3. 本地測試

```bash
pip install -r requirements.txt
python app.py
curl -X POST http://localhost:8000/sync-invoices \
    -H "Authorization: Bearer 你剛產生的字串"
```

看到回應 `{"status": "ok", "count": N}` 且 Sheet 內容被覆蓋更新,代表串接沒問題。

## 4. 設定 Vercel 環境變數並部署

在 Vercel Dashboard(Project → Settings → Environment Variables)或用 CLI 逐一加入下列變數
(都選 Production):

- `INTUIT_CLIENT_ID`
- `INTUIT_CLIENT_SECRET`
- `INTUIT_REDIRECT_URI`
- `QUICKBOOKS_ENVIRONMENT`(sandbox 或 production)
- `QUICKBOOKS_BASE_URL`
- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`
- `GOOGLE_SHEET_ID`
- `GOOGLE_SHEET_NAME`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `CRON_SECRET`
- `FLASK_SECRET_KEY`

CLI 方式(每個變數會互動式要你貼值):

```bash
vercel link
for name in INTUIT_CLIENT_ID INTUIT_CLIENT_SECRET INTUIT_REDIRECT_URI \
    QUICKBOOKS_ENVIRONMENT QUICKBOOKS_BASE_URL UPSTASH_REDIS_REST_URL \
    UPSTASH_REDIS_REST_TOKEN GOOGLE_SHEET_ID GOOGLE_SHEET_NAME \
    GOOGLE_SERVICE_ACCOUNT_JSON CRON_SECRET FLASK_SECRET_KEY; do
    vercel env add "$name" production
done

vercel deploy --prod
```

部署完成後,`vercel.json` 裡的 `crons` 設定會自動生效——不需要另外建立任何排程資源。目前設定是:

```json
"crons": [
  { "path": "/sync-invoices", "schedule": "0 0 1 * *" }
]
```

`schedule` 是 **UTC 時間**的 cron 表達式,`0 0 1 * *` = 每月 1 號 UTC 00:00 = 台北時間每月 1 號
早上 8 點。要改時間就直接改這個 cron 表達式並重新部署。

> **方案限制**:Vercel Hobby 方案的 Cron Jobs 每個 job 最快只能設定為「每天一次」,同帳號的 cron
> 數量也有上限;Pro 方案才能設定更高頻率。目前「每月一次」的需求在 Hobby 方案下沒問題。
>
> **執行時間限制**:`vercel.json` 把 `maxDuration` 設為 60 秒,若 invoice 數量多導致撈取 + 寫入
> Sheet 超時,需要確認你的 Vercel 方案可用的最大值並調整這個數字。
>
> **QuickBooks 正式環境**:切換時記得同時更新 `QUICKBOOKS_ENVIRONMENT=production`、
> `QUICKBOOKS_BASE_URL=https://quickbooks.api.intuit.com/v3`,並改用 Production 的
> `INTUIT_CLIENT_ID` / `INTUIT_CLIENT_SECRET`。

## 5. 驗證

到 Vercel Dashboard →專案 → **Cron Jobs** 分頁,可以看到已註冊的排程與每次執行結果;也可以手動
點 "Run" 立即觸發一次測試,或直接看 **Logs** 分頁確認 `Synced N invoices to sheet` 有印出來,並
檢查 Sheet 內容是否被覆蓋更新。
