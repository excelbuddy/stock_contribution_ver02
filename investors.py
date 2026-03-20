"""
investors.py
Thong ke mua ban cong don theo nhom nha dau tu
Nguon: statistic_investors sheet
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io, requests

INV_SHEET_ID = "1uezTWoFORPtfVZOR4_5GRtWDtSWUexvo7-mdSK59WM0"

# ── Config ────────────────────────────────────────────────────────────────────
GROUPS = {
    "Nuoc ngoai": {"col": "NN cd",  "color": "#e53935", "dash": "solid"},
    "Tu doanh":   {"col": "TD cd",  "color": "#1e88e5", "dash": "solid"},
    "To chuc":    {"col": "TC cd",  "color": "#43a047", "dash": "solid"},
    "Ca nhan":    {"col": "CN cd",  "color": "#fb8c00", "dash": "solid"},
}
VNI_COLOR   = "#7b1fa2"
UNIT        = "ty dong"   # don vi hien thi

# ── Data ──────────────────────────────────────────────────────────────────────

def _parse_num(series):
    """Chuyen (307) -> -307, 1,245 -> 1245"""
    def _conv(v):
        if pd.isna(v): return np.nan
        s = str(v).strip().replace(",", "").replace(" ", "")
        if s.startswith("(") and s.endswith(")"):
            try: return -float(s[1:-1])
            except: return np.nan
        try: return float(s)
        except: return np.nan
    return series.apply(_conv)

@st.cache_data(ttl=600, show_spinner=False)
def load_investors():
    url = ("https://docs.google.com/spreadsheets/d/" + INV_SHEET_ID
           + "/gviz/tq?tqx=out:csv&sheet=statistic_investors")
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    raw = pd.read_csv(io.StringIO(r.text), header=0)   # row 0 la header

    # Lay dung 5 cot can thiet
    col_map = {
        raw.columns[0]:  "Date",
        raw.columns[35]: "NN cd",
        raw.columns[36]: "TD cd",
        raw.columns[37]: "TC cd",
        raw.columns[38]: "CN cd",
        raw.columns[39]: "VNI",
    }
    df = raw.iloc[:, [0, 35, 36, 37, 38, 39]].copy()
    df.columns = ["Date", "NN cd", "TD cd", "TC cd", "CN cd", "VNI"]

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    for col in ["NN cd", "TD cd", "TC cd", "CN cd", "VNI"]:
        df[col] = _parse_num(df[col])

    df["Year"] = df["Date"].dt.year
    return df

# ── Label collision avoidance ─────────────────────────────────────────────────

def _adjust_labels(positions, min_gap=8):
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

# ── Build chart ───────────────────────────────────────────────────────────────

def _fmt_val(v):
    """Format gia tri: 25,977 ty"""
    if pd.isna(v): return ""
    abs_v = abs(v)
    if abs_v >= 1000:
        return "{:+,.0f}".format(v)
    return "{:+,.0f}".format(v)

def build_chart(df, selected_groups, date_range, show_vni):
    mask = (df["Date"] >= pd.Timestamp(date_range[0])) & \
           (df["Date"] <= pd.Timestamp(date_range[1]))
    df_plot = df[mask].copy()
    if df_plot.empty:
        return go.Figure()

    years = sorted(df_plot["Year"].unique())

    # 2 truc Y: trai = gia tri cd (ty dong), phai = VNIndex
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # ── VNI line (lien mach, truc phai) ──────────────────────────────────────
    if show_vni:
        vni_data = df_plot[["Date", "VNI"]].dropna(subset=["VNI"])
        fig.add_trace(go.Scatter(
            x=vni_data["Date"], y=vni_data["VNI"],
            name="VNIndex",
            mode="lines",
            line=dict(color=VNI_COLOR, width=1.5, dash="dot"),
            hovertemplate="<b>VNIndex</b><br>%{x|%d/%m/%Y}: %{y:,.0f}<extra></extra>",
            showlegend=False,
        ), secondary_y=True)

        # End label VNI
        last_vni = vni_data["VNI"].iloc[-1]
        last_date_vni = vni_data["Date"].iloc[-1]
        fig.add_trace(go.Scatter(
            x=[last_date_vni], y=[last_vni],
            mode="markers", marker=dict(color=VNI_COLOR, size=7),
            showlegend=False, hoverinfo="skip",
        ), secondary_y=True)
        fig.add_annotation(
            x=1.01, y=last_vni, xref="paper", yref="y2",
            text="<b>VNIndex</b>: {:,.0f}".format(last_vni),
            showarrow=True, arrowhead=0, arrowwidth=1,
            arrowcolor=VNI_COLOR, ax=5, ay=0,
            xanchor="left", font=dict(size=10, color=VNI_COLOR),
            bgcolor="rgba(255,255,255,0.9)", borderpad=2,
        )

    # ── Cumulative lines theo tung nam (truc trai) ────────────────────────────
    label_positions = []   # (last_val, name, color) de tinh collision

    for grp_name, cfg in GROUPS.items():
        if grp_name not in selected_groups:
            continue
        col   = cfg["col"]
        color = cfg["color"]

        for yr in years:
            yr_data = df_plot[df_plot["Year"] == yr][["Date", col]].dropna(subset=[col])
            if yr_data.empty:
                continue

            is_last_year = bool(yr == years[-1])
            show_leg     = bool(yr == years[0])   # chi hien legend 1 lan

            fig.add_trace(go.Scatter(
                x=yr_data["Date"],
                y=yr_data[col],
                name=grp_name,
                legendgroup=grp_name,
                mode="lines",
                line=dict(color=color, width=2, dash=cfg["dash"]),
                hovertemplate=(
                    "<b>" + grp_name + " " + str(yr) + "</b><br>"
                    "%{x|%d/%m/%Y}: %{y:+,.0f} ty<extra></extra>"),
                showlegend=show_leg,
                connectgaps=False,
            ), secondary_y=False)

            # Dau cham + label chi o cuoi nam hien tai (line cuoi)
            if is_last_year:
                last_v    = yr_data[col].iloc[-1]
                last_date = yr_data["Date"].iloc[-1]
                fig.add_trace(go.Scatter(
                    x=[last_date], y=[last_v],
                    mode="markers",
                    marker=dict(color=color, size=8, line=dict(color="white", width=1.5)),
                    showlegend=False, hoverinfo="skip",
                ), secondary_y=False)
                label_positions.append((last_v, grp_name, color))

            # Dau cham nho tai diem cuoi moi nam (tru nam cuoi)
            elif len(yr_data) > 0:
                last_v    = yr_data[col].iloc[-1]
                last_date = yr_data["Date"].iloc[-1]
                fig.add_trace(go.Scatter(
                    x=[last_date], y=[last_v],
                    mode="markers",
                    marker=dict(color=color, size=5, opacity=0.7),
                    showlegend=False, hoverinfo="skip",
                ), secondary_y=False)

            # Annotation nam ben trong chart (dau nam, giua chart)
            if len(yr_data) >= 5:
                mid_idx  = len(yr_data) // 2
                mid_date = yr_data["Date"].iloc[mid_idx]
                mid_val  = yr_data[col].iloc[mid_idx]
                fig.add_annotation(
                    x=mid_date, y=mid_val,
                    text=str(yr),
                    showarrow=False,
                    font=dict(size=9, color=color),
                    opacity=0.5,
                    yshift=10,
                )

    # ── End-of-line labels (collision avoidance) ──────────────────────────────
    all_vals    = [p[0] for p in label_positions]
    if len(all_vals) > 1:
        val_range = max(all_vals) - min(all_vals)
        min_gap   = max(8, val_range / len(all_vals) * 0.55)
    else:
        min_gap = 8

    adjusted = _adjust_labels(label_positions, min_gap=min_gap)
    for (adj_y, grp_name, color) in adjusted:
        real_y = next((p[0] for p in label_positions if p[1] == grp_name), adj_y)
        fig.add_annotation(
            x=1.01, y=adj_y, xref="paper", yref="y",
            text="<b>" + grp_name + "</b>: " + _fmt_val(real_y) + " ty",
            showarrow=True, arrowhead=0, arrowwidth=1,
            arrowcolor=color, ax=5, ay=0,
            xanchor="left",
            font=dict(size=10, color=color),
            bgcolor="rgba(255,255,255,0.92)",
            borderpad=2,
        )

    # ── Duong 0 tham chieu ────────────────────────────────────────────────────
    fig.add_hline(y=0, line_dash="dot", line_color="#aaa",
                  line_width=1, secondary_y=False)

    # ── Phan cach nam bang duong doc ──────────────────────────────────────────
    for yr in years[1:]:
        yr_start = df_plot[df_plot["Year"] == yr]["Date"].min()
        if pd.notna(yr_start):
            fig.add_vline(
                x=yr_start.timestamp() * 1000,
                line_dash="dot", line_color="#ddd", line_width=1,
            )
            fig.add_annotation(
                x=yr_start, y=1.01, xref="x", yref="paper",
                text=str(yr), showarrow=False,
                font=dict(size=10, color="#aaa"),
                xanchor="center",
            )

    # ── Layout ────────────────────────────────────────────────────────────────
    fig.update_layout(
        template="plotly_white",
        height=580,
        margin=dict(l=60, r=260, t=50, b=50),
        hovermode="closest",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="left", x=0, font=dict(size=11),
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color="#333"),
    )
    fig.update_xaxes(
        showgrid=True, gridcolor="#f0f0f0",
        tickformat="%m/%Y", linecolor="#ccc",
    )
    fig.update_yaxes(
        title_text="Gia tri cong don (ty dong)",
        showgrid=True, gridcolor="#f0f0f0",
        zeroline=False, linecolor="#ccc",
        tickformat=",",
        secondary_y=False,
    )
    fig.update_yaxes(
        title_text="VNIndex",
        showgrid=False,
        tickformat=",",
        linecolor=VNI_COLOR,
        title_font=dict(color=VNI_COLOR),
        tickfont=dict(color=VNI_COLOR),
        secondary_y=True,
    )

    return fig

# ── Render ────────────────────────────────────────────────────────────────────

def render():
    try:
        with st.spinner("Dang tai du lieu..."):
            df = load_investors()
    except Exception as e:
        st.error("Khong tai duoc du lieu: " + str(e))
        return

    min_date = df["Date"].min().date()
    max_date = df["Date"].max().date()

    # ── Header ────────────────────────────────────────────────────────────────
    col_h, col_r = st.columns([9, 1])
    with col_h:
        st.subheader("Thong ke mua ban cong don theo nhom nha dau tu")
        st.caption("Nguon: statistic_investors | Cap nhat: "
                   + df["Date"].max().strftime("%d/%m/%Y")
                   + " | Don vi: ty dong")
    with col_r:
        st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)
        if st.button("Refresh", key="inv_refresh"):
            st.cache_data.clear()
            st.rerun()

    # ── KPI row ───────────────────────────────────────────────────────────────
    last = df.iloc[-1]
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("VNIndex",      "{:,.0f}".format(last["VNI"]))
    k2.metric("Nuoc ngoai",   "{:+,.0f} ty".format(last["NN cd"]),
              delta="CD tu dau nam")
    k3.metric("Tu doanh",     "{:+,.0f} ty".format(last["TD cd"]))
    k4.metric("To chuc",      "{:+,.0f} ty".format(last["TC cd"]))
    k5.metric("Ca nhan",      "{:+,.0f} ty".format(last["CN cd"]))

    st.markdown("---")

    # ── Controls ──────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    import datetime
    with c1:
        preset = st.selectbox("Chon nhanh",
                              ["Toan bo", "Nam nay", "1 nam", "6 thang"],
                              key="inv_preset")
    with c2:
        if preset == "Nam nay":
            default_start = datetime.date(max_date.year, 1, 1)
        elif preset == "1 nam":
            default_start = max_date - datetime.timedelta(days=365)
        elif preset == "6 thang":
            default_start = max_date - datetime.timedelta(days=180)
        else:
            default_start = min_date
        start_date = st.date_input("Tu ngay", value=default_start,
                                   min_value=min_date, max_value=max_date,
                                   key="inv_start")
    with c3:
        end_date = st.date_input("Den ngay", value=max_date,
                                 min_value=min_date, max_value=max_date,
                                 key="inv_end")

    # ── Checkbox chon nhom ────────────────────────────────────────────────────
    st.markdown("**Chon nhom hien thi:**")
    cb_cols = st.columns(5)
    selected = []
    for i, (grp, cfg) in enumerate(GROUPS.items()):
        with cb_cols[i]:
            color = cfg["color"]
            checked = st.checkbox(grp, value=True, key="inv_cb_" + grp)
            if checked:
                selected.append(grp)

    with cb_cols[4]:
        show_vni = st.checkbox("VNIndex", value=True, key="inv_cb_vni")

    if not selected and not show_vni:
        st.warning("Hay chon it nhat 1 nhom.")
        return

    # ── Chart ─────────────────────────────────────────────────────────────────
    fig = build_chart(df, selected, (start_date, end_date), show_vni)
    st.plotly_chart(fig, use_container_width=True)

    # ── Bang so lieu ──────────────────────────────────────────────────────────
    with st.expander("Xem bang so lieu (20 phien gan nhat)"):
        mask = (df["Date"] >= pd.Timestamp(start_date)) & \
               (df["Date"] <= pd.Timestamp(end_date))
        df_show = df[mask].tail(20).copy()
        df_show["Date"] = df_show["Date"].dt.strftime("%d/%m/%Y")
        for col in ["NN cd", "TD cd", "TC cd", "CN cd"]:
            df_show[col] = df_show[col].apply(
                lambda v: "{:+,.0f}".format(v) if pd.notna(v) else "-")
        df_show["VNI"] = df_show["VNI"].apply(
            lambda v: "{:,.0f}".format(v) if pd.notna(v) else "-")
        df_show = df_show.drop(columns=["Year"])
        df_show.columns = ["Ngay", "Nuoc ngoai", "Tu doanh",
                           "To chuc", "Ca nhan", "VNIndex"]
        st.dataframe(df_show, use_container_width=True, hide_index=True)
