"""
valuation.py
Dinh gia VNIndex – Line chart PE & PB theo ngay
Nguon: Google Sheet PE-PB, chi lay StockCode = VNINDEX
Hien thi: line PE/PB + Mean + Median + ±1SD + ±2SD
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import io, requests, datetime

PEPB_SHEET_ID = "1IEx1-UrFAavocKRvafm-gdLC-LNWvGIx9WxXHQgyZsM"

# ── DATA LOADING ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def load_pepb():
    url = ("https://docs.google.com/spreadsheets/d/" + PEPB_SHEET_ID
           + "/gviz/tq?tqx=out:csv&sheet=PE-PB")
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = [c.strip() for c in df.columns]

    # Chi lay VNINDEX
    df = df[df["StockCode"].astype(str).str.strip() == "VNINDEX"].copy()

    df["TradingDate"] = pd.to_datetime(df["TradingDate"], errors="coerce")
    df = df.dropna(subset=["TradingDate"]).sort_values("TradingDate").reset_index(drop=True)
    df["PE"] = pd.to_numeric(df["PE"], errors="coerce")
    df["PB"] = pd.to_numeric(df["PB"], errors="coerce")
    return df

# ── STAT LINES BUILDER ────────────────────────────────────────────────────────

def _stat_traces(x, values, color_mean, color_median, name_prefix):
    """
    Tra ve list cac go.Scatter trace cho:
      Mean, Median, +1SD, -1SD, +2SD, -2SD
    """
    v       = values.dropna()
    mean    = v.mean()
    median  = v.median()
    sd      = v.std()

    traces = []

    def _hline(y, label, color, dash, width=1):
        return go.Scatter(
            x=[x.iloc[0], x.iloc[-1]],
            y=[y, y],
            mode="lines",
            name=label,
            line=dict(color=color, dash=dash, width=width),
            hovertemplate=label + ": <b>%{y:.2f}</b><extra></extra>",
            showlegend=True,
        )

    traces.append(_hline(mean,       name_prefix + " Mean",    color_mean,   "dash",    1.6))
    traces.append(_hline(median,     name_prefix + " Median",  color_median, "dot",     1.6))
    traces.append(_hline(mean + sd,  name_prefix + " +1SD",    "#fb8c00",    "dashdot", 1.2))
    traces.append(_hline(mean - sd,  name_prefix + " -1SD",    "#fb8c00",    "dashdot", 1.2))
    traces.append(_hline(mean + 2*sd,name_prefix + " +2SD",    "#e53935",    "longdash",1.0))
    traces.append(_hline(mean - 2*sd,name_prefix + " -2SD",    "#e53935",    "longdash",1.0))

    return traces, mean, median, sd

# ── CHART BUILDER ─────────────────────────────────────────────────────────────

def _build_chart(df, col, title, line_color, color_mean, color_median, height=500):
    df_plot = df[["TradingDate", col]].dropna(subset=[col])
    if df_plot.empty:
        return go.Figure()

    fig = go.Figure()

    # Line chinh
    fig.add_trace(go.Scatter(
        x=df_plot["TradingDate"],
        y=df_plot[col],
        mode="lines",
        name=col,
        line=dict(color=line_color, width=2),
        hovertemplate="<b>%{x|%d/%m/%Y}</b><br>" + col + ": <b>%{y:.2f}</b><extra></extra>",
        showlegend=True,
        zorder=10,
    ))

    # Stat lines
    stat_traces, mean, median, sd = _stat_traces(
        df_plot["TradingDate"], df_plot[col],
        color_mean, color_median, col)
    for t in stat_traces:
        fig.add_trace(t)

    # Annotations ben phai (gia tri hien tai + stat)
    last_date = df_plot["TradingDate"].iloc[-1]
    last_val  = df_plot[col].iloc[-1]

    annotation_items = [
        (last_val,      line_color, "<b>" + col + " = {:.2f}</b>"),
        (mean,          color_mean,   "Mean = {:.2f}"),
        (median,        color_median, "Median = {:.2f}"),
        (mean + sd,     "#fb8c00",    "+1SD = {:.2f}"),
        (mean - sd,     "#fb8c00",    "−1SD = {:.2f}"),
        (mean + 2*sd,   "#e53935",    "+2SD = {:.2f}"),
        (mean - 2*sd,   "#e53935",    "−2SD = {:.2f}"),
    ]

    for val, color, fmt in annotation_items:
        fig.add_annotation(
            x=1.01, y=val,
            xref="paper", yref="y",
            text=fmt.format(val),
            showarrow=False,
            xanchor="left",
            font=dict(size=10, color=color),
            bgcolor="rgba(255,255,255,0.0)",
        )

    fig.update_layout(
        template="plotly_white",
        title=dict(text=title, font=dict(size=15, color="#333"), x=0),
        height=height,
        margin=dict(l=55, r=160, t=50, b=50),
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
        ),
        yaxis=dict(
            showgrid=True, gridcolor="#efefef",
            zeroline=False, linecolor="#ccc",
            title=col,
        ),
    )
    return fig, mean, median, sd, last_val

# ── SUMMARY TABLE ─────────────────────────────────────────────────────────────

def _summary_table(df, col, mean, median, sd, last_val):
    """Hien thi bang tom tat thong ke va vi tri hien tai."""
    p1 = mean - sd;    p2 = mean - 2*sd
    p3 = mean + sd;    p4 = mean + 2*sd

    if last_val >= p4:
        zone = "🔴 Rat dat (>+2SD)"
        zone_color = "#e53935"
    elif last_val >= p3:
        zone = "🟠 Dat (+1SD ~ +2SD)"
        zone_color = "#fb8c00"
    elif last_val >= mean:
        zone = "🟡 Tren trung binh (Mean ~ +1SD)"
        zone_color = "#f9a825"
    elif last_val >= p1:
        zone = "🟢 Duoi trung binh (-1SD ~ Mean)"
        zone_color = "#43a047"
    elif last_val >= p2:
        zone = "🟢 Re (-2SD ~ -1SD)"
        zone_color = "#1b5e20"
    else:
        zone = "🔵 Rat re (<-2SD)"
        zone_color = "#1565c0"

    stats = {
        "Chi so": col,
        "Hien tai": "{:.2f}".format(last_val),
        "Mean": "{:.2f}".format(mean),
        "Median": "{:.2f}".format(median),
        "+1SD": "{:.2f}".format(mean + sd),
        "-1SD": "{:.2f}".format(mean - sd),
        "+2SD": "{:.2f}".format(mean + 2 * sd),
        "-2SD": "{:.2f}".format(mean - 2 * sd),
        "Vung dinh gia": zone,
    }
    return stats, zone_color

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
    # Load data
    try:
        with st.spinner("Dang tai du lieu PE/PB..."):
            df = load_pepb()
    except Exception as e:
        st.error("Khong tai duoc du lieu: " + str(e))
        return

    # Refresh button
    col_h, col_r = st.columns([9, 1])
    with col_h:
        st.caption(
            "Nguon: Google Sheets PE-PB | StockCode: VNINDEX | "
            "Cap nhat: " + df["TradingDate"].max().strftime("%d/%m/%Y")
            + " | " + str(len(df)) + " phien")
    with col_r:
        st.markdown("<div style='margin-top:6px'></div>", unsafe_allow_html=True)
        if st.button("Refresh", key="val_refresh"):
            st.cache_data.clear()
            st.rerun()

    min_date = df["TradingDate"].min().date()
    max_date = df["TradingDate"].max().date()

    # ── CHART PE ──────────────────────────────────────────────────────────────
    st.markdown("### 📐 P/E Ratio – VNIndex")
    st.caption("Cac duong tham chieu tinh tren toan bo lich su du lieu (khong theo khoang loc ngay).")

    s_pe, e_pe = _date_controls(min_date, max_date, "pe")
    mask_pe = (df["TradingDate"] >= pd.Timestamp(s_pe)) & \
              (df["TradingDate"] <= pd.Timestamp(e_pe))
    df_pe = df[mask_pe].copy()

    # Tinh stat tren toan bo lich su (khong bi anh huong boi date filter)
    pe_full  = df["PE"].dropna()
    mean_pe  = pe_full.mean()
    med_pe   = pe_full.median()
    sd_pe    = pe_full.std()

    if not df_pe.empty and df_pe["PE"].notna().sum() > 0:
        fig_pe, _, _, _, last_pe = _build_chart(
            df_pe, "PE",
            "P/E VNIndex theo ngay",
            line_color="#1565c0",
            color_mean="#7b1fa2",
            color_median="#00838f",
        )
        st.plotly_chart(fig_pe, use_container_width=True)

        # Summary stats
        last_pe_val = df_pe["PE"].dropna().iloc[-1]
        stats_pe, zc_pe = _summary_table(df_pe, "PE", mean_pe, med_pe, sd_pe, last_pe_val)

        k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
        cols = [k1, k2, k3, k4, k5, k6, k7]
        keys_labels = [
            ("Hien tai", "PE Hien tai"),
            ("Mean", "Mean (LS)"),
            ("Median", "Median (LS)"),
            ("+1SD", "+1 SD"),
            ("-1SD", "−1 SD"),
            ("+2SD", "+2 SD"),
            ("-2SD", "−2 SD"),
        ]
        for col_widget, (key, label) in zip(cols, keys_labels):
            col_widget.metric(label, stats_pe[key])

        st.markdown(
            '<div style="background:#f5f5f5;border-left:4px solid '
            + zc_pe + ';padding:8px 14px;border-radius:4px;margin:4px 0 16px 0;">'
            '<b>Dinh gia PE hien tai:</b> ' + stats_pe["Vung dinh gia"] + '</div>',
            unsafe_allow_html=True)
    else:
        st.warning("Khong co du lieu PE trong khoang thoi gian nay.")

    st.markdown("---")

    # ── CHART PB ──────────────────────────────────────────────────────────────
    st.markdown("### 📐 P/B Ratio – VNIndex")
    st.caption("Cac duong tham chieu tinh tren toan bo lich su du lieu (khong theo khoang loc ngay).")

    s_pb, e_pb = _date_controls(min_date, max_date, "pb")
    mask_pb = (df["TradingDate"] >= pd.Timestamp(s_pb)) & \
              (df["TradingDate"] <= pd.Timestamp(e_pb))
    df_pb = df[mask_pb].copy()

    pb_full  = df["PB"].dropna()
    mean_pb  = pb_full.mean()
    med_pb   = pb_full.median()
    sd_pb    = pb_full.std()

    if not df_pb.empty and df_pb["PB"].notna().sum() > 0:
        fig_pb, _, _, _, last_pb = _build_chart(
            df_pb, "PB",
            "P/B VNIndex theo ngay",
            line_color="#e53935",
            color_mean="#7b1fa2",
            color_median="#00838f",
        )
        st.plotly_chart(fig_pb, use_container_width=True)

        last_pb_val = df_pb["PB"].dropna().iloc[-1]
        stats_pb, zc_pb = _summary_table(df_pb, "PB", mean_pb, med_pb, sd_pb, last_pb_val)

        k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
        cols = [k1, k2, k3, k4, k5, k6, k7]
        for col_widget, (key, label) in zip(cols, keys_labels):
            col_widget.metric(label, stats_pb[key])

        st.markdown(
            '<div style="background:#f5f5f5;border-left:4px solid '
            + zc_pb + ';padding:8px 14px;border-radius:4px;margin:4px 0 16px 0;">'
            '<b>Dinh gia PB hien tai:</b> ' + stats_pb["Vung dinh gia"] + '</div>',
            unsafe_allow_html=True)
    else:
        st.warning("Khong co du lieu PB trong khoang thoi gian nay.")

    st.markdown("---")

    # ── NOTE ──────────────────────────────────────────────────────────────────
    st.caption(
        "📌 **Chu thich:** Mean, Median va cac duong do lech chuan (±1SD, ±2SD) "
        "duoc tinh tren toan bo lich su du lieu (tu " + df["TradingDate"].min().strftime("%d/%m/%Y")
        + "), khong phu thuoc vao khoang thoi gian loc hien thi. "
        "Khoang loc chi anh huong den vung hien thi cua line chinh tren chart.")
