"""
macro.py
Vi mo & Hang hoa - 4 charts:
  1. Hang hoa (quy doi 100%)      - cols O:Y  (index 14:25)
  2. World Stock Index (quy doi)  - cols Z:AG (index 25:33)
  3. Chi so DXY va ty gia USD     - cols F:J  (index 5:10)
  4. Lai suat vi mo               - cols A:E  (index 0:5)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import io, requests, datetime

MACRO_SHEET_ID = "1zj3uFY0RwFUKTQNQCkQvPzvXqE3oPQlH7PVJ5VHsxyM"

# ── Mau series ────────────────────────────────────────────────────────────────
COLORS_HANGHOA = {
    "Dau tho WTI":     "#000080",
    "Duong":           "#ff0000",
    "Khi thien nhien": "#00aa00",
    "Nickel":          "#cc00cc",
    "Quang sat":       "#00aaaa",
    "Than coc":        "#34a853",
    "Thep HRC":        "#980000",
    "Copper":          "#ef6c00",
    "London Coffee":   "#563d00",
    "Platinum":        "#9e9e9e",
}

COLORS_WORLD = {
    "DAX":      "#1565c0",
    "DJI":      "#e53935",
    "Gold":     "#f9a825",
    "NIKKEI225":"#7b1fa2",
    "S&P500":   "#2e7d32",
    "SHANGHAI": "#d84315",
    "VNI":      "#00838f",
}

COLORS_DXY = {
    "DXY":          "#1565c0",
    "USD/VND (VCB)":"#e53935",
    "USDT":         "#2e7d32",
    "USDC":         "#f9a825",
}

COLORS_LAISUAT = {
    "Lai suat FED":           "#1565c0",
    "Lai suat LNH":           "#e53935",
    "TPCP My 5Y":             "#2e7d32",
    "TPCP VN 5Y":             "#f9a825",
}

# ── DATA LOADING ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def load_vimo_raw():
    url = ("https://docs.google.com/spreadsheets/d/" + MACRO_SHEET_ID
           + "/gviz/tq?tqx=out:csv&sheet=data.vimo")
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text), header=None)

def _parse_pct(series):
    return pd.to_numeric(
        series.astype(str).str.replace("%","",regex=False).str.strip(),
        errors="coerce")

def _parse_num(series):
    return pd.to_numeric(
        series.astype(str).str.replace(",","",regex=False).str.strip(),
        errors="coerce")

def _clean_header(s):
    if pd.isna(s): return ""
    s = str(s).strip()
    # Bo prefix importrange (co dang "https://... TenCot")
    if s.startswith("http"):
        parts = s.split(" ")
        # Tim phan tu dau tien khong phai URL va khong phai range
        for p in parts:
            if not p.startswith("http") and "!" not in p and ":" not in p and p:
                return p
        return parts[-1]
    # Bo prefix dang "!A3:K TenCot"
    if s.startswith("!") and " " in s:
        return s.split(" ", 1)[1].strip()
    return s

def load_hanghoa(raw):
    sub = raw.iloc[:, 14:25].copy()
    headers = [_clean_header(sub.iloc[0, i]) for i in range(sub.shape[1])]
    headers[0] = "Date"
    # Col 1 co the con prefix "!A3:K "
    for i in range(1, len(headers)):
        if not headers[i] or headers[i] == "nan":
            headers[i] = f"Col{i}"
    data = sub.iloc[1:].copy()
    data.columns = headers
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    for col in headers[1:]:
        data[col] = _parse_pct(data[col])
    # Rename tieng Viet -> khong dau
    rename = {
        "Đầu thô WTI":"Dau tho WTI","Đường":"Duong",
        "Khí thiên nhiên":"Khi thien nhien","Quặng sắt":"Quang sat",
        "Than cốc":"Than coc","Thép HRC":"Thep HRC",
        "Cà phê London":"London Coffee",
    }
    data = data.rename(columns={k:v for k,v in rename.items() if k in data.columns})
    return data

def load_world(raw):
    # Col Z(25)-AG(32), row 0 = header dang "https://... tradingDate"
    sub = raw.iloc[:, 25:33].copy()
    headers = ["Date","DAX","DJI","Gold","NIKKEI225","S&P500","SHANGHAI","VNI"]
    data = sub.iloc[1:].copy()
    data.columns = headers
    data = data[data["Date"].astype(str).str.match(r"\d{4}-\d{2}-\d{2}")]
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    for col in headers[1:]:
        data[col] = _parse_pct(data[col])
    return data

def load_dxy(raw):
    # Col F(5)-J(9), row 0 = header dang "https://... Corect Date"
    sub = raw.iloc[:, 5:10].copy()
    headers = ["Date","DXY","USD/VND (VCB)","USDT","USDC"]
    data = sub.iloc[1:].copy()
    data.columns = headers
    data = data[data["Date"].astype(str).str.match(r"\d{4}-\d{2}-\d{2}")]
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    for col in headers[1:]:
        data[col] = _parse_num(data[col])
    return data

def load_laisuat(raw):
    # Col A(0)-E(4), row 0 = header, data bat dau row 1
    # Nhung col A chua date dang "2024-03-19" xen ke voi nan
    sub = raw.iloc[:, 0:5].copy()
    headers = ["Date","Lai suat FED","Lai suat LNH","TPCP My 5Y","TPCP VN 5Y"]
    data = sub.iloc[1:].copy()
    data.columns = headers
    # Chi lay dong co Date hop le (bo cac dong co Date la nan hoac URL)
    data = data[data["Date"].astype(str).str.match(r"\d{4}-\d{2}-\d{2}")]
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    for col in headers[1:]:
        data[col] = _parse_num(data[col])
    return data

# ── LABEL COLLISION ───────────────────────────────────────────────────────────

def adjust_labels(positions, min_gap):
    if not positions: return []
    srt = sorted(positions, key=lambda x: x[0], reverse=True)
    out = [srt[0]]
    for item in srt[1:]:
        y_prev = out[-1][0]
        y_new  = item[0]
        if y_prev - y_new < min_gap:
            y_new = y_prev - min_gap
        out.append((y_new, item[1], item[2]))
    return out

# ── GENERIC LINE CHART BUILDER ────────────────────────────────────────────────

def build_line_chart(df, selected, date_range, colors, y_title,
                     y_suffix="", y_fmt=".1f", hline=None, height=500):
    mask = (df["Date"] >= pd.Timestamp(date_range[0])) & \
           (df["Date"] <= pd.Timestamp(date_range[1]))
    df_plot = df[mask].copy()
    if df_plot.empty:
        return go.Figure()

    series_cols = [c for c in df.columns if c != "Date"]
    fig = go.Figure()

    # Collect label positions
    label_positions = []
    for col in series_cols:
        if col not in selected or col not in df_plot.columns:
            continue
        s = df_plot[col].dropna()
        if s.empty: continue
        last_val = s.iloc[-1]
        color = colors.get(col, "#666")
        label_positions.append((last_val, col, color))

    if len(label_positions) > 1:
        all_y   = [p[0] for p in label_positions]
        y_range = max(all_y) - min(all_y)
        min_gap = max(y_range * 0.04, abs(max(all_y)) * 0.015)
    else:
        min_gap = 0.1

    adjusted  = adjust_labels(label_positions, min_gap=min_gap)
    label_map = {item[1]: (item[0], item[2]) for item in adjusted}

    for col in series_cols:
        if col not in selected or col not in df_plot.columns:
            continue
        series_data = df_plot[["Date", col]].dropna(subset=[col])
        if series_data.empty: continue

        color    = colors.get(col, "#666")
        last_date = series_data["Date"].iloc[-1]
        last_val  = series_data[col].iloc[-1]
        label_y, _ = label_map.get(col, (last_val, color))

        hover_fmt = "%{y:" + y_fmt + "}" + y_suffix
        fig.add_trace(go.Scatter(
            x=series_data["Date"], y=series_data[col],
            mode="lines", name=col,
            line=dict(color=color, width=1.8),
            showlegend=False,
            hovertemplate="<b>" + col + "</b><br>%{x|%d/%m/%Y}: " + hover_fmt + "<extra></extra>",
        ))

        # Dau cham cuoi line
        fig.add_trace(go.Scatter(
            x=[last_date], y=[last_val], mode="markers",
            marker=dict(color=color, size=6, line=dict(color="white", width=1)),
            showlegend=False, hoverinfo="skip",
        ))

        # Label sat dau cham
        label_text = ("<b>" + col + "</b>: "
                      + ("{:" + y_fmt + "}").format(last_val) + y_suffix)
        fig.add_annotation(
            x=last_date, y=label_y,
            xref="x", yref="y",
            text=label_text,
            showarrow=True, arrowhead=0, arrowwidth=1,
            arrowcolor=color, ax=10, ay=0,
            xanchor="left",
            font=dict(size=10, color=color),
            bgcolor="rgba(0,0,0,0)", #bgcolor="rgba(255,255,255,0.88)",
            borderpad=2,
        )

    if hline is not None:
        fig.add_hline(y=hline, line_dash="dot", line_color="#bbb",
                      line_width=1,
                      annotation_text="  " + ("{:" + y_fmt + "}").format(hline) + y_suffix,
                      annotation_font=dict(color="#bbb", size=10),
                      annotation_position="left")

    # Tinh x range mo rong de labels khong bi cat
    if not df_plot.empty:
        x_end   = df_plot["Date"].max()
        x_start = df_plot["Date"].min()
        x_pad   = (x_end - x_start) * 0.18
        x_range = [x_start, x_end + x_pad]
    else:
        x_range = None

    fig.update_layout(
        template="plotly_white", height=height,
        margin=dict(l=55, r=30, t=35, b=45),
        hovermode="closest",
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(color="#333"),
        xaxis=dict(showgrid=True, gridcolor="#efefef",
                   tickformat="%m/%Y", linecolor="#ccc",
                   range=x_range),
        yaxis=dict(title=y_title, ticksuffix=y_suffix,
                   showgrid=True, gridcolor="#efefef",
                   zeroline=False, linecolor="#ccc"),
    )
    return fig

# ── CONTROLS HELPER ───────────────────────────────────────────────────────────

def _date_controls(key_prefix, min_date, max_date, default_preset="Toan bo"):
    c1, c2, c3 = st.columns(3)
    with c1:
        preset = st.selectbox("Chon nhanh",
                              ["Toan bo", "6 thang", "1 nam", "2 nam"],
                              index=0, key=key_prefix + "_preset")
    if preset == "6 thang":
        ds = max_date - datetime.timedelta(days=180)
    elif preset == "1 nam":
        ds = max_date - datetime.timedelta(days=365)
    elif preset == "2 nam":
        ds = max_date - datetime.timedelta(days=730)
    else:
        ds = min_date
    with c2:
        start = st.date_input("Tu ngay", value=ds,
                              min_value=min_date, max_value=max_date,
                              key=key_prefix + "_start_" + preset)
    with c3:
        end = st.date_input("Den ngay", value=max_date,
                            min_value=min_date, max_value=max_date,
                            key=key_prefix + "_end")
    return start, end

def _checkboxes(series_cols, colors, key_prefix, df_range):
    st.markdown("**Chon series hien thi:**")
    cols_per_row = 5
    check_cols   = st.columns(cols_per_row)
    selected     = []
    for i, col in enumerate(series_cols):
        has_data = (col in df_range.columns
                    and df_range[col].dropna().shape[0] > 0)
        with check_cols[i % cols_per_row]:
            if st.checkbox(col, value=has_data,
                           disabled=not has_data,
                           key="cb_" + key_prefix + "_" + col):
                selected.append(col)
    return selected

# ── RENDER ────────────────────────────────────────────────────────────────────

def render():
    try:
        with st.spinner("Dang tai du lieu vi mo..."):
            raw = load_vimo_raw()
        df_hh  = load_hanghoa(raw)
        df_wld = load_world(raw)
        df_dxy = load_dxy(raw)
        df_ls  = load_laisuat(raw)
    except Exception as e:
        st.error("Khong tai duoc du lieu: " + str(e))
        return

    # Refresh + last update
    col_h, col_r = st.columns([9, 1])
    with col_h:
        st.caption("Cap nhat: " + df_hh["Date"].max().strftime("%d/%m/%Y")
                   + " | Nguon: data.vimo")
    with col_r:
        if st.button("Refresh", key="macro_refresh"):
            st.cache_data.clear()
            st.rerun()

    st.markdown("---")

    # ── CHART 1: HANG HOA ─────────────────────────────────────────────────────
    st.subheader("1. Hang hoa (quy doi 100%)")
    min1, max1 = df_hh["Date"].min().date(), df_hh["Date"].max().date()
    s1, e1 = _date_controls("hh", min1, max1)
    mask1  = (df_hh["Date"] >= pd.Timestamp(s1)) & (df_hh["Date"] <= pd.Timestamp(e1))
    sel1   = _checkboxes([c for c in df_hh.columns if c != "Date"],
                         COLORS_HANGHOA, "hh", df_hh[mask1])
    if sel1:
        fig1 = build_line_chart(df_hh, sel1, (s1, e1),
                                COLORS_HANGHOA, "Quy doi 100% (%)",
                                y_suffix="%", y_fmt=".1f", hline=100, height=480)
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.warning("Chon it nhat 1 series.")

    st.markdown("---")

    # ── CHART 2: WORLD STOCK INDEX ────────────────────────────────────────────
    st.subheader("2. Chi so chung khoan the gioi (quy doi 100%)")
    min2, max2 = df_wld["Date"].min().date(), df_wld["Date"].max().date()
    s2, e2 = _date_controls("wld", min2, max2)
    mask2  = (df_wld["Date"] >= pd.Timestamp(s2)) & (df_wld["Date"] <= pd.Timestamp(e2))
    sel2   = _checkboxes([c for c in df_wld.columns if c != "Date"],
                         COLORS_WORLD, "wld", df_wld[mask2])
    if sel2:
        fig2 = build_line_chart(df_wld, sel2, (s2, e2),
                                COLORS_WORLD, "Quy doi 100% (%)",
                                y_suffix="%", y_fmt=".1f", hline=100, height=440)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.warning("Chon it nhat 1 series.")

    st.markdown("---")

    # ── CHART 3: DXY & TY GIA ─────────────────────────────────────────────────
    st.subheader("3. Chi so DXY va ty gia USD")
    min3, max3 = df_dxy["Date"].min().date(), df_dxy["Date"].max().date()
    s3, e3 = _date_controls("dxy", min3, max3)
    mask3  = (df_dxy["Date"] >= pd.Timestamp(s3)) & (df_dxy["Date"] <= pd.Timestamp(e3))
    sel3   = _checkboxes([c for c in df_dxy.columns if c != "Date"],
                         COLORS_DXY, "dxy", df_dxy[mask3])
    if sel3:
        # DXY va ty gia co don vi khac nhau -> 2 truc Y
        df3    = df_dxy[mask3].copy()
        fig3   = go.Figure()
        label_pos_dxy, label_pos_rate = [], []
        dxy_series   = [c for c in sel3 if c == "DXY"]
        rate_series  = [c for c in sel3 if c != "DXY"]

        for col in sel3:
            s  = df3[col].dropna()
            if s.empty: continue
            color = COLORS_DXY.get(col, "#666")
            if col == "DXY":
                label_pos_dxy.append((s.iloc[-1], col, color))
            else:
                label_pos_rate.append((s.iloc[-1], col, color))

        def _add_series(fig, col, df3, color, secondary):
            sd = df3[["Date", col]].dropna(subset=[col])
            if sd.empty: return
            fig.add_trace(go.Scatter(
                x=sd["Date"], y=sd[col], mode="lines", name=col,
                line=dict(color=color, width=1.8), showlegend=False,
                hovertemplate="<b>" + col + "</b><br>%{x|%d/%m/%Y}: %{y:,.1f}<extra></extra>",
            ))
            fig.add_trace(go.Scatter(
                x=[sd["Date"].iloc[-1]], y=[sd[col].iloc[-1]], mode="markers",
                marker=dict(color=color, size=6, line=dict(color="white", width=1)),
                showlegend=False, hoverinfo="skip",
            ))

        from plotly.subplots import make_subplots
        fig3 = make_subplots(specs=[[{"secondary_y": True}]])

        # Tinh min_gap
        def _gaps(positions):
            if len(positions) < 2: return 0.5
            vals = [p[0] for p in positions]
            return max((max(vals)-min(vals)) * 0.05, 0.3)

        adj_dxy  = adjust_labels(label_pos_dxy,  _gaps(label_pos_dxy))
        adj_rate = adjust_labels(label_pos_rate, _gaps(label_pos_rate))
        lmap_dxy  = {i[1]: i[0] for i in adj_dxy}
        lmap_rate = {i[1]: i[0] for i in adj_rate}

        x_end   = df3["Date"].max()
        x_start = df3["Date"].min()
        x_pad   = (x_end - x_start) * 0.22

        for col in sel3:
            sd = df3[["Date", col]].dropna(subset=[col])
            if sd.empty: continue
            color = COLORS_DXY.get(col, "#666")
            is_dxy = (col == "DXY")
            fig3.add_trace(go.Scatter(
                x=sd["Date"], y=sd[col], mode="lines", name=col,
                line=dict(color=color, width=1.8), showlegend=False,
                hovertemplate="<b>" + col + "</b><br>%{x|%d/%m/%Y}: %{y:,.1f}<extra></extra>",
            ), secondary_y=is_dxy)
            fig3.add_trace(go.Scatter(
                x=[sd["Date"].iloc[-1]], y=[sd[col].iloc[-1]], mode="markers",
                marker=dict(color=color, size=6, line=dict(color="white", width=1)),
                showlegend=False, hoverinfo="skip",
            ), secondary_y=is_dxy)
            lv = sd[col].iloc[-1]
            ly = lmap_dxy.get(col, lv) if is_dxy else lmap_rate.get(col, lv)
            fig3.add_annotation(
                x=sd["Date"].iloc[-1], y=ly,
                xref="x", yref="y2" if is_dxy else "y",
                text="<b>" + col + "</b>: " + "{:,.1f}".format(lv),
                showarrow=True, arrowhead=0, arrowwidth=1,
                arrowcolor=color, ax=10, ay=0, xanchor="left",
                font=dict(size=10, color=color),
                bgcolor="rgba(0,0,0,0)", borderpad=2,                       #bgcolor="rgba(255,255,255,0.88)", borderpad=2,
            )

        fig3.update_layout(
            template="plotly_white", height=440, hovermode="closest",
            margin=dict(l=55, r=30, t=35, b=45),
            plot_bgcolor="white", paper_bgcolor="white", font=dict(color="#333"),
            xaxis=dict(showgrid=True, gridcolor="#efefef", tickformat="%m/%Y",
                       range=[x_start, x_end + x_pad]),
        )
        fig3.update_yaxes(title_text="Ty gia / USDT / USDC",
                          showgrid=True, gridcolor="#efefef",
                          zeroline=False, secondary_y=False)
        fig3.update_yaxes(title_text="DXY", showgrid=False,
                          zeroline=False, secondary_y=True)
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.warning("Chon it nhat 1 series.")

    st.markdown("---")

    # ── CHART 4: LAI SUAT ─────────────────────────────────────────────────────
    st.subheader("4. Lai suat vi mo")
    min4, max4 = df_ls["Date"].min().date(), df_ls["Date"].max().date()
    s4, e4 = _date_controls("ls", min4, max4)
    mask4  = (df_ls["Date"] >= pd.Timestamp(s4)) & (df_ls["Date"] <= pd.Timestamp(e4))
    sel4   = _checkboxes([c for c in df_ls.columns if c != "Date"],
                         COLORS_LAISUAT, "ls", df_ls[mask4])
    if sel4:
        fig4 = build_line_chart(df_ls, sel4, (s4, e4),
                                COLORS_LAISUAT, "Lai suat (%)",
                                y_suffix="%", y_fmt=".2f", height=420)
        st.plotly_chart(fig4, use_container_width=True)
    else:
        st.warning("Chon it nhat 1 series.")
