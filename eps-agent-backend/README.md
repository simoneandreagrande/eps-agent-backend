# Finance EPS Service (FastAPI + yfinance)

A minimal backend to compute **pro forma EPS** and **EPS accretion/dilution** for M&A scenarios using Yahoo Finance data via `yfinance`.

## Endpoints
- `GET /basics?ticker=AAPL` → price, shares, EPS TTM (if available), NI TTM (derived), currency
- `POST /proforma` → pro forma EPS, standalone EPS, accretion %, and a bridge

## Local run
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs

## Example request
```bash
curl -X POST http://127.0.0.1:8000/proforma \
  -H "Content-Type: application/json" \
  -d '{
    "acquirer": "AAPL",
    "target": "ADBE",
    "structure": {
      "type": "stock",
      "exchange_ratio": 0.20,
      "synergies_pre_tax": 1000000000,
      "tax_rate": 0.21,
      "ppa_amort_post_tax": 200000000
    }
  }'
```

## Deploy (Render.com)
1. Push this folder to a new GitHub repo.
2. On Render, create **New → Web Service**, connect the repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. After deploy, visit `/docs`. Copy the base URL.

## Coze plugin
- Edit `openapi.yaml`: replace `https://REPLACE_WITH_YOUR_BASE_URL` with your public URL.
- In Coze: **Plugins → New → Import OpenAPI**, paste the YAML, publish it.
- Add the plugin to your Agent and use the agent instructions you defined.