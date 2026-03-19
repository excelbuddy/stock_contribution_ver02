import io
import pandas as pd
import requests
import streamlit as st

SHEET_ID = "1vxAlLu79JEKN-q6R2-6zxFKC2BrsfrUJjOzbstpA2kc"

# ── FETCH ─────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def load_sheet(name):
    url = ("https://docs.google.com/spreadsheets/d/"
           + SHEET_ID + "/gviz/tq?tqx=out:csv&sheet=" + name)
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text))

@st.cache_data(ttl=3600, show_spinner=False)
def load_all():
    with st.spinner("Dang tai du lieu tu Google Sheets..."):
        hist  = load_sheet("hose-history")
        pc    = load_sheet("hose-history-PC")
        c_old = load_sheet("Contribution_old")
        c_new = load_sheet("Contribution")
    return hist, pc, c_old, c_new

# ── PARSE HELPERS ─────────────────────────────────────────────────────────────

def parse_influence(val):
    if pd.isna(val):
        return 0.0
    s = str(val).strip()
    if s.startswith("(") and s.endswith(")"):
        try:
            return -float(s[1:-1])
        except:
            return 0.0
    try:
        return float(s)
    except:
        return 0.0

def _to_float(series):
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce")

# ── PREP FUNCTIONS ────────────────────────────────────────────────────────────

def prep_history(hist):
    df = hist.copy()
    df["Date"] = pd.to_datetime(df.iloc[:, 0], errors="coerce")
    mask = df["Date"].isna()
    df.loc[mask, "Date"] = pd.to_datetime(
        df.loc[mask, "Ngay"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    df["Close"] = pd.to_numeric(df["GiaDieuChinh"], errors="coerce")
    return df[["Date", "Close"]].dropna()

def prep_pc(pc):
    df = pc.copy()
    df["Start Date"]    = pd.to_datetime(df["Start Date"], errors="coerce")
    df["End Date"]      = pd.to_datetime(df["End Date"],   errors="coerce")
    df["VNIndex-Start"] = _to_float(df["VNIndex-Start"])
    df["VNIndex-End"]   = _to_float(df["VNIndex-End"])
    df["Change_pct"] = pd.to_numeric(
        df["Change %"].astype(str)
        .str.replace("%", "", regex=False)
        .str.replace("+", "", regex=False)
        .str.strip(),
        errors="coerce")
    df["Days"]     = pd.to_numeric(df["Days"], errors="coerce")
    df["has_data"] = ~df["Contribution Data"].str.contains("Not available", na=True)
    return df

def prep_c_old(c_old):
    df = c_old.copy()
    df["Start Date"]     = pd.to_datetime(df["Start Date"], errors="coerce")
    df["End Date"]       = pd.to_datetime(df["End Date"],   errors="coerce")
    df["InfluenceIndex"] = pd.to_numeric(df["InfluenceIndex"], errors="coerce")
    df["Type"] = df["InfluenceIndex"].apply(
        lambda x: "Gainers" if x > 0 else "Losers")
    return df

def prep_c_new(c_new, pc):
    df = c_new.copy()
    df["Date"]           = pd.to_datetime(df["Date"], errors="coerce")
    df["InfluenceIndex"] = df["InfluenceIndex"].apply(parse_influence)

    pc_calc = pc[pc["Contribution Data"].str.contains(
        "Need to calculate", na=False)].copy()

    rows = []
    for _, period in pc_calc.iterrows():
        sd   = period["Start Date"]
        ed   = period["End Date"]
        mask = (df["Date"] >= sd) & (df["Date"] <= ed)
        sub  = df[mask].copy()
        if sub.empty:
            continue
        agg = sub.groupby("StockCode")["InfluenceIndex"].sum().reset_index()
        agg["Type"]       = agg["InfluenceIndex"].apply(
            lambda x: "Gainers" if x > 0 else "Losers")
        agg["Start Date"] = sd
        agg["End Date"]   = ed
        last_price = (sub.sort_values("Date")
                         .drop_duplicates("StockCode", keep="last")
                         .set_index("StockCode")["ClosePrice"])
        agg["ClosePrice"] = agg["StockCode"].map(last_price)
        rows.append(agg)

    if rows:
        return pd.concat(rows, ignore_index=True)
    return pd.DataFrame(columns=[
        "Start Date", "End Date", "StockCode",
        "ClosePrice", "InfluenceIndex", "Type"])

def combine(c_old, c_new_agg):
    combined = pd.concat([c_old, c_new_agg], ignore_index=True)
    combined["InfluenceIndex"] = pd.to_numeric(
        combined["InfluenceIndex"], errors="coerce").fillna(0)
    combined["Type"] = combined["InfluenceIndex"].apply(
        lambda x: "Gainers" if x > 0 else "Losers")
    return combined

def load_and_prep():
    hist_raw, pc_raw, c_old_raw, c_new_raw = load_all()
    hist_df  = prep_history(hist_raw)
    pc_df    = prep_pc(pc_raw)
    c_old_df = prep_c_old(c_old_raw)
    c_new_ag = prep_c_new(c_new_raw, pc_df)
    combined = combine(c_old_df, c_new_ag)
    return hist_df, pc_df, combined
