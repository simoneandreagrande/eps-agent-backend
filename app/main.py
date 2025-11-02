from fastapi import FastAPI, Query
from pydantic import BaseModel, Field
from typing import Optional, Literal
import yfinance as yf

app = FastAPI(title="Finance EPS Service", version="1.0")

class DealStructure(BaseModel):
    type: Literal["cash", "stock", "mix"]
    exchange_ratio: Optional[float] = 0.0
    new_debt: float = 0.0
    cost_of_debt: float = 0.06
    cash_used: float = 0.0
    lost_interest: float = 0.03
    synergies_pre_tax: float = 0.0
    tax_rate: float = 0.25
    ppa_amort_post_tax: float = 0.0

class ProFormaRequest(BaseModel):
    acquirer: str = Field(..., description="Yahoo ticker, e.g., AAPL")
    target: str = Field(..., description="Yahoo ticker, e.g., ADBE")
    structure: DealStructure

class ProFormaBridge(BaseModel):
    ni_pf: Optional[float] = None
    ni_acq: Optional[float] = None
    ni_tgt: Optional[float] = None
    synergies_net: float = 0.0
    interest_new_debt_net: float = 0.0
    interest_lost_net: float = 0.0
    ppa_amort_post_tax: float = 0.0
    shares_pf: Optional[float] = None
    shares_acq: Optional[float] = None

class ProFormaResponse(BaseModel):
    eps_pf: Optional[float]
    eps_acq: Optional[float]
    accretion_pct: Optional[float]
    bridge: ProFormaBridge
    notes: str = ""

def _get_basics(ticker: str):
    notes = []
    try:
        t = yf.Ticker(ticker)
        # fast_info is more robust for basic fields
        fi = getattr(t, "fast_info", {}) or {}
        price = getattr(fi, "last_price", None) or fi.get("last_price")
        shares = fi.get("shares_outstanding")
        currency = fi.get("currency")

        # trailing EPS (may not always be present)
        info = getattr(t, "info", {}) or {}
        eps_ttm = info.get("trailingEps")

        ni_ttm = None
        if eps_ttm is not None and shares:
            ni_ttm = eps_ttm * shares
        else:
            # try to derive from financials if available
            fin = t.financials
            if fin is not None and not fin.empty and "Net Income" in fin.index:
                # take latest column
                ni_vals = fin.loc["Net Income"].dropna()
                if not ni_vals.empty:
                    ni_ttm = float(ni_vals.iloc[0])
            else:
                notes.append(f"Could not derive NI TTM for {ticker}.")

        return dict(price=price, shares=shares, eps_ttm=eps_ttm, ni_ttm=ni_ttm, currency=currency, notes="; ".join(notes))
    except Exception as e:
        return dict(price=None, shares=None, eps_ttm=None, ni_ttm=None, currency=None, notes=f"Error fetching {ticker}: {e}")

@app.get("/basics")
def basics(ticker: str = Query(..., description="Yahoo Finance ticker, e.g., AAPL")):
    return _get_basics(ticker)

@app.post("/proforma", response_model=ProFormaResponse)
def proforma(req: ProFormaRequest):
    notes = []

    A = _get_basics(req.acquirer)
    T = _get_basics(req.target)

    if A.get("ni_ttm") is None or A.get("shares") in (None, 0):
        notes.append("Missing acquirer NI or shares; EPS may be unavailable.")
    if T.get("ni_ttm") is None or T.get("shares") in (None, 0):
        notes.append("Missing target NI or shares; combination NI may be approximate.")

    tax = max(0.0, min(0.6, req.structure.tax_rate))
    if tax != req.structure.tax_rate:
        notes.append(f"Adjusted tax_rate to {tax:.2f}.")

    synergies_net = req.structure.synergies_pre_tax * (1 - tax)
    interest_new_debt_net = req.structure.new_debt * req.structure.cost_of_debt * (1 - tax)
    interest_lost_net = req.structure.cash_used * req.structure.lost_interest * (1 - tax)

    ni_acq = A.get("ni_ttm") or 0.0
    ni_tgt = T.get("ni_ttm") or 0.0

    ni_pf = (
        ni_acq
        + ni_tgt
        + synergies_net
        - interest_new_debt_net
        - interest_lost_net
        - (req.structure.ppa_amort_post_tax or 0.0)
    )

    shares_pf = A.get("shares") or 0.0
    shares_acq = A.get("shares") or 0.0

    if req.structure.type in ("stock", "mix"):
        er = req.structure.exchange_ratio or 0.0
        if er == 0.0:
            notes.append("Exchange ratio not provided or zero; no new shares assumed.")
        tgt_shares = T.get("shares") or 0.0
        shares_pf += tgt_shares * er

    eps_pf = None
    eps_acq = None
    accretion_pct = None

    if shares_pf > 0:
        eps_pf = ni_pf / shares_pf
    else:
        notes.append("Pro forma shares are zero; cannot compute EPS PF.")

    if shares_acq > 0 and ni_acq is not None:
        eps_acq = ni_acq / shares_acq
    else:
        notes.append("Acquirer shares are zero; cannot compute standalone EPS.")

    if eps_pf is not None and eps_acq not in (None, 0):
        accretion_pct = (eps_pf - eps_acq) / eps_acq

    # Append ticker-level notes
    for tag, d in (("Acquirer", A), ("Target", T)):
        if d.get("notes"):
            notes.append(f"{tag}: {d['notes']}")

    return ProFormaResponse(
        eps_pf=eps_pf,
        eps_acq=eps_acq,
        accretion_pct=accretion_pct,
        bridge=ProFormaBridge(
            ni_pf=ni_pf,
            ni_acq=ni_acq,
            ni_tgt=ni_tgt,
            synergies_net=synergies_net,
            interest_new_debt_net=interest_new_debt_net,
            interest_lost_net=interest_lost_net,
            ppa_amort_post_tax=req.structure.ppa_amort_post_tax or 0.0,
            shares_pf=shares_pf,
            shares_acq=shares_acq,
        ),
        notes="; ".join([n for n in notes if n])
    )