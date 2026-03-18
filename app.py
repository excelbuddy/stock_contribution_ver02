"""
VNIndex Contribution Dashboard
Streamlit app - 3 tabs:
  Tab 1: Bảng thống kê Contribution theo đợt (như ảnh mẫu)
  Tab 2: Chart lịch sử VNIndex với đỉnh/đáy và mũi tên
  Tab 3: Phân tích cổ phiếu đóng góp chính (Trading Insights)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import requests

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="VNIndex Contribution Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

SHEET_ID = "1vxAlLu79JEKN-q6R2-6zxFKC2BrsfrUJjOzbstpA2kc"

# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
  .stTabs [data-baseweb="tab-list"] { gap: 8px; }
  .stTabs [data-baseweb="tab"] {
    font-weight: 600; font-size: 14px;
    padding: 8px 20px; border-radius: 6px 6px 0 0;
  }
  .metric-box {
    background: #1e2130; border-radius: 8px;
    padding: 12px 16px; margin: 4px;
  }
  .up-color   { color: #00c853; }
  .down-color { color: #ff1744; }
  .neutral    { color: #90caf9; }
  div[data-testid="stMetricValue"] { font-size: 1.4rem !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_sheet(sheet_name: str) -> pd.DataFrame:
    url = (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
        f"/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    )
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text))


@st.cache_data(ttl=3600, show_spinner=False)
def load_all():
    with st.spinner("Đang tải dữ liệu từ Google Sheets…"):
        hist  = load_sheet("hose-history")
        pc    = load_sheet("hose-history-PC")
        c_old = load_sheet("Contribution_old")
        c_new = load_sheet("Contribution")
    return hist, pc, c_old, c_new


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def parse_influence(val):
    """Convert '(4.6)' or '4.6' → float"""
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


def prep_history(hist: pd.DataFrame) -> pd.DataFrame:
    df = hist.copy()
    # Use col 0 (Correct Date) if parseable, else col 1
    df["Date"] = pd.to_datetime(df.iloc[:, 0], errors="coerce")
    mask = df["Date"].isna()
    df.loc[mask, "Date"] = pd.to_datetime(df.loc[mask, "Ngay"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    df["Close"] = pd.to_numeric(df["GiaDieuChinh"], errors="coerce")
    return df[["Date", "Close"]].dropna()


def prep_pc(pc: pd.DataFrame) -> pd.DataFrame:
    df = pc.copy()
    df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
    df["End Date"]   = pd.to_datetime(df["End Date"],   errors="coerce")
    df["Change_pct"] = (
        df["Change %"]
        .astype(str)
        .str.replace("%", "", regex=False)
        .str.replace("+", "", regex=False)
        .str.strip()
    )
    df["Change_pct"] = pd.to_numeric(df["Change_pct"], errors="coerce")
    df["Days"]       = pd.to_numeric(df["Days"], errors="coerce")
    df["has_data"]   = ~df["Contribution Data"].str.contains("Not available", na=True)
    return df


def prep_contribution_old(c_old: pd.DataFrame) -> pd.DataFrame:
    df = c_old.copy()
    df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
    df["End Date"]   = pd.to_datetime(df["End Date"],   errors="coerce")
    df["InfluenceIndex"] = pd.to_numeric(df["InfluenceIndex"], errors="coerce")
    return df


def prep_contribution_new(c_new: pd.DataFrame, pc: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily contribution into per-period contribution matching hose-history-PC rows 97-100"""
    df = c_new.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["InfluenceIndex"] = df["InfluenceIndex"].apply(parse_influence)

    # Assign each date to a period from hose-history-PC
    pc_calc = pc[pc["Contribution Data"].str.contains("Need to calculate", na=False)].copy()

    rows = []
    for _, period in pc_calc.iterrows():
        mask = (df["Date"] > period["Start Date"]) & (df["Date"] <= period["End Date"])
        sub = df[mask].copy()
        if sub.empty:
            continue
        agg = (
            sub.groupby(["StockCode", "Type"])["InfluenceIndex"]
            .sum()
            .reset_index()
        )
        agg["Start Date"] = period["Start Date"]
        agg["End Date"]   = period["End Date"]
        agg["ClosePrice"] = (
            sub.sort_values("Date")
            .drop_duplicates("StockCode", keep="last")
            .set_index("StockCode")["ClosePrice"]
        )
        agg["ClosePrice"] = agg["StockCode"].map(
            sub.sort_values("Date").drop_duplicates("StockCode", keep="last").set_index("StockCode")["ClosePrice"]
        )
        rows.append(agg)

    if rows:
        return pd.concat(rows, ignore_index=True)
    return pd.DataFrame(columns=["Start Date","End Date","StockCode","ClosePrice","InfluenceIndex","Type"])


