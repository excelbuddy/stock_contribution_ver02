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
    # Group periods into rows of 4 columns
    cols_per_row = 4
    for row_start in range(0, len(periods), cols_per_row):
        row_periods = periods[row_start: row_start + cols_per_row]
        cols = st.columns(len(row_periods))

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
                # Header card
                st.markdown(f"""
                <div style="background:{color_header}; border-radius:8px 8px 0 0;
                            padding:10px 12px; margin-bottom:0;">
                  <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:11px; color:#ccc;">
                      Đỉnh/Đáy {period_number}
                    </span>
                    <span style="background:{badge_color}; color:white; font-weight:700;
                                 padding:2px 10px; border-radius:4px; font-size:12px;">
                      {ptype}
                    </span>
                  </div>
                  <div style="font-size:11px; color:#eee; margin-top:4px;">
                    {sd.strftime('%Y-%m-%d')} → {ed.strftime('%Y-%m-%d')}
                  </div>
                  <div style="display:flex; gap:8px; margin-top:6px;">
                    <div style="flex:1; background:rgba(0,0,0,0.3); border-radius:4px; padding:4px 8px; text-align:center;">
                      <div style="font-size:10px; color:#aaa;">Số ngày GD</div>
                      <div style="font-weight:700; color:white;">{days}</div>
                    </div>
                    <div style="flex:1; background:rgba(0,0,0,0.3); border-radius:4px; padding:4px 8px; text-align:center;">
                      <div style="font-size:10px; color:#aaa;">VNI Start</div>
                      <div style="font-weight:700; color:white;">{vi_s:,.0f}</div>
                    </div>
                    <div style="flex:1; background:rgba(0,0,0,0.3); border-radius:4px; padding:4px 8px; text-align:center;">
                      <div style="font-size:10px; color:#aaa;">+/- (%)</div>
                      <div style="font-weight:700; color:{badge_color};">{chg:+.1f}%</div>
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

                # Build HTML table
                rows_html = ""
                max_rows = max(len(gainers), len(losers))
                for i in range(max_rows):
                    g_cp = g_inf = g_code = ""
                    l_cp = l_inf = l_code = ""
                    if i < len(gainers):
                        g = gainers.iloc[i]
                        g_code = g["StockCode"]
                        g_cp   = str(g["ClosePrice"]) if pd.notna(g["ClosePrice"]) else ""
                        g_inf  = f"{g['InfluenceIndex']:+.1f}"
                    if i < len(losers):
                        l = losers.iloc[i]
                        l_code = l["StockCode"]
                        l_cp   = str(l["ClosePrice"]) if pd.notna(l["ClosePrice"]) else ""
                        l_inf  = f"{l['InfluenceIndex']:+.1f}"

                    row_bg = "#1e2130" if i % 2 == 0 else "#16192b"
                    rows_html += f"""
                    <tr style="background:{row_bg};">
                      <td style="color:#00e676; font-weight:600; padding:2px 5px;">{g_code}</td>
                      <td style="color:#aaa; font-size:11px; padding:2px 4px;">{g_cp}</td>
                      <td style="color:#00e676; text-align:right; padding:2px 5px;">{g_inf}</td>
                      <td style="color:#ff5252; font-weight:600; padding:2px 5px;">{l_code}</td>
                      <td style="color:#aaa; font-size:11px; padding:2px 4px;">{l_cp}</td>
                      <td style="color:#ff5252; text-align:right; padding:2px 5px;">{l_inf}</td>
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
                        <th style="color:#ccc;padding:2px 5px;font-size:10px;font-weight:500;">CP</th>
                        <th style="color:#ccc;padding:2px 4px;font-size:10px;font-weight:500;">Đóng góp</th>
                        <th style="color:#ccc;padding:2px 5px;font-size:10px;font-weight:500;">%</th>
                        <th style="color:#ccc;padding:2px 5px;font-size:10px;font-weight:500;">CP</th>
                        <th style="color:#ccc;padding:2px 4px;font-size:10px;font-weight:500;">Đóng góp</th>
                        <th style="color:#ccc;padding:2px 5px;font-size:10px;font-weight:500;">%</th>
                      </tr>
                    </thead>
                    <tbody>{rows_html}</tbody>
                  </table>
                </div>
                """
                st.markdown(table_html, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# TAB 2 — CHART LỊCH SỬ VNINDEX
# ─────────────────────────────────────────────
def render_tab2(hist_df: pd.DataFrame, pc: pd.DataFrame):
    st.subheader("📈 Lịch sử VNIndex với đỉnh/đáy")

    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        year_from = st.number_input("Từ năm", min_value=2000, max_value=2026, value=2015, step=1)
    with c2:
        year_to = st.number_input("Đến năm", min_value=2000, max_value=2026, value=2026, step=1)
    with c3:
        show_annotations = st.checkbox("Hiện mũi tên & chú thích", value=True)

    df = hist_df[(hist_df["Date"].dt.year >= year_from) & (hist_df["Date"].dt.year <= year_to)]
    pc_f = pc[(pc["Start Date"].dt.year >= year_from) | (pc["End Date"].dt.year <= year_to + 1)]

    fig = go.Figure()

    # Main line chart
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["Close"],
        mode="lines",
        line=dict(color="#4fc3f7", width=1.5),
        name="VNIndex",
        hovertemplate="<b>%{x|%d/%m/%Y}</b><br>VNIndex: %{y:,.2f}<extra></extra>",
    ))

    # Peaks (UP end = local top) and Troughs (DOWN end = local bottom)
    peak_dates, peak_vals, trough_dates, trough_vals = [], [], [], []
    for _, row in pc_f.iterrows():
        if row["Type"] == "UP":
            peak_dates.append(row["End Date"])
            peak_vals.append(row["VNIndex-End"])
        else:
            trough_dates.append(row["End Date"])
            trough_vals.append(row["VNIndex-End"])

    fig.add_trace(go.Scatter(
        x=peak_dates, y=peak_vals,
        mode="markers",
        marker=dict(color="#ff1744", size=10, symbol="triangle-up",
                    line=dict(color="white", width=1)),
        name="Đỉnh",
        hovertemplate="<b>Đỉnh %{x|%d/%m/%Y}</b><br>%{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=trough_dates, y=trough_vals,
        mode="markers",
        marker=dict(color="#00e676", size=10, symbol="triangle-down",
                    line=dict(color="white", width=1)),
        name="Đáy",
        hovertemplate="<b>Đáy %{x|%d/%m/%Y}</b><br>%{y:,.2f}<extra></extra>",
    ))

    # Arrows between consecutive peak/trough points
    if show_annotations:
        all_pts = []
        for _, row in pc_f.iterrows():
            all_pts.append({
                "date": row["End Date"],
                "val": row["VNIndex-End"],
                "type": row["Type"],
                "chg": row["Change_pct"],
                "days": row["Days"],
            })
        all_pts.sort(key=lambda x: x["date"])

        for i in range(len(all_pts) - 1):
            p0, p1 = all_pts[i], all_pts[i + 1]
            if p0["date"].year < year_from or p1["date"].year > year_to + 1:
                continue
            is_up = p1["val"] > p0["val"]
            arr_color = "#00e676" if is_up else "#ff5252"
            label = f"{p1['chg']:+.1f}%\n{int(p1['days'])}ngày"
            fig.add_annotation(
                x=p1["date"], y=p1["val"],
                ax=p0["date"], ay=p0["val"],
                xref="x", yref="y", axref="x", ayref="y",
                showarrow=True,
                arrowhead=2, arrowsize=1.2, arrowwidth=1.5,
                arrowcolor=arr_color,
                text=label,
                font=dict(size=9, color=arr_color),
                bgcolor="rgba(0,0,0,0.6)",
                borderpad=2,
            )

    fig.update_layout(
        template="plotly_dark",
        height=650,
        margin=dict(l=60, r=40, t=40, b=40),
        xaxis=dict(
            title="Ngày",
            rangeslider=dict(visible=True, thickness=0.04),
            type="date",
        ),
        yaxis=dict(title="VNIndex", tickformat=",.0f"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Summary table below chart
    st.markdown("#### Bảng các đợt tăng/giảm")
    display_pc = pc_f[["Start Date","End Date","Type","VNIndex-Start","VNIndex-End","Change %","Days","Contribution Data"]].copy()
    display_pc["Start Date"] = display_pc["Start Date"].dt.strftime("%Y-%m-%d")
    display_pc["End Date"]   = display_pc["End Date"].dt.strftime("%Y-%m-%d")

    def color_type(val):
        if val == "UP":
            return "background-color: #1b3a1b; color: #00e676; font-weight:bold"
        else:
            return "background-color: #3a1b1b; color: #ff5252; font-weight:bold"

    def color_chg(val):
        try:
            v = float(str(val).replace("%","").replace("+","").strip())
            return f"color: {'#00e676' if v > 0 else '#ff5252'}; font-weight:bold"
        except:
            return ""

    styled = (
        display_pc.style
        .applymap(color_type, subset=["Type"])
        .applymap(color_chg, subset=["Change %"])
        .set_properties(**{"font-size": "12px"})
    )
    st.dataframe(styled, use_container_width=True, height=300)


# ─────────────────────────────────────────────
# TAB 3 — INSIGHTS
# ─────────────────────────────────────────────
def render_tab3(pc: pd.DataFrame, combined: pd.DataFrame):
    st.subheader("🔍 Phân tích cổ phiếu đóng góp chính theo xu hướng")

    pc_with_data = pc[pc["has_data"]].reset_index(drop=True)
    if pc_with_data.empty or combined.empty:
        st.info("Chưa đủ dữ liệu để phân tích.")
        return

    # ── Filter ──
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        trend_filter = st.selectbox("Xu hướng phân tích", ["Tất cả", "UP", "DOWN"])
    with c2:
        top_stocks = st.slider("Số cổ phiếu hiển thị", 10, 50, 20)
    with c3:
        min_periods = st.slider("Xuất hiện tối thiểu (đợt)", 1, 10, 2)

    # Join PC periods with contribution
    merged_rows = []
    for _, p in pc_with_data.iterrows():
        mask = (combined["Start Date"] == p["Start Date"]) & (combined["End Date"] == p["End Date"])
        sub = combined[mask].copy()
        sub["period_type"] = p["Type"]
        sub["period_chg"]  = p["Change_pct"]
        merged_rows.append(sub)

    if not merged_rows:
        st.warning("Không khớp dữ liệu.")
        return

    all_data = pd.concat(merged_rows, ignore_index=True)

    if trend_filter != "Tất cả":
        all_data = all_data[all_data["period_type"] == trend_filter]

    # ── Aggregate: per stock across periods ──
    gainers_data = all_data[all_data["Type"] == "Gainers"]
    losers_data  = all_data[all_data["Type"] == "Losers"]

    def aggregate_stock(df, top_n, min_p):
        agg = df.groupby("StockCode").agg(
            total_influence=("InfluenceIndex", "sum"),
            appearances=("InfluenceIndex", "count"),
            avg_influence=("InfluenceIndex", "mean"),
        ).reset_index()
        agg = agg[agg["appearances"] >= min_p]
        agg = agg.nlargest(top_n, "total_influence") if df["InfluenceIndex"].iloc[0] > 0 else agg.nsmallest(top_n, "total_influence")
        return agg

    # Safe aggregation
    if not gainers_data.empty and gainers_data["InfluenceIndex"].notna().any():
        g_agg = gainers_data.groupby("StockCode").agg(
            total_influence=("InfluenceIndex","sum"),
            appearances=("InfluenceIndex","count"),
            avg_influence=("InfluenceIndex","mean"),
        ).reset_index()
        g_agg = g_agg[g_agg["appearances"] >= min_periods]
        g_agg = g_agg.nlargest(top_stocks, "total_influence")
    else:
        g_agg = pd.DataFrame()

    if not losers_data.empty and losers_data["InfluenceIndex"].notna().any():
        l_agg = losers_data.groupby("StockCode").agg(
            total_influence=("InfluenceIndex","sum"),
            appearances=("InfluenceIndex","count"),
            avg_influence=("InfluenceIndex","mean"),
        ).reset_index()
        l_agg = l_agg[l_agg["appearances"] >= min_periods]
        l_agg = l_agg.nsmallest(top_stocks, "total_influence")
    else:
        l_agg = pd.DataFrame()

    # ── Charts ──
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### 🟢 Cổ phiếu đóng góp tăng nhiều nhất")
        if not g_agg.empty:
            fig_g = go.Figure(go.Bar(
                x=g_agg["total_influence"],
                y=g_agg["StockCode"],
                orientation="h",
                marker_color="#00c853",
                customdata=np.stack([g_agg["appearances"], g_agg["avg_influence"]], axis=-1),
                hovertemplate="<b>%{y}</b><br>Tổng: %{x:.1f}<br>Số đợt: %{customdata[0]}<br>TB/đợt: %{customdata[1]:.2f}<extra></extra>",
            ))
            fig_g.update_layout(
                template="plotly_dark", height=550,
                margin=dict(l=20,r=20,t=20,b=20),
                xaxis_title="Tổng điểm đóng góp",
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig_g, use_container_width=True)
        else:
            st.info("Không có dữ liệu.")

    with col_b:
        st.markdown("#### 🔴 Cổ phiếu kéo giảm nhiều nhất")
        if not l_agg.empty:
            fig_l = go.Figure(go.Bar(
                x=l_agg["total_influence"].abs(),
                y=l_agg["StockCode"],
                orientation="h",
                marker_color="#ff1744",
                customdata=np.stack([l_agg["appearances"], l_agg["avg_influence"].abs()], axis=-1),
                hovertemplate="<b>%{y}</b><br>Tổng: -%{x:.1f}<br>Số đợt: %{customdata[0]}<br>TB/đợt: %{customdata[1]:.2f}<extra></extra>",
            ))
            fig_l.update_layout(
                template="plotly_dark", height=550,
                margin=dict(l=20,r=20,t=20,b=20),
                xaxis_title="Tổng điểm kéo giảm",
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig_l, use_container_width=True)
        else:
            st.info("Không có dữ liệu.")

    # ── Heatmap: Stock x Period ──
    st.markdown("---")
    st.markdown("#### 🗺️ Heatmap: Đóng góp của từng cổ phiếu qua các đợt")

    # Build pivot: stock vs period label
    all_data["period_label"] = (
        all_data["period_type"] + " " +
        all_data["Start Date"].dt.strftime("%y/%m") + "→" +
        all_data["End Date"].dt.strftime("%y/%m")
    )

    # Top stocks by absolute total influence
    top_s = (
        all_data.groupby("StockCode")["InfluenceIndex"].apply(lambda x: x.abs().sum())
        .nlargest(top_stocks).index.tolist()
    )
    heat_data = all_data[all_data["StockCode"].isin(top_s)]
    pivot = heat_data.pivot_table(
        index="StockCode", columns="period_label",
        values="InfluenceIndex", aggfunc="sum", fill_value=0
    )

    if not pivot.empty:
        fig_h = go.Figure(go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale=[
                [0.0, "#b71c1c"], [0.4, "#880e4f"],
                [0.5, "#1a1a2e"],
                [0.6, "#1b5e20"], [1.0, "#00e676"],
            ],
            zmid=0,
            text=np.round(pivot.values, 1),
            texttemplate="%{text}",
            textfont=dict(size=9),
            hovertemplate="<b>%{y}</b> | %{x}<br>Điểm: %{z:.2f}<extra></extra>",
            colorbar=dict(title="Điểm"),
        ))
        fig_h.update_layout(
            template="plotly_dark",
            height=max(400, len(pivot) * 22),
            margin=dict(l=20, r=20, t=20, b=80),
            xaxis=dict(tickangle=-45, tickfont=dict(size=9)),
            yaxis=dict(tickfont=dict(size=10)),
        )
        st.plotly_chart(fig_h, use_container_width=True)

    # ── Probability table ──
    st.markdown("---")
    st.markdown("#### 🎯 Xác suất xuất hiện trong đợt UP / DOWN")

    n_up   = len(pc_with_data[pc_with_data["Type"] == "UP"])
    n_down = len(pc_with_data[pc_with_data["Type"] == "DOWN"])

    up_app = (
        all_data[(all_data["period_type"]=="UP") & (all_data["InfluenceIndex"] > 0)]
        .groupby("StockCode")["InfluenceIndex"].agg(["count","sum","mean"])
        .rename(columns={"count":"up_count","sum":"up_total","mean":"up_avg"})
    )
    dn_app = (
        all_data[(all_data["period_type"]=="DOWN") & (all_data["InfluenceIndex"] < 0)]
        .groupby("StockCode")["InfluenceIndex"].agg(["count","sum","mean"])
        .rename(columns={"count":"dn_count","sum":"dn_total","mean":"dn_avg"})
    )

    prob = pd.concat([up_app, dn_app], axis=1).fillna(0)
    prob["up_count"] = prob["up_count"].astype(int)
    prob["dn_count"] = prob["dn_count"].astype(int)
    if n_up > 0:
        prob["P(Tăng|UP)%"]  = (prob["up_count"] / n_up * 100).round(1)
    else:
        prob["P(Tăng|UP)%"] = 0
    if n_down > 0:
        prob["P(Giảm|DOWN)%"] = (prob["dn_count"] / n_down * 100).round(1)
    else:
        prob["P(Giảm|DOWN)%"] = 0

    prob["Vai trò UP (tổng đóng góp)"] = prob["up_total"].round(1)
    prob["Vai trò DOWN (tổng kéo giảm)"] = prob["dn_total"].round(1)

    display_prob = prob[["up_count","P(Tăng|UP)%","Vai trò UP (tổng đóng góp)",
                          "dn_count","P(Giảm|DOWN)%","Vai trò DOWN (tổng kéo giảm)"]].copy()
    display_prob.columns = [
        "Số đợt UP tăng", "P(Tăng|UP)%", "Tổng đóng góp UP",
        "Số đợt DOWN giảm", "P(Giảm|DOWN)%", "Tổng kéo giảm DOWN"
    ]
    display_prob = display_prob.sort_values("P(Tăng|UP)%", ascending=False)
    display_prob = display_prob[display_prob[["Số đợt UP tăng","Số đợt DOWN giảm"]].max(axis=1) >= min_periods]

    st.dataframe(
        display_prob.style
        .background_gradient(subset=["P(Tăng|UP)%"], cmap="Greens")
        .background_gradient(subset=["P(Giảm|DOWN)%"], cmap="Reds")
        .format({
            "P(Tăng|UP)%": "{:.1f}%",
            "P(Giảm|DOWN)%": "{:.1f}%",
            "Tổng đóng góp UP": "{:+.1f}",
            "Tổng kéo giảm DOWN": "{:+.1f}",
        }),
        use_container_width=True,
        height=500,
    )

    st.caption(
        f"📌 Tổng số đợt UP có dữ liệu: {n_up} | Tổng số đợt DOWN có dữ liệu: {n_down}. "
        "P(Tăng|UP)% = xác suất cổ phiếu đóng góp dương trong đợt UP của VNIndex."
    )


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    st.title("📈 VNIndex Contribution Dashboard")
    st.caption("Dữ liệu HOSE · Cập nhật tự động từ Google Sheets")

    try:
        hist_raw, pc_raw, c_old_raw, c_new_raw = load_all()
    except Exception as e:
        st.error(f"❌ Không tải được dữ liệu: {e}")
        st.stop()

    # Preprocess
    hist_df   = prep_history(hist_raw)
    pc_df     = prep_pc(pc_raw)
    c_old_df  = prep_contribution_old(c_old_raw)
    c_new_agg = prep_contribution_new(c_new_raw, pc_df)
    combined  = combine_contributions(c_old_df, c_new_agg)

    # KPI bar
    last_row = hist_df.iloc[-1]
    prev_row = hist_df.iloc[-2]
    delta    = last_row["Close"] - prev_row["Close"]
    delta_p  = delta / prev_row["Close"] * 100

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("VNIndex", f"{last_row['Close']:,.2f}", f"{delta:+.2f} ({delta_p:+.2f}%)")
    k2.metric("Phiên gần nhất", last_row["Date"].strftime("%d/%m/%Y"))

    pc_latest = pc_df.iloc[-1]
    k3.metric("Đợt hiện tại", pc_latest["Type"],
              f"{pc_latest['Change_pct']:+.1f}% / {int(pc_latest['Days'])} ngày")
    k4.metric("Số đợt có dữ liệu", str(pc_df["has_data"].sum()))
    k5.metric("Tổng cổ phiếu tracking", str(combined["StockCode"].nunique()))

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs([
        "📊 Bảng Contribution theo đợt",
        "📈 Chart lịch sử VNIndex",
        "🔍 Insights & Xác suất"
    ])

    with tab1:
        render_tab1(pc_df, combined)
    with tab2:
        render_tab2(hist_df, pc_df)
    with tab3:
        render_tab3(pc_df, combined)

    st.markdown("---")
    st.caption("© VNIndex Dashboard · Dữ liệu từ HOSE · Không phải tư vấn đầu tư")


if __name__ == "__main__":
    main()
