"""
stockprice.py
Chuc nang: Hien thi bang gia so sanh co phieu voi gia tri chot loi
Sheet: TSCP - Google Sheet ID: 1RfJmy3A4Ej_V-J-44eNYog1aop0vj4RvetAA3yFJXIo

Cau truc du lieu:
  Bang 1 (D2:P~): Danh muc | CP | Gia ngung | Gia chot | Co tuc DK |
                  Ty suat/Gia ngung | YM | MP | Profit->ngung | Profit->chot | Co tuc/MP
  Bang 2 (R2:T~): CP | Profit | Co tuc  (sort by Co tuc desc)
  Bang 3 (V2:X~): CP | Profit | Co tuc  (sort by Profit desc)

Logic mau:
  Bang 1: do neu MP >= Gia ngung (da vuot nguong ban)
  Bang 2: do neu Profit (col S) < 0
  Bang 3: khong co quy tac mau dac biet

Tab bo sung:
  Tab 3: Scatter chart Profit vs Co tuc
  Tab 4: Summary metrics & top picks
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import io
import requests

TSCP_SHEET_ID = "1RfJmy3A4Ej_V-J-44eNYog1aop0vj4RvetAA3yFJXIo"

# ── DATA LOADING ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)  # cache 5 phut vi gia MP thay doi lien tuc
def load_tscp():
    url = ("https://docs.google.com/spreadsheets/d/" + TSCP_SHEET_ID
           + "/gviz/tq?tqx=out:csv&sheet=TSCP")
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    # Doc khong co header de xu ly thu cong
    df = pd.read_csv(io.StringIO(r.text), header=None)
    return df

def parse_tscp(df_raw):
    """
    Mapping cot theo vi tri (0-indexed):
    Col index: A=0 B=1 C=2 D=3 E=4 F=5 G=6 H=7 I=8 J=9 K=10 L=11 M=12 N=13 O=14 P=15
               Q=16 R=17 S=18 T=19 U=20 V=21 W=22 X=23

    Row 1 (index 1) = header
    Row 2+ (index 2+) = data
    """
    # ── Bang 1: cols D(3) E(4) H(7) I(8) J(9) K(10) M(12) N(13) O(14) P(15) ──
    # Bo qua cot an: B(1) C(2) F(5) G(6) L(11)
    data_rows = df_raw.iloc[2:].copy()  # tu row index 2 tro di (bo header row 1)
    data_rows = data_rows.reset_index(drop=True)

    def to_num(series):
        return pd.to_numeric(
            series.astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("%", "", regex=False)
            .str.strip(),
            errors="coerce")

    def to_pct(series):
        # Xu ly ca dang "2.9%" lan dang 0.029 (float)
        s = series.copy()
        result = []
        for v in s:
            if pd.isna(v) or str(v).strip() in ("", "nan"):
                result.append(np.nan)
                continue
            sv = str(v).strip()
            if "%" in sv:
                try:
                    result.append(float(sv.replace("%","").replace(",","")) / 100)
                except:
                    result.append(np.nan)
            else:
                try:
                    f = float(sv.replace(",",""))
                    # Neu gia tri > 1 thi co the la % dang 29.0 chu khong phai 0.29
                    result.append(f if abs(f) <= 1.0 else f / 100)
                except:
                    result.append(np.nan)
        return pd.Series(result, index=series.index)

    b1 = pd.DataFrame()
    b1["Danh muc"]         = data_rows.iloc[:, 3].astype(str).str.strip()
    b1["CP"]               = data_rows.iloc[:, 4].astype(str).str.strip()
    b1["Gia ngung"]        = to_num(data_rows.iloc[:, 7])
    b1["Gia chot"]         = to_num(data_rows.iloc[:, 8])
    b1["Co tuc DK"]        = to_num(data_rows.iloc[:, 9])
    b1["Ty suat/Gia ngung"]= to_pct(data_rows.iloc[:, 10])
    b1["MP"]               = to_num(data_rows.iloc[:, 12])
    b1["Profit->Ngung"]    = to_pct(data_rows.iloc[:, 13])
    b1["Profit->Chot"]     = to_pct(data_rows.iloc[:, 14])
    b1["Co tuc/MP"]        = to_pct(data_rows.iloc[:, 15])

    # Loc bo dong trong (CP rong hoac nan)
    b1 = b1[b1["CP"].notna() & (b1["CP"] != "") & (b1["CP"] != "nan")]
    b1 = b1[b1["Gia ngung"].notna()]
    b1 = b1.reset_index(drop=True)

    # Flag: MP >= Gia ngung -> to do
    b1["Alert"] = b1.apply(
        lambda r: (pd.notna(r["MP"]) and pd.notna(r["Gia ngung"])
                   and r["MP"] >= r["Gia ngung"]),
        axis=1)

    # ── Bang 2: cols R(17) S(18) T(19) ──
    b2_rows = df_raw.iloc[2:22].copy().reset_index(drop=True)
    b2 = pd.DataFrame()
    b2["CP"]     = b2_rows.iloc[:, 17].astype(str).str.strip()
    b2["Profit"] = to_pct(b2_rows.iloc[:, 18])
    b2["Co tuc"] = to_pct(b2_rows.iloc[:, 19])
    b2 = b2[b2["CP"].notna() & (b2["CP"] != "") & (b2["CP"] != "nan") & (b2["CP"] != "CP")]
    b2["Alert"] = b2["Profit"] < 0

    # ── Bang 3: cols V(21) W(22) X(23) ──
    b3_rows = df_raw.iloc[2:22].copy().reset_index(drop=True)
    b3 = pd.DataFrame()
    b3["CP"]     = b3_rows.iloc[:, 21].astype(str).str.strip()
    b3["Profit"] = to_pct(b3_rows.iloc[:, 22])
    b3["Co tuc"] = to_pct(b3_rows.iloc[:, 23])
    b3 = b3[b3["CP"].notna() & (b3["CP"] != "") & (b3["CP"] != "nan") & (b3["CP"] != "CP")]

    return b1, b2, b3

# ── HTML TABLE BUILDER ────────────────────────────────────────────────────────

def _fmt_pct(v):
    if pd.isna(v): return ""
    return "{:+.1f}%".format(v * 100)

def _fmt_num(v, decimals=1):
    if pd.isna(v): return ""
    return "{:,.{}f}".format(v, decimals)

def _fmt_cotuc(v):
    if pd.isna(v) or v == 0: return ""
    return "{:,.0f}".format(v)

# ── TAB 1: Bang chinh ─────────────────────────────────────────────────────────

def render_tab1(b1):
    st.subheader("Bang gia thi truong vs Gia tri chot loi")

    # ── Summary KPIs ──
    total   = len(b1)
    alert_n = b1["Alert"].sum()
    safe_n  = total - alert_n
    avg_p   = b1["Profit->Chot"].mean()
    max_p   = b1["Profit->Chot"].max()

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Tong CP", str(total))
    k2.metric("Da vuot nguong (do)", str(alert_n),
              delta=None if alert_n == 0 else "⚠ Can xem lai")
    k3.metric("An toan", str(safe_n))
    k4.metric("Profit TB->Chot", "{:+.1f}%".format(avg_p * 100) if pd.notna(avg_p) else "-")
    k5.metric("Profit max->Chot", "{:+.1f}%".format(max_p * 100) if pd.notna(max_p) else "-")

    st.markdown("---")

    # ── Filter ──
    cf1, cf2, cf3 = st.columns([2, 2, 3])
    with cf1:
        dm_options = ["Tat ca"] + sorted(b1["Danh muc"].dropna().unique().tolist())
        dm_filter  = st.selectbox("Danh muc", dm_options)
    with cf2:
        alert_filter = st.selectbox("Trang thai", ["Tat ca", "Da vuot nguong (do)", "An toan"])
    with cf3:
        sort_col = st.selectbox("Sap xep theo",
                                ["Danh muc", "CP", "Profit->Chot", "Profit->Ngung",
                                 "Co tuc/MP", "MP"])

    df = b1.copy()
    if dm_filter != "Tat ca":
        df = df[df["Danh muc"] == dm_filter]
    if alert_filter == "Da vuot nguong (do)":
        df = df[df["Alert"] == True]
    elif alert_filter == "An toan":
        df = df[df["Alert"] == False]

    asc = sort_col in ["Danh muc", "CP"]
    df = df.sort_values(sort_col, ascending=asc, na_position="last")

    # ── Build HTML table ──
    cols_display = ["Danh muc", "CP", "Gia ngung", "Gia chot", "Co tuc DK",
                    "Ty suat/Gia ngung", "MP", "Profit->Ngung", "Profit->Chot", "Co tuc/MP"]
    headers = ["Danh muc", "CP", "Gia ngung", "Gia chot", "Co tuc DK",
               "Ty suat", "MP (TT)", "Profit->Ngung", "Profit->Chot", "Co tuc/MP"]

    p = []
    p.append('<div style="overflow-x:auto;">')
    p.append('<table style="width:100%;border-collapse:collapse;font-size:13px;">')

    # Header
    p.append('<thead><tr style="background:#1a1d2e;">')
    for h in headers:
        p.append('<th style="color:#90caf9;padding:6px 8px;text-align:center;'
                 'font-size:11px;font-weight:600;border-bottom:1px solid #333;">'
                 + h + '</th>')
    p.append('</tr></thead><tbody>')

    for i, (_, row) in enumerate(df.iterrows()):
        is_alert = row["Alert"]
        row_bg   = "#4a0a0a" if is_alert else ("#1e2130" if i % 2 == 0 else "#16192b")
        dm_color = "#ff5252" if is_alert else ("#ffb300" if row["Danh muc"] == "TAN CONG"
                   else "#64b5f6" if row["Danh muc"] == "CAN BANG"
                   else "#aaa")

        # Mau profit
        def pcolor(v):
            if pd.isna(v): return "#aaa"
            return "#00e676" if v > 0 else "#ff5252"

        mp_color = "#ff5252" if is_alert else "white"

        p.append('<tr style="background:' + row_bg + ';">')
        p.append('<td style="padding:5px 8px;color:' + dm_color + ';font-size:11px;">'
                 + str(row["Danh muc"]) + '</td>')
        p.append('<td style="padding:5px 8px;font-weight:700;color:'
                 + ("#ff5252" if is_alert else "#4fc3f7") + ';text-align:center;">'
                 + str(row["CP"]) + '</td>')
        p.append('<td style="padding:5px 8px;text-align:right;color:#e0e0e0;">'
                 + _fmt_num(row["Gia ngung"]) + '</td>')
        p.append('<td style="padding:5px 8px;text-align:right;color:#e0e0e0;">'
                 + _fmt_num(row["Gia chot"]) + '</td>')
        p.append('<td style="padding:5px 8px;text-align:right;color:#aaa;">'
                 + _fmt_cotuc(row["Co tuc DK"]) + '</td>')
        p.append('<td style="padding:5px 8px;text-align:right;color:#aaa;">'
                 + _fmt_pct(row["Ty suat/Gia ngung"]) + '</td>')
        p.append('<td style="padding:5px 8px;text-align:right;font-weight:700;color:'
                 + mp_color + ';">' + _fmt_num(row["MP"]) + '</td>')
        p.append('<td style="padding:5px 8px;text-align:right;color:'
                 + pcolor(row["Profit->Ngung"]) + ';">'
                 + _fmt_pct(row["Profit->Ngung"]) + '</td>')
        p.append('<td style="padding:5px 8px;text-align:right;font-weight:600;color:'
                 + pcolor(row["Profit->Chot"]) + ';">'
                 + _fmt_pct(row["Profit->Chot"]) + '</td>')
        p.append('<td style="padding:5px 8px;text-align:right;color:#aaa;">'
                 + _fmt_pct(row["Co tuc/MP"]) + '</td>')
        p.append('</tr>')

    p.append('</tbody></table></div>')
    st.markdown("".join(p), unsafe_allow_html=True)

    if alert_n > 0:
        alert_list = ", ".join(b1[b1["Alert"]]["CP"].tolist())
        st.warning("Danh sách CP đã vượt giá ngừng Tích sản: " + alert_list)

# ── TAB 2: Bang 2 & 3 ────────────────────────────────────────────────────────

def _render_small_table(df, title, alert_col, alert_condition, sort_note):
    p = []
    p.append('<div style="background:#12151f;border-radius:8px;overflow:hidden;'
             'margin-bottom:8px;">')
    p.append('<div style="background:#1a2744;padding:8px 12px;">')
    p.append('<span style="font-weight:700;color:#90caf9;font-size:13px;">'
             + title + '</span>')
    p.append('<span style="color:#666;font-size:11px;margin-left:8px;">'
             + sort_note + '</span>')
    p.append('</div>')
    p.append('<table style="width:100%;border-collapse:collapse;font-size:12px;">')
    p.append('<thead><tr style="background:#1a1d2e;">')
    for h in ["CP", "Profit->Chot", "Co tuc/MP"]:
        p.append('<th style="color:#90caf9;padding:5px 10px;font-size:11px;'
                 'font-weight:600;text-align:' + ("left" if h == "CP" else "right") + ';">'
                 + h + '</th>')
    p.append('</tr></thead><tbody>')

    for i, (_, row) in enumerate(df.iterrows()):
        is_red = (alert_condition(row) if callable(alert_condition) else False)
        row_bg = "#4a0a0a" if is_red else ("#1e2130" if i % 2 == 0 else "#16192b")
        pc     = "#00e676" if (pd.notna(row["Profit"]) and row["Profit"] > 0) else "#ff5252"
        p.append('<tr style="background:' + row_bg + ';">')
        p.append('<td style="padding:4px 10px;font-weight:700;color:'
                 + ("#ff5252" if is_red else "#4fc3f7") + ';">' + str(row["CP"]) + '</td>')
        p.append('<td style="padding:4px 10px;text-align:right;color:' + pc + ';font-weight:600;">'
                 + _fmt_pct(row["Profit"]) + '</td>')
        p.append('<td style="padding:4px 10px;text-align:right;color:#aaa;">'
                 + _fmt_pct(row["Co tuc"]) + '</td>')
        p.append('</tr>')

    p.append('</tbody></table></div>')
    return "".join(p)

def render_tab2(b2, b3):
    st.subheader("Xep hang CP theo Profit & Co tuc")
    st.caption("Bang 2: sap xep theo Co tuc giam dan. Bang 3: sap xep theo Profit giam dan. "
               "To do = Profit < 0.")

    col_a, col_b = st.columns(2)
    with col_a:
        html2 = _render_small_table(
            b2, "Bang 2: Top Co tuc cao",
            alert_col="Profit",
            alert_condition=lambda r: pd.notna(r["Profit"]) and r["Profit"] < 0,
            sort_note="(sort: Co tuc desc)")
        st.markdown(html2, unsafe_allow_html=True)
    with col_b:
        html3 = _render_small_table(
            b3, "Bang 3: Top Profit cao",
            alert_col=None,
            alert_condition=lambda r: False,
            sort_note="(sort: Profit desc)")
        st.markdown(html3, unsafe_allow_html=True)

# ── TAB 3: Scatter Profit vs Co tuc ──────────────────────────────────────────

def render_tab3(b1):
    st.subheader("Phan tich: Profit vs Co tuc/MP")
    st.caption("Goc phan tu phai tren (Profit cao + Co tuc cao) = co phieu tot nhat de giu.")

    df = b1[b1["Profit->Chot"].notna() & b1["Co tuc/MP"].notna()].copy()
    if df.empty:
        st.info("Khong du du lieu de ve chart.")
        return

    # Mau theo danh muc
    color_map = {"TẤN CÔNG": "#1e88e5", "CÂN BẰNG": "#ff6d00", "PHÒNG THỦ": "#b0bec5"}
    df["color"] = df["Danh muc"].map(color_map).fillna("#aaa")
    df["alert_marker"] = df["Alert"].apply(lambda x: "star" if x else "circle")

    fig = go.Figure()
    for dm, grp in df.groupby("Danh muc"):
        c = color_map.get(dm, "#aaa")
        fig.add_trace(go.Scatter(
            x=grp["Profit->Chot"] * 100,
            y=grp["Co tuc/MP"] * 100,
            mode="markers+text",
            name=dm,
            text=grp["CP"],
            textposition="top center",
            textfont=dict(size=9, color=c),
            marker=dict(
                size=grp["Alert"].apply(lambda a: 14 if a else 9),
                color=c,
                symbol=grp["Alert"].apply(lambda a: "star" if a else "circle"),
                line=dict(width=grp["Alert"].apply(lambda a: 2 if a else 0).tolist(),
                          color="#ff1744"),
            ),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Profit->Chot: %{x:.1f}%<br>"
                "Co tuc/MP: %{y:.1f}%<br>"
                "<extra>" + dm + "</extra>"),
        ))

    # Duong ke 0%
    fig.add_hline(y=0, line_dash="dot", line_color="#555", line_width=1)
    fig.add_vline(x=0, line_dash="dot", line_color="#555", line_width=1)

    # Vung tot nhat (goc phai tren)
    x_vals = df["Profit->Chot"].dropna() * 100
    y_vals = df["Co tuc/MP"].dropna() * 100
    if len(x_vals) > 0 and len(y_vals) > 0:
        fig.add_shape(type="rect",
                      x0=0, y0=0,
                      x1=x_vals.max() * 1.1,
                      y1=y_vals.max() * 1.1,
                      fillcolor="rgba(0,200,100,0.04)",
                      line=dict(width=0))
        fig.add_annotation(
            x=x_vals.max() * 0.7, y=y_vals.max() * 0.9,
            text="Vung tot: Profit > 0 & Co tuc cao",
            font=dict(size=10, color="#00c853"),
            showarrow=False, bgcolor="rgba(0,0,0,0.5)")

    fig.update_layout(
        template="plotly_dark", height=600,
        margin=dict(l=50, r=30, t=40, b=50),
        xaxis=dict(title="Profit -> Gia chot (%)", ticksuffix="%", zeroline=False),
        yaxis=dict(title="Co tuc / Gia thi truong (%)", ticksuffix="%", zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="closest",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Goc phan tu phai tren: vua co profit vua co co tuc cao
    best = df[(df["Profit->Chot"] > 0) & (df["Co tuc/MP"] > df["Co tuc/MP"].median())]
    if not best.empty:
        st.markdown("**Top picks (Profit > 0 & Co tuc tren trung vi):**")
        best_disp = best[["Danh muc","CP","MP","Profit->Chot","Co tuc/MP","Gia chot"]].copy()
        best_disp["Profit->Chot"] = best_disp["Profit->Chot"].apply(
            lambda v: "{:+.1f}%".format(v*100) if pd.notna(v) else "")
        best_disp["Co tuc/MP"] = best_disp["Co tuc/MP"].apply(
            lambda v: "{:.1f}%".format(v*100) if pd.notna(v) else "")
        best_disp = best_disp.sort_values("Profit->Chot", ascending=False)
        st.dataframe(best_disp, use_container_width=True, hide_index=True)

# ── TAB 4: Summary & Metrics ──────────────────────────────────────────────────

def render_tab4(b1, b2, b3):
    st.subheader("Tong quan danh muc")

    # ── By Danh muc ──
    st.markdown("#### Phan tich theo Danh muc")
    grp = b1.groupby("Danh muc").agg(
        So_CP=("CP", "count"),
        Profit_Chot_TB=("Profit->Chot", "mean"),
        Profit_Chot_Max=("Profit->Chot", "max"),
        Profit_Chot_Min=("Profit->Chot", "min"),
        CoTuc_TB=("Co tuc/MP", "mean"),
        Da_vuot=("Alert", "sum"),
    ).reset_index()

    fig_bar = go.Figure()
    for _, r in grp.iterrows():
        color = "#ff7043" if r["Da_vuot"] > 0 else "#42a5f5"
        fig_bar.add_trace(go.Bar(
            name=r["Danh muc"],
            x=[r["Danh muc"]],
            y=[r["Profit_Chot_TB"] * 100],
            marker_color=color,
            text=["{:+.1f}%".format(r["Profit_Chot_TB"]*100)],
            textposition="outside",
            hovertemplate=(
                "<b>" + str(r["Danh muc"]) + "</b><br>"
                "So CP: " + str(int(r["So_CP"])) + "<br>"
                "Profit TB: %{y:.1f}%<br>"
                "Da vuot nguong: " + str(int(r["Da_vuot"])) + "<extra></extra>"),
        ))

    fig_bar.update_layout(
        template="plotly_dark", height=350, showlegend=False,
        margin=dict(l=20, r=20, t=30, b=20),
        yaxis=dict(title="Profit TB -> Gia chot (%)", ticksuffix="%"),
        barmode="group")
    st.plotly_chart(fig_bar, use_container_width=True)

    # ── Distribution histogram ──
    st.markdown("#### Phan phoi Profit -> Gia chot")
    col_h1, col_h2 = st.columns(2)
    with col_h1:
        fig_hist = go.Figure(go.Histogram(
            x=b1["Profit->Chot"].dropna() * 100,
            nbinsx=20,
            marker_color="#42a5f5",
            hovertemplate="Profit: %{x:.0f}%<br>So CP: %{y}<extra></extra>",
        ))
        fig_hist.add_vline(x=0, line_dash="dash", line_color="#ff5252", line_width=2)
        fig_hist.update_layout(
            template="plotly_dark", height=300,
            margin=dict(l=20,r=20,t=30,b=20),
            xaxis=dict(title="Profit (%)", ticksuffix="%"),
            yaxis=dict(title="So luong CP"),
            title="Phan phoi Profit -> Gia chot")
        st.plotly_chart(fig_hist, use_container_width=True)

    with col_h2:
        fig_hist2 = go.Figure(go.Histogram(
            x=b1["Co tuc/MP"].dropna() * 100,
            nbinsx=15,
            marker_color="#66bb6a",
            hovertemplate="Co tuc/MP: %{x:.1f}%<br>So CP: %{y}<extra></extra>",
        ))
        fig_hist2.update_layout(
            template="plotly_dark", height=300,
            margin=dict(l=20,r=20,t=30,b=20),
            xaxis=dict(title="Co tuc/MP (%)", ticksuffix="%"),
            yaxis=dict(title="So luong CP"),
            title="Phan phoi Co tuc / Gia thi truong")
        st.plotly_chart(fig_hist2, use_container_width=True)

    # ── Stats table ──
    st.markdown("#### Chi tiet theo Danh muc")
    grp_disp = grp.copy()
    for col in ["Profit_Chot_TB","Profit_Chot_Max","Profit_Chot_Min","CoTuc_TB"]:
        grp_disp[col] = grp_disp[col].apply(
            lambda v: "{:+.1f}%".format(v*100) if pd.notna(v) else "")
    grp_disp.columns = ["Danh muc","So CP","Profit TB","Profit Max","Profit Min",
                        "Co tuc TB","Da vuot nguong"]
    st.dataframe(grp_disp, use_container_width=True, hide_index=True)

# ── MAIN RENDER ───────────────────────────────────────────────────────────────

def render(refresh_key=None):
    try:
        with st.spinner("Dang tai du lieu TSCP..."):
            df_raw = load_tscp()
        b1, b2, b3 = parse_tscp(df_raw)
    except Exception as e:
        st.error("Khong tai duoc du lieu TSCP: " + str(e))
        return

    # Refresh button
    col_r1, col_r2 = st.columns([8, 1])
    with col_r2:
        if st.button("Refresh", key="tscp_refresh"):
            st.cache_data.clear()
            st.rerun()
    with col_r1:
        alert_count = b1["Alert"].sum()
        if alert_count > 0:
            st.warning(str(alert_count) + " CP đã vượt giá ngừng tích sản. Xem tab Danh mục tích sản!")
        else:
            st.success("Tat ca CP deu an toan (MP < Gia ngung)")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Danh mục Tích sản",
        "Xếp hạng", #Xep hang (R:T & V:X)
        "Scatter: Lợi nhuận - Cổ tức",
        "Tổng quan danh mục",
    ])
    with tab1:
        render_tab1(b1)
    with tab2:
        render_tab2(b2, b3)
    with tab3:
        render_tab3(b1)
    with tab4:
        render_tab4(b1, b2, b3)
