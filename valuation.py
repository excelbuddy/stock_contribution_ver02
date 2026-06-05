"""
valuation.py
Dinh gia VNIndex – Line chart PE & PB theo ngay
Nguon: Google Sheet PE-PB, chi lay StockCode = VNINDEX
Hien thi: line PE/PB + Mean + Median + ±1SD + ±2SD

Fix v2:
  1. ttl=0 -> luon tai lai tu Google Sheet moi lan load (khong cache vinh vien)
  2. Right-margin mo rong + annotations dat o paper x=1.0 voi clip=False de khong bi cat
  3. KPI row moi: PE hien tai | so sanh voi Mean | so sanh voi Median | Vung dinh gia
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import io, requests, datetime

PEPB_SHEET_ID = "1IEx1-UrFAavocKRvafm-gdLC-LNWvGIx9WxXHQgyZsM"

# ── DATA LOADING ──────────────────────────────────────────────────────────────
# ttl=300: cache 5 phut de khong spam Google Sheet,
# nhung moi lan Refresh button bam se clear cache ngay lap tuc.
@st.cache_data(ttl=300, show_spinner=False)
def load_pepb():
    url = ("https://docs.google.com/spreadsheets/d/" + PEPB_SHEET_ID
           + "/gviz/tq?tqx=out:csv&sheet=PE-PB")
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = [c.strip() for c in df.columns]
    df = df[df["StockCode"].astype(str).str.strip() == "VNINDEX"].copy()
    df["TradingDate"] = pd.to_datetime(df["TradingDate"], errors="coerce")
    df = df.dropna(subset=["TradingDate"]).sort_values("TradingDate").reset_index(drop=True)
    df["PE"] = pd.to_numeric(df["PE"], errors="coerce")
    df["PB"] = pd.to_numeric(df["PB"], errors="coerce")
    return df

# ── ZONE CLASSIFIER ───────────────────────────────────────────────────────────

def _zone(val, mean, sd):
    p1, p2, p3, p4 = mean - sd, mean - 2*sd, mean + sd, mean + 2*sd
    if val >= p4:   return "🔴 Rat dat (>+2SD)",           "#e53935"
    if val >= p3:   return "🟠 Dat (+1SD ~ +2SD)",         "#fb8c00"
    if val >= mean: return "🟡 Tren trung binh (Mean~+1SD)","#f9a825"
    if val >= p1:   return "🟢 Duoi trung binh (-1SD~Mean)","#43a047"
    if val >= p2:   return "🟢 Re (-2SD ~ -1SD)",          "#1b5e20"
    return              "🔵 Rat re (<-2SD)",                "#1565c0"

# ── DELTA LABEL HELPER ────────────────────────────────────────────────────────

def _delta_label(val, ref, ref_name):
    """Tra ve string mo ta khoang cach % so voi ref."""
    if ref == 0:
        return "N/A"
    pct = (val - ref) / abs(ref) * 100
    direction = "cao hon" if pct > 0 else "thap hon"
    return "{} {} {:.1f}%".format(direction, ref_name, abs(pct))

# ── CHART BUILDER ─────────────────────────────────────────────────────────────

def _build_chart(df_plot_in, col, full_series,
                 title, line_color, color_mean, color_median, height=520):
    """
    df_plot_in : df da loc theo date range (chi de ve line chinh)
    full_series: Series PE hoac PB cua toan bo lich su (de tinh stat)
    """
    df_plot = df_plot_in[["TradingDate", col]].dropna(subset=[col]).copy()
    if df_plot.empty:
        return go.Figure(), 0, 0, 0, 0

    v      = full_series.dropna()
    mean   = v.mean()
    median = v.median()
    sd     = v.std()

    x0 = df_plot["TradingDate"].iloc[0]
    x1 = df_plot["TradingDate"].iloc[-1]

    fig = go.Figure()

    # ── Line chinh ────────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=df_plot["TradingDate"], y=df_plot[col],
        mode="lines", name=col,
        line=dict(color=line_color, width=2),
        hovertemplate="<b>%{x|%d/%m/%Y}</b><br>" + col + ": <b>%{y:.2f}</b><extra></extra>",
        showlegend=True,
    ))

    # ── Stat horizontal lines ─────────────────────────────────────────────────
    stat_lines = [
        (mean,         col + " Mean",    color_mean,    "dash",     1.6),
        (median,       col + " Median",  color_median,  "dot",      1.6),
        (mean + sd,    col + " +1SD",    "#fb8c00",     "dashdot",  1.2),
        (mean - sd,    col + " -1SD",    "#fb8c00",     "dashdot",  1.2),
        (mean + 2*sd,  col + " +2SD",    "#e53935",     "longdash", 1.0),
        (mean - 2*sd,  col + " -2SD",    "#e53935",     "longdash", 1.0),
    ]
    for y_val, label, color, dash, width in stat_lines:
        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[y_val, y_val],
            mode="lines", name=label,
            line=dict(color=color, dash=dash, width=width),
            hovertemplate=label + ": <b>%{y:.2f}</b><extra></extra>",
            showlegend=True,
        ))

    # ── Annotations ben phai truc Y (dung yref='y', x=1.02 paper) ────────────
    # Dung xref='paper' x=1.02 -> nam NGOAI vung plot, khong che len data
    last_val = df_plot[col].iloc[-1]
    ann_items = [
        (last_val,       line_color,   "<b>" + col + " = {:.2f}</b>"),
        (mean,           color_mean,   "Mean = {:.2f}"),
        (median,         color_median, "Median = {:.2f}"),
        (mean + sd,      "#fb8c00",    "+1SD = {:.2f}"),
        (mean - sd,      "#fb8c00",    "−1SD = {:.2f}"),
        (mean + 2*sd,    "#e53935",    "+2SD = {:.2f}"),
        (mean - 2*sd,    "#e53935",    "−2SD = {:.2f}"),
    ]

    # Sap xep theo y de tranh overlap: gop cac annotation qua gan nhau
    ann_items_sorted = sorted(ann_items, key=lambda t: t[0], reverse=True)
    y_used = []
    min_gap = (v.max() - v.min()) * 0.035   # khoang cach toi thieu giua cac label

    def _safe_y(y_want):
        y_try = y_want
        for y_prev in y_used:
            if abs(y_try - y_prev) < min_gap:
                y_try = y_prev - min_gap
        y_used.append(y_try)
        return y_try

    for y_raw, color, fmt in ann_items_sorted:
        y_adj = _safe_y(y_raw)
        fig.add_annotation(
            xref="paper", yref="y",
            x=1.02, y=y_adj,
            text=fmt.format(y_raw),
            showarrow=(abs(y_adj - y_raw) > min_gap * 0.3),
            arrowhead=0, arrowwidth=1, arrowcolor=color,
            ax=0, ay=(y_adj - y_raw) * 0,   # chi de showarrow=True hien duong noi
            xanchor="left",
            font=dict(size=10, color=color),
            bgcolor="rgba(255,255,255,0.85)",
            borderpad=2,
            # clip=False la mac dinh trong plotly – annotation se hien ra ngoai plot area
        )

    fig.update_layout(
        template="plotly_white",
        title=dict(text=title, font=dict(size=15, color="#333"), x=0),
        height=height,
        # r=200 du cho cac annotation ben phai hien day du
        margin=dict(l=55, r=200, t=50, b=50),
        hovermode="x unified",
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color="#333"),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="left", x=0,
            font=dict(size=11),
        ),
        xaxis=dict(
            showgrid=True, gridcolor="#efefef",
            tickformat="%m/%Y", linecolor="#ccc",
            rangeslider=dict(visible=True, thickness=0.04),
            type="date",
            # Gioi han x range dung trong plot area, khong mo rong sang phai
            # (annotation nam ngoai plot area nen khong can them khoang trang trong x)
        ),
        yaxis=dict(
            showgrid=True, gridcolor="#efefef",
            zeroline=False, linecolor="#ccc",
            title=col,
        ),
    )
    return fig, mean, median, sd, last_val

# ── KPI ROW (moi) ─────────────────────────────────────────────────────────────

def _render_kpi(col_name, last_val, mean, median, sd):
    """
    Hien thi 4 metric:
      1. Gia tri hien tai
      2. So sanh voi Mean (% chenh lech + huong)
      3. So sanh voi Median (% chenh lech + huong)
      4. Vung dinh gia
    """
    zone_label, zone_color = _zone(last_val, mean, sd)

    diff_mean   = (last_val - mean)   / abs(mean)   * 100 if mean   != 0 else 0
    diff_median = (last_val - median) / abs(median) * 100 if median != 0 else 0

    dir_mean   = "▲ cao hon" if diff_mean   > 0 else "▼ thap hon"
    dir_median = "▲ cao hon" if diff_median > 0 else "▼ thap hon"

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        col_name + " Hien tai",
        "{:.2f}x".format(last_val),
    )
    k2.metric(
        "So voi Mean ({:.2f})".format(mean),
        "{} {:.1f}%".format(dir_mean, abs(diff_mean)),
        delta=None,
    )
    k3.metric(
        "So voi Median ({:.2f})".format(median),
        "{} {:.1f}%".format(dir_median, abs(diff_median)),
        delta=None,
    )
    k4.metric("Vung dinh gia", zone_label)

    # Banner mau
    st.markdown(
        '<div style="background:#f8f8f8;border-left:4px solid '
        + zone_color + ';padding:7px 14px;border-radius:4px;'
        'margin:2px 0 18px 0;font-size:13px;">'
        '<b>' + col_name + ' = ' + '{:.2f}x'.format(last_val) + '</b> &nbsp;|&nbsp; '
        'Mean: ' + '{:.2f}'.format(mean) + ' &nbsp;|&nbsp; '
        'Median: ' + '{:.2f}'.format(median) + ' &nbsp;|&nbsp; '
        '±1SD: [' + '{:.2f}'.format(mean - sd) + ' – ' + '{:.2f}'.format(mean + sd) + '] &nbsp;|&nbsp; '
        '±2SD: [' + '{:.2f}'.format(mean - 2*sd) + ' – ' + '{:.2f}'.format(mean + 2*sd) + ']'
        '</div>',
        unsafe_allow_html=True)

# ── DATE CONTROLS ─────────────────────────────────────────────────────────────

def _date_controls(min_date, max_date, key_prefix):
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        preset = st.selectbox(
            "Chon nhanh",
            ["Toan bo", "10 nam", "5 nam", "3 nam", "1 nam"],
            key=key_prefix + "_preset")
    if preset == "10 nam":
        ds = max_date - datetime.timedelta(days=365 * 10)
    elif preset == "5 nam":
        ds = max_date - datetime.timedelta(days=365 * 5)
    elif preset == "3 nam":
        ds = max_date - datetime.timedelta(days=365 * 3)
    elif preset == "1 nam":
        ds = max_date - datetime.timedelta(days=365)
    else:
        ds = min_date
    ds = max(ds, min_date)
    with c2:
        start = st.date_input("Tu ngay", value=ds,
                              min_value=min_date, max_value=max_date,
                              key=key_prefix + "_start_" + preset)
    with c3:
        end = st.date_input("Den ngay", value=max_date,
                            min_value=min_date, max_value=max_date,
                            key=key_prefix + "_end")
    return start, end

# ── MAIN RENDER ───────────────────────────────────────────────────────────────

def render():
    # Header + Refresh
    col_h, col_r = st.columns([9, 1])
    with col_r:
        st.markdown("<div style='margin-top:6px'></div>", unsafe_allow_html=True)
        if st.button("🔄 Refresh", key="val_refresh"):
            st.cache_data.clear()
            st.rerun()

    # Load data (luon lay moi tu Google Sheet, cache 5 phut)
    try:
        with st.spinner("Dang tai du lieu PE/PB tu Google Sheets..."):
            df = load_pepb()
    except Exception as e:
        st.error("Khong tai duoc du lieu: " + str(e))
        return

    with col_h:
        st.caption(
            "Nguon: Google Sheets PE-PB | StockCode: VNINDEX | "
            "Du lieu moi nhat: **" + df["TradingDate"].max().strftime("%d/%m/%Y") + "**"
            + " | " + str(len(df)) + " phien | Cache 5 phut (bam Refresh de cap nhat ngay)")

    min_date = df["TradingDate"].min().date()
    max_date = df["TradingDate"].max().date()

    # Tinh stat tren TOAN BO lich su (bat bien du filter ngay nao)
    pe_full = df["PE"].dropna()
    pb_full = df["PB"].dropna()
    mean_pe, med_pe, sd_pe = pe_full.mean(), pe_full.median(), pe_full.std()
    mean_pb, med_pb, sd_pb = pb_full.mean(), pb_full.median(), pb_full.std()

    # ── CHART PE ──────────────────────────────────────────────────────────────
    st.markdown("### 📐 P/E Ratio – VNIndex")
    st.caption("Stat lines (Mean/Median/SD) tinh tren toan bo lich su, doc lap voi khoang loc hien thi.")

    s_pe, e_pe = _date_controls(min_date, max_date, "pe")
    mask_pe = (df["TradingDate"] >= pd.Timestamp(s_pe)) & \
              (df["TradingDate"] <= pd.Timestamp(e_pe))
    df_pe = df[mask_pe].copy()

    if not df_pe.empty and df_pe["PE"].notna().sum() > 0:
        fig_pe, _, _, _, last_pe = _build_chart(
            df_pe, "PE", pe_full,
            "P/E VNIndex theo ngay",
            line_color="#1565c0",
            color_mean="#7b1fa2",
            color_median="#00838f",
        )
        st.plotly_chart(fig_pe, use_container_width=True)
        _render_kpi("PE", last_pe, mean_pe, med_pe, sd_pe)
    else:
        st.warning("Khong co du lieu PE trong khoang thoi gian nay.")

    st.markdown("---")

    # ── CHART PB ──────────────────────────────────────────────────────────────
    st.markdown("### 📐 P/B Ratio – VNIndex")
    st.caption("Stat lines (Mean/Median/SD) tinh tren toan bo lich su, doc lap voi khoang loc hien thi.")

    s_pb, e_pb = _date_controls(min_date, max_date, "pb")
    mask_pb = (df["TradingDate"] >= pd.Timestamp(s_pb)) & \
              (df["TradingDate"] <= pd.Timestamp(e_pb))
    df_pb = df[mask_pb].copy()

    if not df_pb.empty and df_pb["PB"].notna().sum() > 0:
        fig_pb, _, _, _, last_pb = _build_chart(
            df_pb, "PB", pb_full,
            "P/B VNIndex theo ngay",
            line_color="#e53935",
            color_mean="#7b1fa2",
            color_median="#00838f",
        )
        st.plotly_chart(fig_pb, use_container_width=True)
        _render_kpi("PB", last_pb, mean_pb, med_pb, sd_pb)
    else:
        st.warning("Khong co du lieu PB trong khoang thoi gian nay.")

    st.markdown("---")
    st.caption(
        "📌 **Chu thich:** Mean, Median, ±1SD, ±2SD tinh tren toan bo "
        + str(len(df)) + " phien (tu "
        + df["TradingDate"].min().strftime("%d/%m/%Y") + " den "
        + df["TradingDate"].max().strftime("%d/%m/%Y") + "). "
        "Khoang loc ngay chi anh huong vung hien thi cua PE/PB line. "
        "Bam 🔄 Refresh de lay du lieu moi nhat tu Google Sheets.")