def combine_contributions(c_old_prep, c_new_agg):
    combined = pd.concat([c_old_prep, c_new_agg], ignore_index=True)
    combined["InfluenceIndex"] = pd.to_numeric(combined["InfluenceIndex"], errors="coerce").fillna(0)
    return combined


# ─────────────────────────────────────────────
# TAB 1 — BẢNG THỐNG KÊ (như ảnh mẫu)
# ─────────────────────────────────────────────
def render_tab1(pc: pd.DataFrame, combined: pd.DataFrame):
    st.subheader("📊 Thống kê Contribution theo đợt tăng/giảm")

    pc_with_data = pc[pc["has_data"]].reset_index(drop=True)

    if pc_with_data.empty:
        st.info("Chưa có dữ liệu contribution.")
        return

    # Sidebar filters
    col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
    with col_f1:
        type_filter = st.selectbox("Loại đợt", ["Tất cả", "UP", "DOWN"])
    with col_f2:
        top_n = st.slider("Top N cổ phiếu mỗi đợt", 5, 30, 15)
    with col_f3:
        selected_periods = st.multiselect(
            "Chọn đợt (để trống = tất cả)",
            options=[
                f"{r['Type']} {r['Start Date'].strftime('%Y-%m-%d')} → {r['End Date'].strftime('%Y-%m-%d')} ({r['Change_pct']:+.1f}%)"
                for _, r in pc_with_data.iterrows()
            ],
        )

    if type_filter != "Tất cả":
        pc_with_data = pc_with_data[pc_with_data["Type"] == type_filter]

    # Build period list
    periods = []
    for _, row in pc_with_data.iterrows():
        label = f"{row['Type']} {row['Start Date'].strftime('%Y-%m-%d')} → {row['End Date'].strftime('%Y-%m-%d')} ({row['Change_pct']:+.1f}%)"
        if selected_periods and label not in selected_periods:
            continue
        periods.append(row)

    if not periods:
        st.warning("Không có đợt nào phù hợp.")
        return

    # ── Render bảng dạng grid như ảnh mẫu ──
    # Always create 4 columns per row so last card stays same width
    cols_per_row = 4
    for row_start in range(0, len(periods), cols_per_row):
        row_periods = periods[row_start: row_start + cols_per_row]
        cols = st.columns(cols_per_row)  # always 4 cols, extras stay empty

        for col_idx, (col, period) in enumerate(zip(cols, row_periods)):
            period_number = row_start + col_idx + 1
            sd = period["Start Date"]
            ed = period["End Date"]
            ptype = period["Type"]
            chg   = period["Change_pct"]
            days  = int(period["Days"])
            vi_s  = period["VNIndex-Start"]
            vi_e  = period["VNIndex-End"]

            # Get contribution data for this period
            mask = (
                (combined["Start Date"] == sd) &
                (combined["End Date"]   == ed)
            )
            df_p = combined[mask].copy()

            gainers = df_p[df_p["Type"] == "Gainers"].nlargest(top_n, "InfluenceIndex")
            losers  = df_p[df_p["Type"] == "Losers"].nsmallest(top_n, "InfluenceIndex")

            color_header = "#1b5e20" if ptype == "UP" else "#b71c1c"
            badge_color  = "#00c853" if ptype == "UP" else "#ff1744"

            with col:
                # Pre-compute % contribution correctly:
                # % = InfluenceIndex / sum of ALL |InfluenceIndex| in this period * 100
                total_abs = df_p["InfluenceIndex"].abs().sum() if not df_p.empty else 0

                gap_pts = vi_e - vi_s  # GAP in points

                # Header card — 2 rows of metrics: row1: Số ngày GD / VNI Start / VNI End
                #                                   row2: GAP (điểm) / GAP (%) badge
                st.markdown(f"""
                <div style="background:{color_header}; border-radius:8px 8px 0 0;
                            padding:10px 12px; margin-bottom:0;">
                  <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:11px; color:#ccc;">Đỉnh/Đáy {period_number}</span>
                    <span style="background:{badge_color}; color:white; font-weight:700;
                                 padding:2px 10px; border-radius:4px; font-size:12px;">
                      {ptype}
                    </span>
                  </div>
                  <div style="font-size:11px; color:#eee; margin-top:4px;">
                    {sd.strftime('%Y-%m-%d')} → {ed.strftime('%Y-%m-%d')}
                  </div>
                  <div style="display:flex; gap:6px; margin-top:6px;">
                    <div style="flex:1; background:rgba(0,0,0,0.3); border-radius:4px; padding:4px 6px; text-align:center;">
                      <div style="font-size:9px; color:#aaa;">Số ngày GD</div>
                      <div style="font-weight:700; color:white; font-size:13px;">{days}</div>
                    </div>
                    <div style="flex:1; background:rgba(0,0,0,0.3); border-radius:4px; padding:4px 6px; text-align:center;">
                      <div style="font-size:9px; color:#aaa;">VNI Start</div>
                      <div style="font-weight:700; color:white; font-size:13px;">{vi_s:,.0f}</div>
                    </div>
                    <div style="flex:1; background:rgba(0,0,0,0.3); border-radius:4px; padding:4px 6px; text-align:center;">
                      <div style="font-size:9px; color:#aaa;">VNI End</div>
                      <div style="font-weight:700; color:white; font-size:13px;">{vi_e:,.0f}</div>
                    </div>
                    <div style="flex:1; background:rgba(0,0,0,0.3); border-radius:4px; padding:4px 6px; text-align:center;">
                      <div style="font-size:9px; color:#aaa;">GAP (điểm)</div>
                      <div style="font-weight:700; color:{badge_color}; font-size:13px;">{gap_pts:+.1f}</div>
                    </div>
                    <div style="flex:1; background:rgba(0,0,0,0.3); border-radius:4px; padding:4px 6px; text-align:center;">
                      <div style="font-size:9px; color:#aaa;">GAP (%)</div>
                      <div style="font-weight:700; color:{badge_color}; font-size:13px;">{chg:+.1f}%</div>
                    </div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

                # Sub-table: TOP TĂNG + TOP GIẢM
                if df_p.empty:
                    st.markdown(
                        '<div style="background:#1e2130;padding:8px;border-radius:0 0 8px 8px;">'
                        '<i style="color:#888;">Chưa có dữ liệu</i></div>',
                        unsafe_allow_html=True
                    )
                    continue

                # Build HTML table rows
                # % = InfluenceIndex / total_abs_all * 100  (correct logic per user)
                rows_html = ""
                max_rows = max(len(gainers), len(losers))
                for i in range(max_rows):
                    g_cp = g_inf = g_pct = g_code = ""
                    l_cp = l_inf = l_pct = l_code = ""
                    if i < len(gainers):
                        g = gainers.iloc[i]
                        g_code = g["StockCode"]
                        g_inf  = f"{g['InfluenceIndex']:+.1f}"
                        g_pct  = f"{g['InfluenceIndex'] / gap_pts * 100:.1f}%" if gap_pts else ""
                    if i < len(losers):
                        l = losers.iloc[i]
                        l_code = l["StockCode"]
                        l_inf  = f"{l['InfluenceIndex']:+.1f}"
                        l_pct  = f"{l['InfluenceIndex'] / gap_pts * 100:.1f}%" if gap_pts else ""

                    row_bg = "#1e2130" if i % 2 == 0 else "#16192b"
                    rows_html += f"""
                    <tr style="background:{row_bg};">
                      <td style="color:#00e676; font-weight:600; padding:2px 6px;">{g_code}</td>
                      <td style="color:#00e676; text-align:right; padding:2px 6px;">{g_inf}</td>
                      <td style="color:#00e676; text-align:right; padding:2px 6px; font-size:11px;">{g_pct}</td>
                      <td style="color:#ff5252; font-weight:600; padding:2px 6px;">{l_code}</td>
                      <td style="color:#ff5252; text-align:right; padding:2px 6px;">{l_inf}</td>
                      <td style="color:#ff5252; text-align:right; padding:2px 6px; font-size:11px;">{l_pct}</td>
                    </tr>"""

                table_html = f"""
                <div style="background:#12151f; border-radius:0 0 8px 8px;
                            overflow:hidden; margin-bottom:16px;">
                  <table style="width:100%; border-collapse:collapse; font-size:12px;">
                    <thead>
                      <tr>
                        <th colspan="3" style="background:#1b3a1b; color:#00e676;
                                               text-align:center; padding:4px; font-size:11px;">
                          TOP TĂNG
                        </th>
                        <th colspan="3" style="background:#3a1b1b; color:#ff5252;
                                               text-align:center; padding:4px; font-size:11px;">
                          TOP GIẢM
                        </th>
                      </tr>
                      <tr style="background:#1a1d2e;">
                        <th style="color:#ccc;padding:2px 6px;font-size:10px;font-weight:500;">CP</th>
                        <th style="color:#ccc;padding:2px 6px;font-size:10px;font-weight:500;text-align:right;">Đóng góp</th>
                        <th style="color:#ccc;padding:2px 6px;font-size:10px;font-weight:500;text-align:right;">%</th>
                        <th style="color:#ccc;padding:2px 6px;font-size:10px;font-weight:500;">CP</th>
                        <th style="color:#ccc;padding:2px 6px;font-size:10px;font-weight:500;text-align:right;">Đóng góp</th>
                        <th style="color:#ccc;padding:2px 6px;font-size:10px;font-weight:500;text-align:right;">%</th>
                      </tr>
                    </thead>
                    <tbody>{rows_html}</tbody>
                  </table>
                </div>
