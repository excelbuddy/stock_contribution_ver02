import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import io
import requests

st.set_page_config(page_title="VNIndex Contribution Dashboard", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

SHEET_ID = "1vxAlLu79JEKN-q6R2-6zxFKC2BrsfrUJjOzbstpA2kc"

st.markdown('<style>div[data-testid="stMetricValue"]{font-size:1.4rem!important}</style>', unsafe_allow_html=True)

# ── DATA LOADING ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def load_sheet(name):
    url = "https://docs.google.com/spreadsheets/d/" + SHEET_ID + "/gviz/tq?tqx=out:csv&sheet=" + name
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text))

@st.cache_data(ttl=3600, show_spinner=False)
def load_all():
    with st.spinner("Dang tai du lieu..."):
        hist  = load_sheet("hose-history")
        pc    = load_sheet("hose-history-PC")
        c_old = load_sheet("Contribution_old")
        c_new = load_sheet("Contribution")
    return hist, pc, c_old, c_new

# ── HELPERS ───────────────────────────────────────────────────────────────────

def parse_influence(val):
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

def prep_history(hist):
    df = hist.copy()
    df["Date"] = pd.to_datetime(df.iloc[:, 0], errors="coerce")
    mask = df["Date"].isna()
    df.loc[mask, "Date"] = pd.to_datetime(df.loc[mask, "Ngay"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    df["Close"] = pd.to_numeric(df["GiaDieuChinh"], errors="coerce")
    return df[["Date", "Close"]].dropna()

def prep_pc(pc):
    df = pc.copy()
    df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
    df["End Date"]   = pd.to_datetime(df["End Date"],   errors="coerce")
    df["Change_pct"] = pd.to_numeric(
        df["Change %"].astype(str)
        .str.replace("%", "", regex=False)
        .str.replace("+", "", regex=False)
        .str.strip(),
        errors="coerce")
    df["Days"]     = pd.to_numeric(df["Days"], errors="coerce")
    df["has_data"] = ~df["Contribution Data"].str.contains("Not available", na=True)
    return df

def prep_c_old(c_old):
    # Contribution_old: pre-aggregated per period (Start Date, End Date, StockCode, InfluenceIndex)
    # Type = Gainers if InfluenceIndex > 0, else Losers  [matches =IF(E>0,"Gainers","Losers")]
    df = c_old.copy()
    df["Start Date"]     = pd.to_datetime(df["Start Date"], errors="coerce")
    df["End Date"]       = pd.to_datetime(df["End Date"],   errors="coerce")
    df["InfluenceIndex"] = pd.to_numeric(df["InfluenceIndex"], errors="coerce")
    df["Type"] = df["InfluenceIndex"].apply(lambda x: "Gainers" if x > 0 else "Losers")
    return df

def prep_c_new(c_new, pc):
    # Sheet Contribution: daily rows. Google Sheet DB logic:
    #   For each period (StartDate, EndDate):
    #     Filter daily rows: Date > StartDate AND Date <= EndDate
    #     SUMIF InfluenceIndex by StockCode  (= QUERY FILTER ... select Col3 Col5)
    #     Gainers = summed rows with result > 0
    #     Losers  = summed rows with result < 0
    #   % column = InfluenceIndex / GAP_pts  where GAP_pts = VNI_End - VNI_Start
    df = c_new.copy()
    df["Date"]           = pd.to_datetime(df["Date"], errors="coerce")
    df["InfluenceIndex"] = df["InfluenceIndex"].apply(parse_influence)

    pc_calc = pc[pc["Contribution Data"].str.contains("Need to calculate", na=False)].copy()

    rows = []
    for _, period in pc_calc.iterrows():
        sd = period["Start Date"]
        ed = period["End Date"]
        # Strictly after StartDate, up to and including EndDate
        mask = (df["Date"] > sd) & (df["Date"] <= ed)
        sub  = df[mask].copy()
        if sub.empty:
            continue

        # SUMIF InfluenceIndex by StockCode across all days in the period
        agg = sub.groupby("StockCode")["InfluenceIndex"].sum().reset_index()

        # Assign Type from sign of cumulative influence
        agg["Type"] = agg["InfluenceIndex"].apply(lambda x: "Gainers" if x > 0 else "Losers")

        agg["Start Date"] = sd
        agg["End Date"]   = ed

        # ClosePrice = last known price for each stock within the period
        last_price = (sub.sort_values("Date")
                         .drop_duplicates("StockCode", keep="last")
                         .set_index("StockCode")["ClosePrice"])
        agg["ClosePrice"] = agg["StockCode"].map(last_price)

        rows.append(agg)

    if rows:
        return pd.concat(rows, ignore_index=True)
    return pd.DataFrame(columns=["Start Date", "End Date", "StockCode", "ClosePrice", "InfluenceIndex", "Type"])

def combine(c_old, c_new_agg):
    combined = pd.concat([c_old, c_new_agg], ignore_index=True)
    combined["InfluenceIndex"] = pd.to_numeric(combined["InfluenceIndex"], errors="coerce").fillna(0)
    # Ensure Type matches sign (defensive — mirrors =IF(InfluenceIndex>0,"Gainers","Losers"))
    combined["Type"] = combined["InfluenceIndex"].apply(lambda x: "Gainers" if x > 0 else "Losers")
    return combined

# ── TAB 1 HELPERS ─────────────────────────────────────────────────────────────

def metric_box_html(label, value, color="white"):
    return (
        '<div style="flex:1;background:rgba(0,0,0,0.3);border-radius:4px;padding:3px 5px;text-align:center;">'
        + '<div style="font-size:9px;color:#aaa;">' + label + '</div>'
        + '<div style="font-weight:700;color:' + color + ';font-size:12px;">' + value + '</div>'
        + '</div>'
    )

def build_header_html(period_number, ptype, sd, ed, days, vi_s, vi_e, gap_pts, chg):
    color_header = "#1b5e20" if ptype == "UP" else "#7b1515"
    badge_color  = "#00c853" if ptype == "UP" else "#ff1744"
    gap_color    = "#00c853" if gap_pts >= 0 else "#ff1744"

    parts = []
    parts.append('<div style="background:' + color_header + ';border-radius:8px 8px 0 0;padding:10px 12px;">')
    parts.append('<div style="display:flex;justify-content:space-between;align-items:center;">')
    parts.append('<span style="font-size:11px;color:#ccc;">Dinh/Day ' + str(period_number) + '</span>')
    parts.append('<span style="background:' + badge_color + ';color:white;font-weight:700;padding:2px 10px;border-radius:4px;font-size:12px;">' + ptype + '</span>')
    parts.append('</div>')
    parts.append('<div style="font-size:11px;color:#eee;margin-top:4px;">' + sd.strftime("%Y-%m-%d") + ' &rarr; ' + ed.strftime("%Y-%m-%d") + '</div>')
    parts.append('<div style="display:flex;gap:5px;margin-top:6px;">')
    parts.append(metric_box_html("So ngay GD", str(days)))
    parts.append(metric_box_html("VNI Start", "{:,.0f}".format(vi_s)))
    parts.append(metric_box_html("VNI End", "{:,.0f}".format(vi_e)))
    parts.append(metric_box_html("GAP (diem)", "{:+.1f}".format(gap_pts), gap_color))
    parts.append(metric_box_html("GAP (%)", "{:+.1f}%".format(chg), gap_color))
    parts.append('</div></div>')
    return "".join(parts)

def build_table_html(gainers, losers, gap_pts):
    parts = []
    parts.append('<div style="background:#12151f;border-radius:0 0 8px 8px;overflow:hidden;margin-bottom:14px;">')
    parts.append('<table style="width:100%;border-collapse:collapse;font-size:12px;">')
    parts.append('<thead>')
    parts.append('<tr>')
    parts.append('<th colspan="3" style="background:#1b3a1b;color:#00e676;text-align:center;padding:4px;font-size:11px;">TOP TANG</th>')
    parts.append('<th colspan="3" style="background:#3a1b1b;color:#ff5252;text-align:center;padding:4px;font-size:11px;">TOP GIAM</th>')
    parts.append('</tr>')
    parts.append('<tr style="background:#1a1d2e;">')
    for _ in range(2):
        parts.append('<th style="color:#ccc;padding:2px 6px;font-size:10px;font-weight:500;">CP</th>')
        parts.append('<th style="color:#ccc;padding:2px 6px;font-size:10px;font-weight:500;text-align:right;">Dong gop</th>')
        parts.append('<th style="color:#ccc;padding:2px 6px;font-size:10px;font-weight:500;text-align:right;">%</th>')
    parts.append('</tr>')
    parts.append('</thead><tbody>')

    max_rows = max(len(gainers), len(losers))
    for i in range(max_rows):
        g_code = g_inf = g_pct = ""
        l_code = l_inf = l_pct = ""
        if i < len(gainers):
            g = gainers.iloc[i]
            g_code = str(g["StockCode"])
            g_inf  = "{:+.1f}".format(g["InfluenceIndex"])
            g_pct  = "{:.1f}%".format(g["InfluenceIndex"] / gap_pts * 100) if gap_pts else ""
        if i < len(losers):
            l = losers.iloc[i]
            l_code = str(l["StockCode"])
            l_inf  = "{:+.1f}".format(l["InfluenceIndex"])
            l_pct  = "{:.1f}%".format(l["InfluenceIndex"] / gap_pts * 100) if gap_pts else ""

        row_bg = "#1e2130" if i % 2 == 0 else "#16192b"
        parts.append('<tr style="background:' + row_bg + ';">')
        parts.append('<td style="color:#00e676;font-weight:600;padding:2px 6px;">'                    + g_code + '</td>')
        parts.append('<td style="color:#00e676;text-align:right;padding:2px 6px;">'                   + g_inf  + '</td>')
        parts.append('<td style="color:#00e676;text-align:right;padding:2px 6px;font-size:11px;">'    + g_pct  + '</td>')
        parts.append('<td style="color:#ff5252;font-weight:600;padding:2px 6px;">'                    + l_code + '</td>')
        parts.append('<td style="color:#ff5252;text-align:right;padding:2px 6px;">'                   + l_inf  + '</td>')
        parts.append('<td style="color:#ff5252;text-align:right;padding:2px 6px;font-size:11px;">'    + l_pct  + '</td>')
        parts.append('</tr>')

    parts.append('</tbody></table></div>')
    return "".join(parts)

# ── TAB 1 ─────────────────────────────────────────────────────────────────────

def render_tab1(pc, combined):
    st.subheader("Thong ke Contribution theo dot tang/giam")

    pc_with_data = pc[pc["has_data"]].reset_index(drop=True)
    if pc_with_data.empty:
        st.info("Chua co du lieu contribution.")
        return

    col_f1, col_f2, col_f3 = st.columns([2, 2, 3])
    with col_f1:
        type_filter = st.selectbox("Loai dot", ["Tat ca", "UP", "DOWN"])
    with col_f2:
        top_n = st.slider("Top N co phieu moi dot", 5, 30, 15)
    with col_f3:
        period_labels = [
            r["Type"] + " " + r["Start Date"].strftime("%Y-%m-%d") + " -> "
            + r["End Date"].strftime("%Y-%m-%d") + " ("
            + "{:+.1f}%".format(r["Change_pct"]) + ")"
            for _, r in pc_with_data.iterrows()
        ]
        selected_periods = st.multiselect("Chon dot (de trong = tat ca)", options=period_labels)

    if type_filter != "Tat ca":
        pc_with_data = pc_with_data[pc_with_data["Type"] == type_filter]

    periods = []
    for _, row in pc_with_data.iterrows():
        label = (row["Type"] + " " + row["Start Date"].strftime("%Y-%m-%d")
                 + " -> " + row["End Date"].strftime("%Y-%m-%d")
                 + " (" + "{:+.1f}%".format(row["Change_pct"]) + ")")
        if selected_periods and label not in selected_periods:
            continue
        periods.append(row)

    if not periods:
        st.warning("Khong co dot nao phu hop.")
        return

    cols_per_row = 4
    for row_start in range(0, len(periods), cols_per_row):
        row_periods = periods[row_start: row_start + cols_per_row]
        cols = st.columns(cols_per_row)

        for col_idx, period in enumerate(row_periods):
            sd    = period["Start Date"]
            ed    = period["End Date"]
            ptype = period["Type"]
            chg   = period["Change_pct"]
            days  = int(period["Days"])
            vi_s  = period["VNIndex-Start"]
            vi_e  = period["VNIndex-End"]
            gap_pts      = vi_e - vi_s
            period_number = row_start + col_idx + 1

            mask = (combined["Start Date"] == sd) & (combined["End Date"] == ed)
            df_p = combined[mask].copy()

            gainers = df_p[df_p["Type"] == "Gainers"].nlargest(top_n, "InfluenceIndex")
            losers  = df_p[df_p["Type"] == "Losers"].nsmallest(top_n, "InfluenceIndex")

            with cols[col_idx]:
                st.markdown(build_header_html(period_number, ptype, sd, ed, days, vi_s, vi_e, gap_pts, chg), unsafe_allow_html=True)
                if df_p.empty:
                    st.markdown('<div style="background:#1e2130;padding:8px;border-radius:0 0 8px 8px;margin-bottom:14px;"><i style="color:#888;">Chua co du lieu</i></div>', unsafe_allow_html=True)
                else:
                    st.markdown(build_table_html(gainers, losers, gap_pts), unsafe_allow_html=True)

# ── TAB 2 ─────────────────────────────────────────────────────────────────────

def render_tab2(hist_df, pc):
    st.subheader("Lich su VNIndex voi dinh/day")

    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        year_from = st.number_input("Tu nam", min_value=2000, max_value=2026, value=2015, step=1)
    with c2:
        year_to = st.number_input("Den nam", min_value=2000, max_value=2026, value=2026, step=1)
    with c3:
        show_annotations = st.checkbox("Hien mui ten & chu thich", value=True)

    df   = hist_df[(hist_df["Date"].dt.year >= year_from) & (hist_df["Date"].dt.year <= year_to)]
    pc_f = pc[(pc["Start Date"].dt.year >= year_from) | (pc["End Date"].dt.year <= year_to + 1)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["Close"], mode="lines",
        line=dict(color="#4fc3f7", width=1.5), name="VNIndex",
        hovertemplate="<b>%{x|%d/%m/%Y}</b><br>VNIndex: %{y:,.2f}<extra></extra>",
    ))

    peak_dates, peak_vals, trough_dates, trough_vals = [], [], [], []
    for _, row in pc_f.iterrows():
        if row["Type"] == "UP":
            peak_dates.append(row["End Date"])
            peak_vals.append(row["VNIndex-End"])
        else:
            trough_dates.append(row["End Date"])
            trough_vals.append(row["VNIndex-End"])

    fig.add_trace(go.Scatter(
        x=peak_dates, y=peak_vals, mode="markers",
        marker=dict(color="#ff1744", size=10, symbol="triangle-up", line=dict(color="white", width=1)),
        name="Dinh",
        hovertemplate="<b>Dinh %{x|%d/%m/%Y}</b><br>%{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=trough_dates, y=trough_vals, mode="markers",
        marker=dict(color="#00e676", size=10, symbol="triangle-down", line=dict(color="white", width=1)),
        name="Day",
        hovertemplate="<b>Day %{x|%d/%m/%Y}</b><br>%{y:,.2f}<extra></extra>",
    ))

    if show_annotations:
        all_pts = sorted([
            {"date": row["End Date"], "val": row["VNIndex-End"], "chg": row["Change_pct"], "days": row["Days"]}
            for _, row in pc_f.iterrows()
        ], key=lambda x: x["date"])

        for i in range(len(all_pts) - 1):
            p0, p1 = all_pts[i], all_pts[i + 1]
            if p0["date"].year < year_from or p1["date"].year > year_to + 1:
                continue
            is_up = p1["val"] > p0["val"]
            arr_color = "#00e676" if is_up else "#ff5252"
            fig.add_annotation(
                x=p1["date"], y=p1["val"], ax=p0["date"], ay=p0["val"],
                xref="x", yref="y", axref="x", ayref="y",
                showarrow=True, arrowhead=2, arrowsize=1.2, arrowwidth=1.5,
                arrowcolor=arr_color,
                text="{:+.1f}%<br>{}ng".format(p1["chg"], int(p1["days"])),
                font=dict(size=9, color=arr_color),
                bgcolor="rgba(0,0,0,0.6)", borderpad=2,
            )

    fig.update_layout(
        template="plotly_dark", height=650,
        margin=dict(l=60, r=40, t=40, b=40),
        xaxis=dict(title="Ngay", rangeslider=dict(visible=True, thickness=0.04), type="date"),
        yaxis=dict(title="VNIndex", tickformat=",.0f"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Bang cac dot tang/giam")
    disp = pc_f[["Start Date", "End Date", "Type", "VNIndex-Start", "VNIndex-End", "Change %", "Days", "Contribution Data"]].copy()
    disp["Start Date"] = disp["Start Date"].dt.strftime("%Y-%m-%d")
    disp["End Date"]   = disp["End Date"].dt.strftime("%Y-%m-%d")

    def color_type(val):
        if val == "UP":
            return "background-color:#1b3a1b;color:#00e676;font-weight:bold"
        return "background-color:#3a1b1b;color:#ff5252;font-weight:bold"

    def color_chg(val):
        try:
            v = float(str(val).replace("%", "").replace("+", "").strip())
            return "color:#00e676;font-weight:bold" if v > 0 else "color:#ff5252;font-weight:bold"
        except:
            return ""

    st.dataframe(
        disp.style.applymap(color_type, subset=["Type"]).applymap(color_chg, subset=["Change %"]),
        use_container_width=True, height=300,
    )

# ── TAB 3 ─────────────────────────────────────────────────────────────────────

def render_tab3(pc, combined):
    st.subheader("Phan tich co phieu dong gop chinh theo xu huong")

    pc_with_data = pc[pc["has_data"]].reset_index(drop=True)
    if pc_with_data.empty or combined.empty:
        st.info("Chua du du lieu.")
        return

    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        trend_filter = st.selectbox("Xu huong", ["Tat ca", "UP", "DOWN"])
    with c2:
        top_stocks = st.slider("So co phieu hien thi", 10, 50, 20)
    with c3:
        min_periods = st.slider("Xuat hien toi thieu (dot)", 1, 10, 2)

    merged_rows = []
    for _, p in pc_with_data.iterrows():
        mask = (combined["Start Date"] == p["Start Date"]) & (combined["End Date"] == p["End Date"])
        sub  = combined[mask].copy()
        sub["period_type"] = p["Type"]
        sub["period_chg"]  = p["Change_pct"]
        merged_rows.append(sub)

    if not merged_rows:
        st.warning("Khong khop du lieu.")
        return

    all_data = pd.concat(merged_rows, ignore_index=True)
    if trend_filter != "Tat ca":
        all_data = all_data[all_data["period_type"] == trend_filter]

    gainers_data = all_data[all_data["Type"] == "Gainers"]
    losers_data  = all_data[all_data["Type"] == "Losers"]

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### Co phieu dong gop tang nhieu nhat")
        if not gainers_data.empty:
            g_agg = (gainers_data.groupby("StockCode")
                     .agg(total=("InfluenceIndex", "sum"),
                          count=("InfluenceIndex", "count"),
                          avg=("InfluenceIndex", "mean"))
                     .reset_index())
            g_agg = g_agg[g_agg["count"] >= min_periods].nlargest(top_stocks, "total")
            fig_g = go.Figure(go.Bar(
                x=g_agg["total"], y=g_agg["StockCode"], orientation="h",
                marker_color="#00c853",
                customdata=np.stack([g_agg["count"], g_agg["avg"]], axis=-1),
                hovertemplate="<b>%{y}</b><br>Tong: %{x:.1f}<br>So dot: %{customdata[0]}<br>TB/dot: %{customdata[1]:.2f}<extra></extra>",
            ))
            fig_g.update_layout(
                template="plotly_dark", height=550,
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis_title="Tong diem dong gop",
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig_g, use_container_width=True)

    with col_b:
        st.markdown("#### Co phieu keo giam nhieu nhat")
        if not losers_data.empty:
            l_agg = (losers_data.groupby("StockCode")
                     .agg(total=("InfluenceIndex", "sum"),
                          count=("InfluenceIndex", "count"),
                          avg=("InfluenceIndex", "mean"))
                     .reset_index())
            l_agg = l_agg[l_agg["count"] >= min_periods].nsmallest(top_stocks, "total")
            fig_l = go.Figure(go.Bar(
                x=l_agg["total"].abs(), y=l_agg["StockCode"], orientation="h",
                marker_color="#ff1744",
                customdata=np.stack([l_agg["count"], l_agg["avg"].abs()], axis=-1),
                hovertemplate="<b>%{y}</b><br>Tong: -%{x:.1f}<br>So dot: %{customdata[0]}<br>TB/dot: %{customdata[1]:.2f}<extra></extra>",
            ))
            fig_l.update_layout(
                template="plotly_dark", height=550,
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis_title="Tong diem keo giam",
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig_l, use_container_width=True)

    st.markdown("---")
    st.markdown("#### Heatmap: Dong gop cua tung co phieu qua cac dot")

    all_data["period_label"] = (
        all_data["period_type"] + " "
        + all_data["Start Date"].dt.strftime("%y/%m") + "->"
        + all_data["End Date"].dt.strftime("%y/%m")
    )
    top_s = (all_data.groupby("StockCode")["InfluenceIndex"]
             .apply(lambda x: x.abs().sum())
             .nlargest(top_stocks).index.tolist())
    heat_data = all_data[all_data["StockCode"].isin(top_s)]
    pivot = heat_data.pivot_table(
        index="StockCode", columns="period_label",
        values="InfluenceIndex", aggfunc="sum", fill_value=0,
    )
    if not pivot.empty:
        fig_h = go.Figure(go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale=[[0.0, "#b71c1c"], [0.4, "#880e4f"], [0.5, "#1a1a2e"], [0.6, "#1b5e20"], [1.0, "#00e676"]],
            zmid=0,
            text=np.round(pivot.values, 1),
            texttemplate="%{text}",
            textfont=dict(size=9),
            hovertemplate="<b>%{y}</b> | %{x}<br>Diem: %{z:.2f}<extra></extra>",
            colorbar=dict(title="Diem"),
        ))
        fig_h.update_layout(
            template="plotly_dark",
            height=max(400, len(pivot) * 22),
            margin=dict(l=20, r=20, t=20, b=80),
            xaxis=dict(tickangle=-45, tickfont=dict(size=9)),
            yaxis=dict(tickfont=dict(size=10)),
        )
        st.plotly_chart(fig_h, use_container_width=True)

    st.markdown("---")
    st.markdown("#### Xac suat xuat hien trong dot UP / DOWN")

    n_up   = len(pc_with_data[pc_with_data["Type"] == "UP"])
    n_down = len(pc_with_data[pc_with_data["Type"] == "DOWN"])

    up_app = (all_data[(all_data["period_type"] == "UP") & (all_data["InfluenceIndex"] > 0)]
              .groupby("StockCode")["InfluenceIndex"]
              .agg(["count", "sum", "mean"])
              .rename(columns={"count": "up_count", "sum": "up_total", "mean": "up_avg"}))
    dn_app = (all_data[(all_data["period_type"] == "DOWN") & (all_data["InfluenceIndex"] < 0)]
              .groupby("StockCode")["InfluenceIndex"]
              .agg(["count", "sum", "mean"])
              .rename(columns={"count": "dn_count", "sum": "dn_total", "mean": "dn_avg"}))

    prob = pd.concat([up_app, dn_app], axis=1).fillna(0)
    prob["up_count"] = prob["up_count"].astype(int)
    prob["dn_count"] = prob["dn_count"].astype(int)
    prob["P_UP"] = (prob["up_count"] / n_up   * 100).round(1) if n_up   > 0 else 0.0
    prob["P_DN"] = (prob["dn_count"] / n_down * 100).round(1) if n_down > 0 else 0.0

    disp_prob = prob[["up_count", "P_UP", "up_total", "dn_count", "P_DN", "dn_total"]].copy()
    disp_prob.columns = ["So dot UP tang", "P(Tang|UP)%", "Tong dong gop UP",
                         "So dot DOWN giam", "P(Giam|DOWN)%", "Tong keo giam DOWN"]
    disp_prob = disp_prob.sort_values("P(Tang|UP)%", ascending=False)
    disp_prob = disp_prob[disp_prob[["So dot UP tang", "So dot DOWN giam"]].max(axis=1) >= min_periods]

    def color_up(val):
        try:
            g = min(int(float(val) * 2.55), 200)
            return "background-color:rgba(0," + str(g) + ",80,0.4);color:#00e676"
        except:
            return ""

    def color_dn(val):
        try:
            r = min(int(float(val) * 2.55), 200)
            return "background-color:rgba(" + str(r) + ",0,50,0.4);color:#ff5252"
        except:
            return ""

    def color_contrib(val):
        try:
            return "color:#00e676" if float(val) > 0 else "color:#ff5252"
        except:
            return ""

    st.dataframe(
        disp_prob.style
        .applymap(color_up,     subset=["P(Tang|UP)%"])
        .applymap(color_dn,     subset=["P(Giam|DOWN)%"])
        .applymap(color_contrib, subset=["Tong dong gop UP", "Tong keo giam DOWN"])
        .format({
            "P(Tang|UP)%":       "{:.1f}%",
            "P(Giam|DOWN)%":     "{:.1f}%",
            "Tong dong gop UP":  "{:+.1f}",
            "Tong keo giam DOWN": "{:+.1f}",
        }),
        use_container_width=True,
        height=500,
    )
    st.caption(
        "Tong so dot UP co du lieu: " + str(n_up)
        + " | Tong so dot DOWN co du lieu: " + str(n_down)
        + ". P(Tang|UP)% = xac suat co phieu dong gop duong trong dot UP."
    )

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    st.title("VNIndex Contribution Dashboard")
    st.caption("Du lieu HOSE - Cap nhat tu dong tu Google Sheets")

    try:
        hist_raw, pc_raw, c_old_raw, c_new_raw = load_all()
    except Exception as e:
        st.error("Khong tai duoc du lieu: " + str(e))
        st.stop()

    hist_df  = prep_history(hist_raw)
    pc_df    = prep_pc(pc_raw)
    c_old_df = prep_c_old(c_old_raw)
    c_new_ag = prep_c_new(c_new_raw, pc_df)
    combined = combine(c_old_df, c_new_ag)

    last_row = hist_df.iloc[-1]
    prev_row = hist_df.iloc[-2]
    delta    = last_row["Close"] - prev_row["Close"]
    delta_p  = delta / prev_row["Close"] * 100

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("VNIndex", "{:,.2f}".format(last_row["Close"]), "{:+.2f} ({:+.2f}%)".format(delta, delta_p))
    k2.metric("Phien gan nhat", last_row["Date"].strftime("%d/%m/%Y"))
    pc_latest = pc_df.iloc[-1]
    k3.metric("Dot hien tai", pc_latest["Type"], "{:+.1f}% / {} ngay".format(pc_latest["Change_pct"], int(pc_latest["Days"])))
    k4.metric("So dot co du lieu", str(pc_df["has_data"].sum()))
    k5.metric("Tong co phieu tracking", str(combined["StockCode"].nunique()))

    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["Bang Contribution theo dot", "Chart lich su VNIndex", "Insights & Xac suat"])

    with tab1:
        render_tab1(pc_df, combined)
    with tab2:
        render_tab2(hist_df, pc_df)
    with tab3:
        render_tab3(pc_df, combined)

    st.markdown("---")
    st.caption("VNIndex Dashboard - Du lieu tu HOSE - Khong phai tu van dau tu")

if __name__ == "__main__":
    main()
