"""
contribution.py
Tab 1 : Bang Contribution theo dot
Tab 2 : Chart lich su VNIndex
Tab 3 : Insights & Xac suat
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ── HTML BUILDERS ─────────────────────────────────────────────────────────────

def _metric_box(label, value, color="white"):
    return (
        '<div style="flex:1;background:rgba(0,0,0,0.3);border-radius:4px;'
        'padding:3px 5px;text-align:center;">'
        '<div style="font-size:9px;color:#aaa;">' + label + '</div>'
        '<div style="font-weight:700;color:' + color + ';font-size:12px;">'
        + value + '</div></div>'
    )

def _build_header(num, ptype, sd, ed, days, vi_s, vi_e, gap_pts, chg):
    bg    = "#1b5e20" if ptype == "UP" else "#7b1515"
    badge = "#00c853" if ptype == "UP" else "#ff1744"
    gc    = "#00c853" if gap_pts >= 0 else "#ff1744"
    p = []
    p.append('<div style="background:' + bg
             + ';border-radius:8px 8px 0 0;padding:10px 12px;">')
    p.append('<div style="display:flex;justify-content:space-between;align-items:center;">')
    p.append('<span style="font-size:11px;color:#ccc;">Dinh/Day ' + str(num) + '</span>')
    p.append('<span style="background:' + badge
             + ';color:white;font-weight:700;padding:2px 10px;'
             'border-radius:4px;font-size:12px;">' + ptype + '</span>')
    p.append('</div>')
    p.append('<div style="font-size:11px;color:#eee;margin-top:4px;">'
             + sd.strftime("%Y-%m-%d") + ' &rarr; ' + ed.strftime("%Y-%m-%d") + '</div>')
    p.append('<div style="display:flex;gap:5px;margin-top:6px;">')
    p.append(_metric_box("So ngay GD", str(days)))
    p.append(_metric_box("VNI Start", "{:,.0f}".format(vi_s)))
    p.append(_metric_box("VNI End",   "{:,.0f}".format(vi_e)))
    p.append(_metric_box("GAP (diem)", "{:+.1f}".format(gap_pts), gc))
    p.append(_metric_box("GAP (%)",    "{:+.1f}%".format(chg),    gc))
    p.append('</div></div>')
    return "".join(p)

def _build_table(gainers, losers, gap_pts):
    p = []
    p.append('<div style="background:#12151f;border-radius:0 0 8px 8px;'
             'overflow:hidden;margin-bottom:14px;">')
    p.append('<table style="width:100%;border-collapse:collapse;font-size:12px;">')
    p.append('<thead><tr>')
    p.append('<th colspan="3" style="background:#1b3a1b;color:#00e676;'
             'text-align:center;padding:4px;font-size:11px;">TOP TANG</th>')
    p.append('<th colspan="3" style="background:#3a1b1b;color:#ff5252;'
             'text-align:center;padding:4px;font-size:11px;">TOP GIAM</th>')
    p.append('</tr>')
    p.append('<tr style="background:#1a1d2e;">')
    for _ in range(2):
        p.append('<th style="color:#ccc;padding:2px 6px;font-size:10px;font-weight:500;">CP</th>')
        p.append('<th style="color:#ccc;padding:2px 6px;font-size:10px;'
                 'font-weight:500;text-align:right;">Dong gop</th>')
        p.append('<th style="color:#ccc;padding:2px 6px;font-size:10px;'
                 'font-weight:500;text-align:right;">%</th>')
    p.append('</tr></thead><tbody>')

    max_rows = max(len(gainers), len(losers))
    for i in range(max_rows):
        g_code = g_inf = g_pct = ""
        l_code = l_inf = l_pct = ""
        if i < len(gainers):
            g      = gainers.iloc[i]
            g_code = str(g["StockCode"])
            g_inf  = "{:+.1f}".format(g["InfluenceIndex"])
            g_pct  = "{:.1f}%".format(g["InfluenceIndex"] / gap_pts * 100) if gap_pts else ""
        if i < len(losers):
            l      = losers.iloc[i]
            l_code = str(l["StockCode"])
            l_inf  = "{:+.1f}".format(l["InfluenceIndex"])
            l_pct  = "{:.1f}%".format(l["InfluenceIndex"] / gap_pts * 100) if gap_pts else ""

        row_bg = "#1e2130" if i % 2 == 0 else "#16192b"
        p.append('<tr style="background:' + row_bg + ';">')
        p.append('<td style="color:#00e676;font-weight:700;padding:3px 6px;">' + g_code + '</td>')
        p.append('<td style="color:#00e676;text-align:right;padding:3px 6px;">' + g_inf + '</td>')
        p.append('<td style="color:#00e676;text-align:right;padding:3px 6px;font-size:11px;">' + g_pct + '</td>')
        p.append('<td style="color:#ff5252;font-weight:700;padding:3px 6px;">' + l_code + '</td>')
        p.append('<td style="color:#ff5252;text-align:right;padding:3px 6px;">' + l_inf + '</td>')
        p.append('<td style="color:#ff5252;text-align:right;padding:3px 6px;font-size:11px;">' + l_pct + '</td>')
        p.append('</tr>')

    p.append('</tbody></table></div>')
    return "".join(p)

# ── TAB 1 ─────────────────────────────────────────────────────────────────────

def render_tab1(pc, combined):
    col_f1, col_f2, col_f3 = st.columns([2, 2, 4])
    with col_f1:
        type_filter = st.selectbox("Loai dot", ["Tat ca", "UP", "DOWN"])
    with col_f2:
        top_n = st.slider("Top cổ phiếu đóng góp", 5, 30, 10)
    with col_f3:
        pc_filtered = pc[pc["has_data"]]
        if type_filter != "Tat ca":
            pc_filtered = pc_filtered[pc_filtered["Type"] == type_filter]
        period_labels = [
            r["Type"] + " " + r["Start Date"].strftime("%Y-%m-%d")
            + " -> " + r["End Date"].strftime("%Y-%m-%d")
            + " (" + "{:+.1f}%".format(r["Change_pct"]) + ")"
            for _, r in pc_filtered.iterrows()
        ]
        selected_periods = st.multiselect(
            "Chon dot (de trong = tat ca)", options=period_labels)

    pc_with_data = pc[pc["has_data"]].reset_index(drop=True)
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
            vi_s  = float(str(period["VNIndex-Start"]).replace(",", "")) \
                    if pd.notna(period["VNIndex-Start"]) else 0.0
            vi_e  = float(str(period["VNIndex-End"]).replace(",", "")) \
                    if pd.notna(period["VNIndex-End"]) else 0.0
            gap_pts      = vi_e - vi_s
            period_number = row_start + col_idx + 1

            mask    = (combined["Start Date"] == sd) & (combined["End Date"] == ed)
            df_p    = combined[mask].copy()
            gainers = df_p[df_p["Type"] == "Gainers"].nlargest(top_n, "InfluenceIndex")
            losers  = df_p[df_p["Type"] == "Losers"].nsmallest(top_n, "InfluenceIndex")

            with cols[col_idx]:
                st.markdown(
                    _build_header(period_number, ptype, sd, ed, days, vi_s, vi_e, gap_pts, chg),
                    unsafe_allow_html=True)
                if df_p.empty:
                    st.markdown(
                        '<div style="background:#1e2130;padding:8px;border-radius:0 0 8px 8px;'
                        'margin-bottom:14px;"><i style="color:#888;">Chua co du lieu</i></div>',
                        unsafe_allow_html=True)
                else:
                    st.markdown(_build_table(gainers, losers, gap_pts), unsafe_allow_html=True)

# ── TAB 2 ─────────────────────────────────────────────────────────────────────

def render_tab2(hist_df, pc):
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        year_from = st.number_input("Tu nam", min_value=2000, max_value=2030, value=2015, step=1)
    with c2:
        year_to = st.number_input("Den nam", min_value=2000, max_value=2030, value=2026, step=1)
    with c3:
        show_ann = st.checkbox("Hien mui ten & chu thich", value=True)

    df   = hist_df[(hist_df["Date"].dt.year >= year_from)
                   & (hist_df["Date"].dt.year <= year_to)]
    pc_f = pc[(pc["Start Date"].dt.year >= year_from)
              | (pc["End Date"].dt.year <= year_to + 1)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["Close"], mode="lines",
        line=dict(color="#4fc3f7", width=1.5), name="VNIndex",
        hovertemplate="<b>%{x|%d/%m/%Y}</b><br>VNIndex: %{y:,.2f}<extra></extra>",
    ))

    peak_x, peak_y, trough_x, trough_y = [], [], [], []
    for _, row in pc_f.iterrows():
        if row["Type"] == "UP":
            peak_x.append(row["End Date"])
            peak_y.append(row["VNIndex-End"])
        else:
            trough_x.append(row["End Date"])
            trough_y.append(row["VNIndex-End"])

    fig.add_trace(go.Scatter(
        x=peak_x, y=peak_y, mode="markers",
        marker=dict(color="#ff1744", size=10, symbol="triangle-up",
                    line=dict(color="white", width=1)),
        name="Dinh",
        hovertemplate="<b>Dinh %{x|%d/%m/%Y}</b><br>%{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=trough_x, y=trough_y, mode="markers",
        marker=dict(color="#00e676", size=10, symbol="triangle-down",
                    line=dict(color="white", width=1)),
        name="Day",
        hovertemplate="<b>Day %{x|%d/%m/%Y}</b><br>%{y:,.2f}<extra></extra>",
    ))

    if show_ann:
        pts = sorted([
            {"date": r["End Date"], "val": r["VNIndex-End"],
             "chg": r["Change_pct"], "days": r["Days"]}
            for _, r in pc_f.iterrows()
        ], key=lambda x: x["date"])
        for i in range(len(pts) - 1):
            p0, p1 = pts[i], pts[i + 1]
            if p0["date"].year < year_from or p1["date"].year > year_to + 1:
                continue
            c = "#00e676" if p1["val"] > p0["val"] else "#ff5252"
            fig.add_annotation(
                x=p1["date"], y=p1["val"], ax=p0["date"], ay=p0["val"],
                xref="x", yref="y", axref="x", ayref="y",
                showarrow=True, arrowhead=2, arrowsize=1.2,
                arrowwidth=1.5, arrowcolor=c,
                text="{:+.1f}%<br>{}ng".format(p1["chg"], int(p1["days"])),
                font=dict(size=9, color=c),
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
    disp = pc_f[["Start Date", "End Date", "Type",
                 "VNIndex-Start", "VNIndex-End",
                 "Change %", "Days", "Contribution Data"]].copy()
    disp["Start Date"] = disp["Start Date"].dt.strftime("%Y-%m-%d")
    disp["End Date"]   = disp["End Date"].dt.strftime("%Y-%m-%d")

    def color_type(v):
        if v == "UP":
            return "background-color:#1b3a1b;color:#00e676;font-weight:bold"
        return "background-color:#3a1b1b;color:#ff5252;font-weight:bold"

    def color_chg(v):
        try:
            n = float(str(v).replace("%", "").replace("+", "").strip())
            return "color:#00e676;font-weight:bold" if n > 0 else "color:#ff5252;font-weight:bold"
        except:
            return ""

    st.dataframe(
        disp.style.applymap(color_type, subset=["Type"])
                  .applymap(color_chg,  subset=["Change %"]),
        use_container_width=True, height=300)

# ── TAB 3 ─────────────────────────────────────────────────────────────────────

def render_tab3(pc, combined):
    pc_with_data = pc[pc["has_data"]].reset_index(drop=True)
    if pc_with_data.empty or combined.empty:
        st.info("Chua du du lieu.")
        return

    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        trend_filter = st.selectbox("Xu hướng", ["Tất cả", "UP", "DOWN"])
    with c2:
        top_stocks = st.slider("Số CP hiển thị", 10, 30, 10)
    with c3:
        min_periods = st.slider("Xuất hiện tối thiểu (đợt)", 1, 10, 6)

    rows = []
    for _, p in pc_with_data.iterrows():
        mask = ((combined["Start Date"] == p["Start Date"])
                & (combined["End Date"] == p["End Date"]))
        sub = combined[mask].copy()
        sub["period_type"] = p["Type"]
        rows.append(sub)

    if not rows:
        st.warning("Khong khop du lieu.")
        return

    all_data = pd.concat(rows, ignore_index=True)
    if trend_filter != "Tat ca":
        all_data = all_data[all_data["period_type"] == trend_filter]

    gainers_data = all_data[all_data["Type"] == "Gainers"]
    losers_data  = all_data[all_data["Type"] == "Losers"]

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### CP đóng góp nhiều nhất")
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
            fig_g.update_layout(template="plotly_dark", height=550,
                                margin=dict(l=20, r=20, t=20, b=20),
                                xaxis_title="Tong diem dong gop",
                                yaxis=dict(autorange="reversed"))
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
            fig_l.update_layout(template="plotly_dark", height=550,
                                margin=dict(l=20, r=20, t=20, b=20),
                                xaxis_title="Tong diem keo giam",
                                yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig_l, use_container_width=True)

    st.markdown("---")
    st.markdown("#### Heatmap: Đóng góp của từng CP qua các đợt")
    all_data["period_label"] = (
        all_data["period_type"] + " "
        + all_data["Start Date"].dt.strftime("%y/%m") + "->"
        + all_data["End Date"].dt.strftime("%y/%m"))
    top_s = (all_data.groupby("StockCode")["InfluenceIndex"]
             .apply(lambda x: x.abs().sum())
             .nlargest(top_stocks).index.tolist())
    heat  = all_data[all_data["StockCode"].isin(top_s)]
    pivot = heat.pivot_table(index="StockCode", columns="period_label",
                             values="InfluenceIndex", aggfunc="sum", fill_value=0)
    if not pivot.empty:
        fig_h = go.Figure(go.Heatmap(
            z=pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(),
            colorscale=[[0.0,"#b71c1c"],[0.4,"#880e4f"],[0.5,"#1a1a2e"],
                        [0.6,"#1b5e20"],[1.0,"#00e676"]],
            zmid=0, text=np.round(pivot.values, 1),
            texttemplate="%{text}", textfont=dict(size=9),
            hovertemplate="<b>%{y}</b> | %{x}<br>Diem: %{z:.2f}<extra></extra>",
            colorbar=dict(title="Diem"),
        ))
        fig_h.update_layout(
            template="plotly_dark", height=max(400, len(pivot) * 22),
            margin=dict(l=20, r=20, t=20, b=80),
            xaxis=dict(tickangle=-45, tickfont=dict(size=9)),
            yaxis=dict(tickfont=dict(size=10)))
        st.plotly_chart(fig_h, use_container_width=True)

    st.markdown("---")
    st.markdown("#### Xác suất xuất hiện trong từng đợt UP / DOWN")
    n_up   = len(pc_with_data[pc_with_data["Type"] == "UP"])
    n_down = len(pc_with_data[pc_with_data["Type"] == "DOWN"])

    up_app = (all_data[(all_data["period_type"] == "UP") & (all_data["InfluenceIndex"] > 0)]
              .groupby("StockCode")["InfluenceIndex"].agg(["count", "sum", "mean"])
              .rename(columns={"count": "uc", "sum": "ut", "mean": "ua"}))
    dn_app = (all_data[(all_data["period_type"] == "DOWN") & (all_data["InfluenceIndex"] < 0)]
              .groupby("StockCode")["InfluenceIndex"].agg(["count", "sum", "mean"])
              .rename(columns={"count": "dc", "sum": "dt", "mean": "da"}))

    prob = pd.concat([up_app, dn_app], axis=1).fillna(0)
    prob["uc"] = prob["uc"].astype(int)
    prob["dc"] = prob["dc"].astype(int)
    prob["P_UP"] = (prob["uc"] / n_up   * 100).round(1) if n_up   > 0 else 0.0
    prob["P_DN"] = (prob["dc"] / n_down * 100).round(1) if n_down > 0 else 0.0

    dp = prob[["uc", "P_UP", "ut", "dc", "P_DN", "dt"]].copy()
    dp.columns = ["So dot UP tang", "P(Tang|UP)%", "Tong dong gop UP",
                  "So dot DOWN giam", "P(Giam|DOWN)%", "Tong keo giam DOWN"]
    dp = dp.sort_values("P(Tang|UP)%", ascending=False)
    dp = dp[dp[["So dot UP tang", "So dot DOWN giam"]].max(axis=1) >= min_periods]

    def cu(v):
        try:
            g = min(int(float(v) * 2.55), 200)
            return "background-color:rgba(0," + str(g) + ",80,0.4);color:#00e676"
        except: return ""

    def cd(v):
        try:
            r = min(int(float(v) * 2.55), 200)
            return "background-color:rgba(" + str(r) + ",0,50,0.4);color:#ff5252"
        except: return ""

    def cc(v):
        try: return "color:#00e676" if float(v) > 0 else "color:#ff5252"
        except: return ""

    st.dataframe(
        dp.style
        .applymap(cu, subset=["P(Tang|UP)%"])
        .applymap(cd, subset=["P(Giam|DOWN)%"])
        .applymap(cc, subset=["Tong dong gop UP", "Tong keo giam DOWN"])
        .format({"P(Tang|UP)%": "{:.1f}%", "P(Giam|DOWN)%": "{:.1f}%",
                 "Tong dong gop UP": "{:+.1f}", "Tong keo giam DOWN": "{:+.1f}"}),
        use_container_width=True, height=500)

    st.caption("Tổng số đợt UP: " + str(n_up) + " | DOWN: " + str(n_down)
               + ". P(Tang|UP)% = xác suất CP đóng góp dương trong đợt UP.")
