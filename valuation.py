"""
valuation.py  v4
Changes:
  - Summary PE+PB (KPI snapshot) hien thi o DAU trang truoc cac chart
  - Bo rangeslider (chart nho phia duoi)
  - Cac chart chi hien thi sau phan summary
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
    if val >= p4:   return "🔴 Rat dat (>+2SD)",               "#e53935"
    if val >= p3:   return "🟠 Dat (+1SD ~ +2SD)",             "#fb8c00"
    if val >= mean: return "🟡 Tren trung binh (Mean ~ +1SD)", "#f9a825"
    if val >= p1:   return "🟢 Duoi trung binh (-1SD ~ Mean)", "#43a047"
    if val >= p2:   return "🟢 Re (-2SD ~ -1SD)",              "#1b5e20"
    return              "🔵 Rat re (<-2SD)",                   "#1565c0"

# ── SNAPSHOT CARD (hien o dau) ────────────────────────────────────────────────
def _snapshot_card(col_name, last_val, mean, median, sd, border_color):
    zone_label, zone_color = _zone(last_val, mean, sd)
    diff_mean   = (last_val - mean)   / abs(mean)   * 100 if mean   != 0 else 0
    diff_median = (last_val - median) / abs(median) * 100 if median != 0 else 0

    def _cmp_html(diff, ref_name, ref_val):
        if diff > 0:
            # Cao hon ref -> XAU (dat hon) -> do dam + in dam + in nghieng
            clr   = "#b71c1c"
            icon  = "▲"
            desc  = "cao hon"
            style = ("display:inline-block;font-weight:800;font-style:italic;"
                     "color:#fff;background:" + clr + ";"
                     "padding:2px 8px;border-radius:4px;font-size:14px;")
        else:
            # Thap hon ref -> TOT (re hon) -> xanh la dam + in dam
            clr   = "#1b5e20"
            icon  = "▼"
            desc  = "thap hon"
            style = ("display:inline-block;font-weight:800;"
                     "color:#fff;background:" + clr + ";"
                     "padding:2px 8px;border-radius:4px;font-size:14px;")
        return (
            '<div style="display:flex;align-items:center;gap:8px;margin:5px 0;">'
            '<span style="' + style + '">'
            + icon + '&nbsp;{:.1f}%'.format(abs(diff))
            + '</span>'
            '<span style="font-size:12px;color:#444;">'
            + desc + '&nbsp;<b>' + ref_name + '</b>'
            + '&nbsp;<span style="color:#999;font-size:11px;">({:.2f})</span>'.format(ref_val)
            + '</span>'
            '</div>'
        )

    # Header bar mau theo border_color
    return (
        '<div style="border:2px solid ' + border_color + ';border-radius:12px;'
        'overflow:hidden;box-shadow:0 2px 8px ' + border_color + '30;">'

        # Header strip
        + '<div style="background:' + border_color + ';padding:8px 18px;">'
        + '<span style="font-size:13px;font-weight:800;color:#fff;'
          'text-transform:uppercase;letter-spacing:1.5px;">'
        + col_name + ' Ratio</span>'
        + '</div>'

        # Body
        + '<div style="padding:16px 20px;background:#fff;">'

        # Gia tri hien tai
        + '<div style="font-size:42px;font-weight:900;color:#111;line-height:1;'
          'margin-bottom:14px;">'
        + '{:.2f}'.format(last_val)
        + '<span style="font-size:20px;font-weight:500;color:#aaa;">x</span>'
        + '</div>'

        # So sanh
        + _cmp_html(diff_mean,   "Mean",   mean)
        + _cmp_html(diff_median, "Median", median)

        # Vung dinh gia
        + '<div style="margin-top:14px;font-size:13px;padding:7px 12px;'
          'border-radius:6px;background:' + zone_color + '18;'
          'color:' + zone_color + ';font-weight:700;'
          'border-left:4px solid ' + zone_color + ';">'
        + zone_label
        + '</div>'

        # SD ranges
        + '<div style="margin-top:10px;font-size:11px;color:#aaa;">'
        + '±1SD&nbsp;[{:.2f}–{:.2f}]&nbsp;&nbsp;±2SD&nbsp;[{:.2f}–{:.2f}]'.format(
            mean - sd, mean + sd, mean - 2*sd, mean + 2*sd)
        + '</div>'

        + '</div></div>'  # close body + card
    )

# ── CHART ─────────────────────────────────────────────────────────────────────
def _build_chart(df_filtered, col, full_series,
                 title, line_color, color_mean, color_median, height=500):
    dp = df_filtered[["TradingDate", col]].dropna(subset=[col]).copy()
    if dp.empty:
        return go.Figure(), 0, 0, 0, 0

    v      = full_series.dropna()
    mean   = float(v.mean())
    median = float(v.median())
    sd     = float(v.std())
    last   = float(dp[col].iloc[-1])

    all_y  = list(dp[col].dropna()) + [mean+2*sd, mean-2*sd]
    y_min, y_max = min(all_y), max(all_y)
    y_pad  = (y_max - y_min) * 0.08
    y_rng  = [y_min - y_pad, y_max + y_pad]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Line chinh
    fig.add_trace(go.Scatter(
        x=dp["TradingDate"], y=dp[col],
        mode="lines", name=col,
        line=dict(color=line_color, width=2),
        hovertemplate="<b>%{x|%d/%m/%Y}</b><br>" + col + ": <b>%{y:.2f}</b><extra></extra>",
        showlegend=True,
    ), secondary_y=False)

    x0, x1 = dp["TradingDate"].iloc[0], dp["TradingDate"].iloc[-1]

    # Stat lines
    stat_legend = [
        ("Mean",   mean,        color_mean,   "dash",     1.5),
        ("Median", median,      color_median, "dot",      1.5),
        ("+1SD",   mean + sd,   "#fb8c00",    "dashdot",  1.1),
        ("-1SD",   mean - sd,   "#fb8c00",    "dashdot",  1.1),
        ("+2SD",   mean + 2*sd, "#e53935",    "longdash", 1.0),
        ("-2SD",   mean - 2*sd, "#e53935",    "longdash", 1.0),
    ]
    for label, yv, color, dash, w in stat_legend:
        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[yv, yv],
            mode="lines", name=col + " " + label,
            line=dict(color=color, dash=dash, width=w),
            hovertemplate=label + " = <b>{:.2f}</b><extra></extra>".format(yv),
            showlegend=True,
        ), secondary_y=False)

    # Truc Y phai: tickvals tai cac gia tri stat
    tick_vals = sorted(set([last, mean, median,
                             mean+sd, mean-sd, mean+2*sd, mean-2*sd]))

    def _lbl(yv):
        tol = 1e-6
        if abs(yv - last)        < tol: return "<b>" + col + "={:.2f}</b>".format(yv)
        if abs(yv - mean)        < tol: return "Mean={:.2f}".format(yv)
        if abs(yv - median)      < tol: return "Med={:.2f}".format(yv)
        if abs(yv - (mean+sd))   < tol: return "+1SD={:.2f}".format(yv)
        if abs(yv - (mean-sd))   < tol: return "-1SD={:.2f}".format(yv)
        if abs(yv - (mean+2*sd)) < tol: return "+2SD={:.2f}".format(yv)
        if abs(yv - (mean-2*sd)) < tol: return "-2SD={:.2f}".format(yv)
        return "{:.2f}".format(yv)

    fig.add_trace(go.Scatter(
        x=[x0], y=[last], mode="markers",
        marker=dict(opacity=0, size=1),
        showlegend=False, hoverinfo="skip",
    ), secondary_y=True)

    fig.update_layout(
        template="plotly_white",
        title=dict(text=title, font=dict(size=14, color="#333"), x=0),
        height=height,
        margin=dict(l=60, r=130, t=45, b=40),
        hovermode="x unified",
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(color="#333"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="left", x=0, font=dict(size=11)),
        xaxis=dict(
            showgrid=True, gridcolor="#efefef",
            tickformat="%m/%Y", linecolor="#ccc",
            # KHONG co rangeslider
            type="date",
        ),
    )
    fig.update_yaxes(range=y_rng, showgrid=True, gridcolor="#efefef",
                     zeroline=False, linecolor="#ccc",
                     title_text=col, secondary_y=False)
    fig.update_yaxes(range=y_rng,
                     tickvals=tick_vals,
                     ticktext=[_lbl(yv) for yv in tick_vals],
                     showgrid=False, zeroline=False,
                     tickfont=dict(size=10),
                     automargin=True, secondary_y=True, side="right")

    return fig, mean, median, sd, last

# ── DATE CONTROLS ─────────────────────────────────────────────────────────────
def _date_controls(min_date, max_date, key_prefix):
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        preset = st.selectbox("Chon nhanh",
                              ["Toan bo", "10 nam", "5 nam", "3 nam", "1 nam"],
                              key=key_prefix + "_preset")
    offsets = {"10 nam": 3650, "5 nam": 1825, "3 nam": 1095, "1 nam": 365}
    ds = max(max_date - datetime.timedelta(days=offsets[preset])
             if preset in offsets else min_date, min_date)
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
    # Header + Refresh
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

    # Stat tren toan bo lich su
    pe_full = df["PE"].dropna()
    pb_full = df["PB"].dropna()
    mean_pe, med_pe, sd_pe = float(pe_full.mean()), float(pe_full.median()), float(pe_full.std())
    mean_pb, med_pb, sd_pb = float(pb_full.mean()), float(pb_full.median()), float(pb_full.std())
    last_pe = float(pe_full.iloc[-1])
    last_pb = float(pb_full.iloc[-1])

    # ── SNAPSHOT ROW (PE + PB) o DAU ─────────────────────────────────────────
    st.markdown("#### 📊 Dinh gia hien tai")
    snap_c1, snap_c2 = st.columns(2)
    with snap_c1:
        st.markdown(
            _snapshot_card("P/E", last_pe, mean_pe, med_pe, sd_pe, "#1565c0"),
            unsafe_allow_html=True)
    with snap_c2:
        st.markdown(
            _snapshot_card("P/B", last_pb, mean_pb, med_pb, sd_pb, "#e53935"),
            unsafe_allow_html=True)

    st.markdown("---")

    # ── CHART PE ──────────────────────────────────────────────────────────────
    st.markdown("### 📐 P/E Ratio – VNIndex")
    st.caption("Stat lines tinh tren toan bo lich su, doc lap voi bo loc ngay.")
    s_pe, e_pe = _date_controls(min_date, max_date, "pe")
    df_pe = df[(df["TradingDate"] >= pd.Timestamp(s_pe)) &
               (df["TradingDate"] <= pd.Timestamp(e_pe))].copy()

    if not df_pe.empty and df_pe["PE"].notna().sum() > 0:
        fig_pe, _, _, _, _ = _build_chart(
            df_pe, "PE", pe_full,
            "P/E VNIndex theo ngay",
            "#1565c0", "#7b1fa2", "#00838f",
        )
        st.plotly_chart(fig_pe, use_container_width=True)
    else:
        st.warning("Khong co du lieu PE trong khoang thoi gian nay.")

    st.markdown("---")

    # ── CHART PB ──────────────────────────────────────────────────────────────
    st.markdown("### 📐 P/B Ratio – VNIndex")
    st.caption("Stat lines tinh tren toan bo lich su, doc lap voi bo loc ngay.")
    s_pb, e_pb = _date_controls(min_date, max_date, "pb")
    df_pb = df[(df["TradingDate"] >= pd.Timestamp(s_pb)) &
               (df["TradingDate"] <= pd.Timestamp(e_pb))].copy()

    if not df_pb.empty and df_pb["PB"].notna().sum() > 0:
        fig_pb, _, _, _, _ = _build_chart(
            df_pb, "PB", pb_full,
            "P/B VNIndex theo ngay",
            "#e53935", "#7b1fa2", "#00838f",
        )
        st.plotly_chart(fig_pb, use_container_width=True)
    else:
        st.warning("Khong co du lieu PB trong khoang thoi gian nay.")

    st.markdown("---")
    st.caption(
        "📌 Mean/Median/±SD tinh tren " + str(len(df)) + " phien ("
        + df["TradingDate"].min().strftime("%d/%m/%Y")
        + " → " + df["TradingDate"].max().strftime("%d/%m/%Y")
        + "). Bo loc ngay chi anh huong vung hien thi line chinh."
    )
