"""
macro.py
Bieu do vi mo / hang hoa
Chart 1: Hang hoa (quy doi 100%) - data.vimo O:Y
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import io
import requests

MACRO_SHEET_ID = "1zj3uFY0RwFUKTQNQCkQvPzvXqE3oPQlH7PVJ5VHsxyM"

# ── Mau cho tung series ───────────────────────────────────────────────────────
SERIES_COLORS = {
    "Dau tho WTI":      "#000000",   # xanh duong dam (navy)
    "Duong":            "#ff0000",   # do dam
    "Khi thien nhien":  "#00ff00",   # xanh la dam
    "Nickel":           "#ff00ff",   # hong/magenta
    "Quang sat":        "#00ffff",   # xanh cyan
    "Than coc":         "#34a853",   # xanh la nhat
    "Thep HRC":         "#980000",   # do nau dam (dark red)
    "Copper":           "#ef6c00",   # cam dam
    "London Coffee":    "#563d00",   # nau dam
    "Platinum":         "#9e9e9e",   # xam
}

# ── DATA LOADING ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def load_vimo():
    url = ("https://docs.google.com/spreadsheets/d/" + MACRO_SHEET_ID
           + "/gviz/tq?tqx=out:csv&sheet=data.vimo")
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    df_raw = pd.read_csv(io.StringIO(r.text), header=None)

    # Row 0 = merged header row (lay cot O14 den Y24)
    # Cot O = index 14, Y = index 24
    raw = df_raw.iloc[:, 14:25].copy()

    # Lay ten cot tu row 0: "correctDate", "Dau tho WTI", ...
    # Row 0 col 14 co dang "... correctDate" - lay phan sau dau space cuoi
    header_raw = raw.iloc[0].tolist()
    # Cot 0 la date, lay tu "correctDate"
    col_names = []
    for i, h in enumerate(header_raw):
        if i == 0:
            col_names.append("Date")
        else:
            s = str(h).strip() if pd.notna(h) else ""
            # Bo prefix neu co (vd "!A3:K Dau tho WTI" -> "Dau tho WTI")
            if " " in s and i == 1:
                s = s.split(" ", 1)[1].strip()
            col_names.append(s if s and s != "nan" else f"Col{i}")

    # Data bat dau tu row 1 (bo row 0 la header)
    data = raw.iloc[1:].copy()
    data.columns = col_names
    data = data.reset_index(drop=True)

    # Parse date
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    # Parse % values: "95.2%" -> 95.2 (giu nguyen don vi % de de hien thi)
    for col in col_names[1:]:
        if col in data.columns:
            data[col] = pd.to_numeric(
                data[col].astype(str)
                .str.replace("%", "", regex=False)
                .str.strip(),
                errors="coerce")

    # Doi ten cot cho dep (khop voi SERIES_COLORS)
    rename_map = {}
    for col in data.columns:
        # Normalize: bo dau tieng Viet don gian
        norm = (col
                .replace("Đầu thô WTI", "Dau tho WTI")
                .replace("Đường", "Duong")
                .replace("Khí thiên nhiên", "Khi thien nhien")
                .replace("Quặng sắt", "Quang sat")
                .replace("Than cốc", "Than coc")
                .replace("Thép HRC", "Thep HRC")
                .replace("Cà phê London", "London Coffee")
                )
        if norm != col:
            rename_map[col] = norm
    if rename_map:
        data = data.rename(columns=rename_map)

    return data

# ── LABEL COLLISION AVOIDANCE ─────────────────────────────────────────────────

def adjust_labels(positions, min_gap=2.0):
    """
    positions: list of (y_value, label) sorted by y_value desc
    Tra ve list (y_adjusted, label) da duoc gian cach de tranh chong lan.
    min_gap: khoang cach toi thieu giua 2 label (don vi %)
    """
    if not positions:
        return []

    # Sort theo y giam dan
    sorted_pos = sorted(positions, key=lambda x: x[0], reverse=True)

    adjusted = [sorted_pos[0]]
    for i in range(1, len(sorted_pos)):
        y_prev  = adjusted[-1][0]
        y_curr  = sorted_pos[i][0]
        label   = sorted_pos[i][1]
        color   = sorted_pos[i][2]
        # Neu qua gan, day xuong
        if y_prev - y_curr < min_gap:
            y_curr = y_prev - min_gap
        adjusted.append((y_curr, label, color))

    return adjusted

# ── BUILD CHART ───────────────────────────────────────────────────────────────

def build_hanghoa_chart(df, selected_series, date_range):
    """
    df: DataFrame voi cot Date + cac series
    selected_series: list ten series duoc chon hien thi
    date_range: (start_date, end_date)
    """
    # Filter theo date
    mask = (df["Date"] >= pd.Timestamp(date_range[0])) & \
           (df["Date"] <= pd.Timestamp(date_range[1]))
    df_plot = df[mask].copy()

    if df_plot.empty:
        return go.Figure()

    fig = go.Figure()

    # Lay tat ca series co du lieu
    series_cols = [c for c in df.columns if c != "Date"]

    # --- Tinh min_gap tu dong theo so luong series va range Y ---
    label_positions = []
    for col in series_cols:
        if col not in selected_series:
            continue
        if col not in df_plot.columns:
            continue
        series_data = df_plot[col].dropna()
        if series_data.empty:
            continue
        last_val = series_data.iloc[-1]
        color    = SERIES_COLORS.get(col, "#aaa")
        label_positions.append((last_val, col, color))

    # Tinh min_gap tu dong
    if len(label_positions) > 1:
        all_y   = [p[0] for p in label_positions]
        y_range = max(all_y) - min(all_y)
        min_gap = max(2.5, y_range / len(label_positions) * 0.6)
    else:
        min_gap = 1.5

    # Adjust label positions
    adjusted = adjust_labels(label_positions, min_gap=min_gap)
    label_map = {item[1]: (item[0], item[2]) for item in adjusted}

    # --- Ve tung series ---
    for col in series_cols:
        if col not in selected_series:
            continue
        if col not in df_plot.columns:
            continue

        series_data = df_plot[["Date", col]].dropna(subset=[col])
        if series_data.empty:
            continue

        color     = SERIES_COLORS.get(col, "#aaa")
        last_date = series_data["Date"].iloc[-1]
        last_val  = series_data[col].iloc[-1]
        label_y, _ = label_map.get(col, (last_val, color))

        fig.add_trace(go.Scatter(
            x=series_data["Date"],
            y=series_data[col],
            mode="lines",
            name=col,
            line=dict(color=color, width=1.8),
            hovertemplate=(
                "<b>" + col + "</b><br>"
                "%{x|%d/%m/%Y}<br>"
                "%{y:.1f}%<extra></extra>"),
            showlegend=False,   # Tat legend mac dinh, dung end-label thay the
        ))

        # End-of-line label (dat o ben phai vung chart)
        # Dung annotation voi xref="paper" cho truc x de dat ngoai chart
        fig.add_annotation(
            x=1.01,               # Ngoai vung chart (paper coords)
            y=label_y,
            xref="paper",
            yref="y",
            text="<b>" + col + "</b>: " + "{:.1f}%".format(last_val),
            showarrow=True,
            arrowhead=0,
            arrowwidth=1,
            arrowcolor=color,
            ax=5,
            ay=0,
            xanchor="left",
            font=dict(size=10, color=color),
            bgcolor="rgba(255,255,255,0.9)",
            borderpad=2,
        )

        # Dau cham tai diem cuoi cua line
        fig.add_trace(go.Scatter(
            x=[last_date],
            y=[last_val],
            mode="markers",
            marker=dict(color=color, size=5),
            showlegend=False,
            hoverinfo="skip",
        ))

    # --- Layout ---
    fig.update_layout(
        template="plotly_white",
        height=560,
        margin=dict(l=50, r=290, t=40, b=50),  # r rong de cho labels
        xaxis=dict(
            title="",
            showgrid=True,
            gridcolor="#e8e8e8",
            tickformat="%m/%Y",
            linecolor="#ccc",
        ),
        yaxis=dict(
            title="Quy doi 100% (%)",
            ticksuffix="%",
            showgrid=True,
            gridcolor="#e8e8e8",
            zeroline=False,
            linecolor="#ccc",
        ),
        hovermode="closest",
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color="#333"),
    )

    # Them duong 100% lam moc tham chieu
    fig.add_hline(
        y=100, line_dash="dot",
        line_color="#999", line_width=1.2,
        annotation_text="  100%",
        annotation_font=dict(color="#999", size=10),
        annotation_position="left",
    )

    return fig

# ── MAIN RENDER ───────────────────────────────────────────────────────────────

def render():
    # Load data
    try:
        with st.spinner("Dang tai du lieu hang hoa..."):
            df = load_vimo()
    except Exception as e:
        st.error("Khong tai duoc du lieu: " + str(e))
        return

    series_cols = [c for c in df.columns if c != "Date"]

    # ── Header + Refresh ──
    col_title, col_refresh = st.columns([9, 1])
    with col_title:
        st.subheader("Hang hoa (quy doi 100%)")
        st.caption("Nguon: data.vimo | Cap nhat: "
                   + df["Date"].max().strftime("%d/%m/%Y"))
    with col_refresh:
        st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
        if st.button("Refresh", key="macro_refresh"):
            st.cache_data.clear()
            st.rerun()

    # ── Date range slider ──
    min_date = df["Date"].min().date()
    max_date = df["Date"].max().date()

    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        preset = st.selectbox("Chon nhanh",
                              ["Toan bo", "6 thang", "1 nam", "2 nam"],
                              key="macro_preset")
    with col_d2:
        start_date = st.date_input("Tu ngay", value=min_date,
                                   min_value=min_date, max_value=max_date,
                                   key="macro_start")
    with col_d3:
        end_date = st.date_input("Den ngay", value=max_date,
                                 min_value=min_date, max_value=max_date,
                                 key="macro_end")

    # Ap dung preset
    import datetime
    if preset == "6 thang":
        start_date = (max_date - datetime.timedelta(days=180))
    elif preset == "1 nam":
        start_date = (max_date - datetime.timedelta(days=365))
    elif preset == "2 nam":
        start_date = (max_date - datetime.timedelta(days=730))
    elif preset == "Toan bo":
        start_date = min_date

    # ── Checkbox chon series ──
    st.markdown("**Chon series hien thi:**")

    # Tinh so series co du lieu trong khoang date da chon
    mask = (df["Date"] >= pd.Timestamp(start_date)) & \
           (df["Date"] <= pd.Timestamp(end_date))
    df_range = df[mask]

    # Hien thi checkbox theo hang ngang
    cols_per_row = 5
    check_cols   = st.columns(cols_per_row)
    selected     = []

    for i, col_name in enumerate(series_cols):
        has_data = (col_name in df_range.columns
                    and df_range[col_name].dropna().shape[0] > 0)
        color    = SERIES_COLORS.get(col_name, "#aaa")

        with check_cols[i % cols_per_row]:
            # Hien thi checkbox voi ten co mau
            checked = st.checkbox(
                col_name,
                value=has_data,       # Mac dinh tick neu co data
                disabled=not has_data,
                key="cb_hanghoa_" + col_name,
            )
            if checked:
                selected.append(col_name)

    if not selected:
        st.warning("Hay chon it nhat 1 series de hien thi.")
        return

    # ── Ve chart ──
    fig = build_hanghoa_chart(df, selected, (start_date, end_date))
    st.plotly_chart(fig, use_container_width=True)

    # ── Bang so lieu cuoi cung ──
    with st.expander("Xem bang so lieu (gia tri cuoi cung)"):
        last_row = df[mask].dropna(how="all", subset=series_cols).iloc[-1:]
        if not last_row.empty:
            display = last_row[["Date"] + [c for c in series_cols if c in last_row.columns]].copy()
            display["Date"] = display["Date"].dt.strftime("%d/%m/%Y")
            for col in series_cols:
                if col in display.columns:
                    display[col] = display[col].apply(
                        lambda v: "{:.1f}%".format(v) if pd.notna(v) else "-")
            st.dataframe(display, use_container_width=True, hide_index=True)
