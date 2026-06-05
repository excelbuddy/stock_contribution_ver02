"""
valuation.py  v3
Dinh gia VNIndex – PE & PB
Fix:
  1. cache_data.clear() + ttl ngan -> luon lay du lieu moi
  2. Annotation dat o yaxis2 (truc phai rieng) -> khong bao gio che data
  3. KPI: PE hien tai | so voi Mean | so voi Median | Vung dinh gia
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io, requests, datetime

PEPB_SHEET_ID = "1IEx1-UrFAavocKRvafm-gdLC-LNWvGIx9WxXHQgyZsM"

# ── DATA ──────────────────────────────────────────────────────────────────────
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

# ── ZONE ──────────────────────────────────────────────────────────────────────
def _zone(val, mean, sd):
    p1, p2, p3, p4 = mean - sd, mean - 2*sd, mean + sd, mean + 2*sd
    if val >= p4:   return "🔴 Rat dat (>+2SD)",              "#e53935"
    if val >= p3:   return "🟠 Dat (+1SD ~ +2SD)",            "#fb8c00"
    if val >= mean: return "🟡 Tren trung binh (Mean ~ +1SD)","#f9a825"
    if val >= p1:   return "🟢 Duoi trung binh (-1SD ~ Mean)","#43a047"
    if val >= p2:   return "🟢 Re (-2SD ~ -1SD)",             "#1b5e20"
    return              "🔵 Rat re (<-2SD)",                  "#1565c0"

# ── CHART ─────────────────────────────────────────────────────────────────────
def _build_chart(df_filtered, col, full_series,
                 title, line_color, color_mean, color_median, height=530):
    """
    Dung make_subplots voi secondary_y=True.
    Truc Y trai: gia tri PE/PB (data + stat lines)
    Truc Y phai: dummy range giong Y trai, chi de hien tick labels
                 = cac gia tri stat (Mean, Median, +/-1SD, +/-2SD, hien tai)
    Nho do label khong bao gio che len data.
    """
    dp = df_filtered[["TradingDate", col]].dropna(subset=[col]).copy()
    if dp.empty:
        return go.Figure(), 0, 0, 0, 0

    v      = full_series.dropna()
    mean   = float(v.mean())
    median = float(v.median())
    sd     = float(v.std())
    last   = float(dp[col].iloc[-1])

    stat_vals = {
        col + " hien tai": (last,         line_color,   "solid",    2.0),
        "Mean":             (mean,         color_mean,   "dash",     1.5),
        "Median":           (median,       color_median, "dot",      1.5),
        "+1SD":             (mean + sd,    "#fb8c00",    "dashdot",  1.1),
        "-1SD":             (mean - sd,    "#fb8c00",    "dashdot",  1.1),
        "+2SD":             (mean + 2*sd,  "#e53935",    "longdash", 1.0),
        "-2SD":             (mean - 2*sd,  "#e53935",    "longdash", 1.0),
    }

    # Y range chung
    all_y  = [t[0] for t in stat_vals.values()] + list(dp[col].dropna())
    y_min  = min(all_y)
    y_max  = max(all_y)
    y_pad  = (y_max - y_min) * 0.08
    y_rng  = [y_min - y_pad, y_max + y_pad]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # ── Line chinh (truc trai) ────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=dp["TradingDate"], y=dp[col],
        mode="lines", name=col,
        line=dict(color=line_color, width=2),
        hovertemplate="<b>%{x|%d/%m/%Y}</b><br>" + col + ": <b>%{y:.2f}</b><extra></extra>",
        showlegend=True,
    ), secondary_y=False)

    x0 = dp["TradingDate"].iloc[0]
    x1 = dp["TradingDate"].iloc[-1]

    # ── Stat lines (truc trai, hien trong legend) ─────────────────────────────
    stat_legend = [
        ("Mean",    mean,        color_mean,   "dash",     1.5),
        ("Median",  median,      color_median, "dot",      1.5),
        ("+1SD",    mean + sd,   "#fb8c00",    "dashdot",  1.1),
        ("-1SD",    mean - sd,   "#fb8c00",    "dashdot",  1.1),
        ("+2SD",    mean + 2*sd, "#e53935",    "longdash", 1.0),
        ("-2SD",    mean - 2*sd, "#e53935",    "longdash", 1.0),
    ]
    for label, yv, color, dash, w in stat_legend:
        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[yv, yv],
            mode="lines",
            name=col + " " + label,
            line=dict(color=color, dash=dash, width=w),
            hovertemplate=label + " = <b>" + "{:.2f}".format(yv) + "</b><extra></extra>",
            showlegend=True,
        ), secondary_y=False)

    # ── Truc Y PHAI: tick tai dung cac gia tri stat ───────────────────────────
    # Them 1 trace invisible tren secondary_y de keo tickvals vao
    tick_vals  = sorted(set([last, mean, median,
                              mean+sd, mean-sd, mean+2*sd, mean-2*sd]))

    def _tick_label(yv):
        if abs(yv - last)       < 0.001: return "<b>" + col + "={:.2f}</b>".format(yv)
        if abs(yv - mean)       < 0.001: return "Mean={:.2f}".format(yv)
        if abs(yv - median)     < 0.001: return "Med={:.2f}".format(yv)
        if abs(yv - (mean+sd))  < 0.001: return "+1SD={:.2f}".format(yv)
        if abs(yv - (mean-sd))  < 0.001: return "-1SD={:.2f}".format(yv)
        if abs(yv - (mean+2*sd))< 0.001: return "+2SD={:.2f}".format(yv)
        if abs(yv - (mean-2*sd))< 0.001: return "-2SD={:.2f}".format(yv)
        return "{:.2f}".format(yv)

    tick_labels = [_tick_label(yv) for yv in tick_vals]

    # Invisible scatter tren truc phai de set tickvals
    fig.add_trace(go.Scatter(
        x=[x0], y=[last],
        mode="markers", marker=dict(opacity=0, size=1),
        showlegend=False, hoverinfo="skip",
    ), secondary_y=True)

    # ── Layout ────────────────────────────────────────────────────────────────
    fig.update_layout(
        template="plotly_white",
        title=dict(text=title, font=dict(size=15, color="#333"), x=0),
        height=height,
        margin=dict(l=60, r=20, t=50, b=50),
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
    )

    # Truc trai
    fig.update_yaxes(
        range=y_rng,
        showgrid=True, gridcolor="#efefef",
        zeroline=False, linecolor="#ccc",
        title_text=col,
        secondary_y=False,
    )

    # Truc phai: tick tai cac gia tri stat, mau tuong ung, khong grid
    # Phai set range = y_rng de dong bo voi truc trai
    fig.update_yaxes(
        range=y_rng,
        tickvals=tick_vals,
        ticktext=tick_labels,
        showgrid=False,
        zeroline=False,
        tickfont=dict(size=10),
        secondary_y=True,
        side="right",
    )

    return fig, mean, median, sd, last

# ── KPI ROW ───────────────────────────────────────────────────────────────────
def _render_kpi(col_name, last_val, mean, median, sd):
    zone_label, zone_color = _zone(last_val, mean, sd)

    diff_mean   = (last_val - mean)   / abs(mean)   * 100 if mean   != 0 else 0
    diff_median = (last_val - median) / abs(median) * 100 if median != 0 else 0

    sign_m  = "▲" if diff_mean   > 0 else "▼"
    sign_md = "▲" if diff_median > 0 else "▼"
    dir_m   = "cao hon" if diff_mean   > 0 else "thap hon"
    dir_md  = "cao hon" if diff_median > 0 else "thap hon"

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(col_name + " Hien tai", "{:.2f}x".format(last_val))
    k2.metric(
        "So voi Mean ({:.2f})".format(mean),
        "{} {} {:.1f}%".format(sign_m, dir_m, abs(diff_mean)),
    )
    k3.metric(
        "So voi Median ({:.2f})".format(median),
        "{} {} {:.1f}%".format(sign_md, dir_md, abs(diff_median)),
    )
    k4.metric("Vung dinh gia", zone_label)

    st.markdown(
        '<div style="background:#f8f8f8;border-left:4px solid '
        + zone_color
        + ';padding:7px 14px;border-radius:4px;margin:2px 0 18px 0;font-size:13px;">'
        + col_name + " = <b>{:.2f}x</b>".format(last_val)
        + " &nbsp;|&nbsp; Mean: {:.2f}".format(mean)
        + " &nbsp;|&nbsp; Median: {:.2f}".format(median)
        + " &nbsp;|&nbsp; ±1SD: [{:.2f} – {:.2f}]".format(mean - sd, mean + sd)
        + " &nbsp;|&nbsp; ±2SD: [{:.2f} – {:.2f}]".format(mean - 2*sd, mean + 2*sd)
        + '</div>',
        unsafe_allow_html=True,
    )

# ── DATE CONTROLS ─────────────────────────────────────────────────────────────
def _date_controls(min_date, max_date, key_prefix):
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        preset = st.selectbox(
            "Chon nhanh",
            ["Toan bo", "10 nam", "5 nam", "3 nam", "1 nam"],
            key=key_prefix + "_preset",
        )
    offsets = {"10 nam": 3650, "5 nam": 1825, "3 nam": 1095, "1 nam": 365}
    ds = (max_date - datetime.timedelta(days=offsets[preset])
          if preset in offsets else min_date)
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

# ── RENDER ────────────────────────────────────────────────────────────────────
def render():
    col_h, col_r = st.columns([9, 1])
    with col_r:
        if st.button("🔄 Refresh", key="val_refresh"):
            st.cache_data.clear()
            st.rerun()

    with st.spinner("Dang tai du lieu PE/PB tu Google Sheets..."):
        try:
            df = load_pepb()
        except Exception as e:
            st.error("Khong tai duoc du lieu: " + str(e))
            return

    with col_h:
        st.caption(
            "Nguon: Google Sheets PE-PB | StockCode: VNINDEX | "
            "Du lieu moi nhat: **" + df["TradingDate"].max().strftime("%d/%m/%Y") + "**"
            + " | " + str(len(df)) + " phien"
            + " | Khoang: " + df["TradingDate"].min().strftime("%d/%m/%Y")
            + " – " + df["TradingDate"].max().strftime("%d/%m/%Y")
        )

    min_date = df["TradingDate"].min().date()
    max_date = df["TradingDate"].max().date()

    # Stat tren TOAN BO lich su (bat bien vs date filter)
    pe_full = df["PE"].dropna()
    pb_full = df["PB"].dropna()
    mean_pe, med_pe, sd_pe = float(pe_full.mean()), float(pe_full.median()), float(pe_full.std())
    mean_pb, med_pb, sd_pb = float(pb_full.mean()), float(pb_full.median()), float(pb_full.std())

    # ── PE ────────────────────────────────────────────────────────────────────
    st.markdown("### 📐 P/E Ratio – VNIndex")
    st.caption("Stat lines tinh tren toan bo lich su, doc lap voi bo loc ngay.")
    s_pe, e_pe = _date_controls(min_date, max_date, "pe")
    df_pe = df[(df["TradingDate"] >= pd.Timestamp(s_pe)) &
               (df["TradingDate"] <= pd.Timestamp(e_pe))].copy()

    if not df_pe.empty and df_pe["PE"].notna().sum() > 0:
        fig_pe, _, _, _, last_pe = _build_chart(
            df_pe, "PE", pe_full,
            "P/E VNIndex theo ngay",
            "#1565c0", "#7b1fa2", "#00838f",
        )
        st.plotly_chart(fig_pe, use_container_width=True)
        _render_kpi("PE", last_pe, mean_pe, med_pe, sd_pe)
    else:
        st.warning("Khong co du lieu PE trong khoang thoi gian nay.")

    st.markdown("---")

    # ── PB ────────────────────────────────────────────────────────────────────
    st.markdown("### 📐 P/B Ratio – VNIndex")
    st.caption("Stat lines tinh tren toan bo lich su, doc lap voi bo loc ngay.")
    s_pb, e_pb = _date_controls(min_date, max_date, "pb")
    df_pb = df[(df["TradingDate"] >= pd.Timestamp(s_pb)) &
               (df["TradingDate"] <= pd.Timestamp(e_pb))].copy()

    if not df_pb.empty and df_pb["PB"].notna().sum() > 0:
        fig_pb, _, _, _, last_pb = _build_chart(
            df_pb, "PB", pb_full,
            "P/B VNIndex theo ngay",
            "#e53935", "#7b1fa2", "#00838f",
        )
        st.plotly_chart(fig_pb, use_container_width=True)
        _render_kpi("PB", last_pb, mean_pb, med_pb, sd_pb)
    else:
        st.warning("Khong co du lieu PB trong khoang thoi gian nay.")

    st.markdown("---")
    st.caption(
        "📌 Mean/Median/±SD tinh tren " + str(len(df)) + " phien ("
        + df["TradingDate"].min().strftime("%d/%m/%Y")
        + " → " + df["TradingDate"].max().strftime("%d/%m/%Y")
        + "). Bo loc ngay chi anh huong vung hien thi line chinh."
    )
