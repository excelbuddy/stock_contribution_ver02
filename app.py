import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import gspread
from google.oauth2 import service_account
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="VNIndex Contribution Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background: #0d1117; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background: #161b22; border-radius: 8px 8px 0 0;
        color: #8b949e; padding: 10px 20px; font-weight: 600;
    }
    .stTabs [aria-selected="true"] { background: #1f6feb; color: white; }
    .metric-card {
        background: #161b22; border: 1px solid #30363d;
        border-radius: 10px; padding: 16px; text-align: center;
    }
    .up-badge { background: #1a4731; color: #3fb950; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 700; }
    .down-badge { background: #4d1515; color: #f85149; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 700; }
    div[data-testid="metric-container"] { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 12px; }
</style>
""", unsafe_allow_html=True)

SHEET_ID = "1vxAlLu79JEKN-q6R2-6zxFKC2BrsfrUJjOzbstpA2kc"

# ─── Data loading ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_data():
    base_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet="
    
    def read_sheet(name):
        url = base_url + name.replace(" ", "%20")
        return pd.read_csv(url)
    
    try:
        # hose-history
        hist = read_sheet("hose-history")
        hist.columns = [c.strip() for c in hist.columns]
        # find date and price columns
        date_col = hist.columns[1]    # Ngay
        price_col = hist.columns[2]   # GiaDieuChinh
        hist = hist[[date_col, price_col]].copy()
        hist.columns = ['Date', 'Close']
        hist['Date'] = pd.to_datetime(hist['Date'], dayfirst=True, errors='coerce')
        hist['Close'] = pd.to_numeric(hist['Close'], errors='coerce')
        hist = hist.dropna().sort_values('Date').reset_index(drop=True)

        # hose-history-PC
        pc = read_sheet("hose-history-PC")
        pc.columns = [c.strip() for c in pc.columns]
        pc.columns = ['StartDate', 'EndDate', 'Type', 'StartPrice', 'EndPrice', 'ChangePct', 'Days', 'ContribData']
        for c in ['StartDate', 'EndDate']:
            pc[c] = pd.to_datetime(pc[c], errors='coerce')
        for c in ['StartPrice', 'EndPrice', 'ChangePct', 'Days']:
            pc[c] = pd.to_numeric(pc[c], errors='coerce')
        pc = pc.dropna(subset=['StartDate', 'EndDate'])

        # Contribution_old
        cont_old = read_sheet("Contribution_old")
        cont_old.columns = ['StartDate', 'EndDate', 'StockCode', 'ClosePrice', 'InfluenceIndex', 'Type']
        for c in ['StartDate', 'EndDate']:
            cont_old[c] = pd.to_datetime(cont_old[c], errors='coerce')
        cont_old['InfluenceIndex'] = pd.to_numeric(cont_old['InfluenceIndex'], errors='coerce')
        cont_old['StockCode'] = cont_old['StockCode'].astype(str).str.strip()

        # Contribution (daily)
        cont = read_sheet("Contribution")
        cont.columns = [c.strip() for c in cont.columns]
        cont = cont[['StockCode', 'ClosePrice', 'InfluenceIndex', 'Date', 'Type']].copy()
        cont['Date'] = pd.to_datetime(cont['Date'], errors='coerce')
        cont['InfluenceIndex'] = pd.to_numeric(cont['InfluenceIndex'], errors='coerce')
        cont['StockCode'] = cont['StockCode'].astype(str).str.strip()

        return hist, pc, cont_old, cont

    except Exception as e:
        st.error(f"Lỗi khi tải dữ liệu từ Google Sheets: {e}")
        st.stop()


def build_period_contribution(cont_old, cont, pc_row):
    """Aggregate contribution for a given PC period.
    ContribData values:
      - 'Available in sheet "Contribution_old"' → use cont_old
      - '"Need to calculate in sheet "Contribution"' → aggregate from daily cont
    """
    sd, ed = pc_row['StartDate'], pc_row['EndDate']
    cd = str(pc_row['ContribData'])

    if 'Contribution_old' in cd:
        # Use pre-aggregated data from cont_old
        df = cont_old[(cont_old['StartDate'] == sd) & (cont_old['EndDate'] == ed)].copy()
        if not df.empty:
            return df[['StockCode', 'InfluenceIndex', 'Type']].copy()
        # fallback to daily aggregation
        df = cont[(cont['Date'] >= sd) & (cont['Date'] <= ed)]
        if not df.empty:
            return df.groupby(['StockCode', 'Type'])['InfluenceIndex'].sum().reset_index()
        return pd.DataFrame()

    elif 'Contribution' in cd:
        # "Need to calculate" — aggregate daily contribution in date range
        df = cont[(cont['Date'] >= sd) & (cont['Date'] <= ed)]
        if not df.empty:
            return df.groupby(['StockCode', 'Type'])['InfluenceIndex'].sum().reset_index()
        return pd.DataFrame()

    return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 – BẢNG THỐNG KÊ CONTRIBUTION
# ═══════════════════════════════════════════════════════════════════════════════
def render_tab1(hist, pc, cont_old, cont):
    st.subheader("📊 Bảng Thống Kê Contribution – Đỉnh/Đáy VNIndex")

    # Sidebar filter
    st.sidebar.header("🔧 Lọc Tab 1")
    type_filter = st.sidebar.multiselect("Loại đợt", ["UP", "DOWN"], default=["UP", "DOWN"])
    min_change = st.sidebar.slider("Biến động tối thiểu (%)", 0, 200, 10)
    top_n = st.sidebar.slider("Hiện top N cổ phiếu", 5, 30, 15)

    pc_filtered = pc[
        pc['Type'].isin(type_filter) &
        (pc['ChangePct'].abs() * 100 >= min_change)
    ].copy()

    # Summary row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng số đợt", len(pc_filtered))
    c2.metric("Đợt UP", len(pc_filtered[pc_filtered['Type'] == 'UP']))
    c3.metric("Đợt DOWN", len(pc_filtered[pc_filtered['Type'] == 'DOWN']))
    latest = pc.iloc[-1]
    label = "🟢 UP" if latest['Type'] == 'UP' else "🔴 DOWN"
    c4.metric("Xu hướng hiện tại", label, f"{latest['ChangePct']*100:.1f}%")

    st.divider()

    # ── Pivot table: each period as column ──────────────────────────────────
    # Fix: "Not available" also contains "available" → must exclude it explicitly
    periods_with_data = pc_filtered[
        pc_filtered['ContribData'].str.contains('Available in|Need to calculate', na=False, case=False)
    ]

    all_rows = []
    period_labels = []
    for _, row in periods_with_data.iterrows():
        pct_str = f"{row['ChangePct']*100:+.0f}%"
        label = f"{'🟢' if row['Type']=='UP' else '🔴'} {row['StartDate'].strftime('%m/%y')} {pct_str}"
        period_labels.append(label)
        df = build_period_contribution(cont_old, cont, row)
        if not df.empty:
            for _, r in df.iterrows():
                all_rows.append({
                    'Period': label,
                    'Type_period': row['Type'],
                    'StockCode': r['StockCode'],
                    'InfluenceIndex': r['InfluenceIndex'],
                    'ContribType': r.get('Type', 'Unknown')
                })

    if not all_rows:
        st.warning("Không có dữ liệu contribution cho các đợt đã lọc.")
        return

    df_all = pd.DataFrame(all_rows)

    # Aggregate: top gainers per period
    st.markdown("### 📈 Top Gainers theo từng đợt")
    gainers = df_all[df_all['ContribType'] == 'Gainers']
    if not gainers.empty:
        pivot_g = gainers.pivot_table(index='StockCode', columns='Period', values='InfluenceIndex', aggfunc='sum')
        pivot_g['Tổng'] = pivot_g.sum(axis=1)
        pivot_g['Số đợt'] = pivot_g.drop('Tổng', axis=1).notna().sum(axis=1)
        pivot_g = pivot_g.sort_values('Tổng', ascending=False).head(top_n)
        pivot_g = pivot_g.round(2)

        def style_gainer(val):
            if pd.isna(val) or val == 0: return 'color: #484f58'
            if val > 0: return 'background-color: #1a3a1a; color: #3fb950; font-weight: bold'
            return 'background-color: #3a1a1a; color: #f85149'

        styled = pivot_g.style.map(style_gainer).format("{:.2f}", na_rep="-")
        st.dataframe(styled, use_container_width=True, height=400)

    # Top losers
    st.markdown("### 📉 Top Losers theo từng đợt")
    losers = df_all[df_all['ContribType'] == 'Losers']
    if not losers.empty:
        pivot_l = losers.pivot_table(index='StockCode', columns='Period', values='InfluenceIndex', aggfunc='sum')
        pivot_l['Tổng'] = pivot_l.sum(axis=1)
        pivot_l['Số đợt'] = pivot_l.drop('Tổng', axis=1).notna().sum(axis=1)
        pivot_l = pivot_l.sort_values('Tổng').head(top_n)
        pivot_l = pivot_l.round(2)

        def style_loser(val):
            if pd.isna(val) or val == 0: return 'color: #484f58'
            if val < 0: return 'background-color: #3a1a1a; color: #f85149; font-weight: bold'
            return 'background-color: #1a3a1a; color: #3fb950'

        styled_l = pivot_l.style.map(style_loser).format("{:.2f}", na_rep="-")
        st.dataframe(styled_l, use_container_width=True, height=350)

    # Tổng hợp theo từng đợt (dashboard-style header rows như ảnh mẫu)
    st.divider()
    st.markdown("### 📋 Tổng hợp VNIndex theo từng đợt")
    summary_rows = []
    for _, row in periods_with_data.iterrows():
        summary_rows.append({
            'Loại': "🟢 UP" if row['Type'] == 'UP' else "🔴 DOWN",
            'Từ ngày': row['StartDate'].strftime('%Y-%m-%d'),
            'Đến ngày': row['EndDate'].strftime('%Y-%m-%d'),
            'Điểm đầu': f"{row['StartPrice']:.2f}",
            'Điểm cuối': f"{row['EndPrice']:.2f}",
            'Thay đổi': f"{row['ChangePct']*100:+.1f}%",
            'Số ngày': int(row['Days']) if pd.notna(row['Days']) else '-',
        })
    if summary_rows:
        df_sum = pd.DataFrame(summary_rows)

        def color_type(val):
            if '🟢' in str(val): return 'color: #3fb950; font-weight: bold'
            return 'color: #f85149; font-weight: bold'

        def color_change(val):
            if '+' in str(val): return 'color: #3fb950'
            return 'color: #f85149'

        styled_sum = df_sum.style\
            .map(color_type, subset=['Loại'])\
            .map(color_change, subset=['Thay đổi'])
        st.dataframe(styled_sum, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 – CHART LỊCH SỬ VNINDEX
# ═══════════════════════════════════════════════════════════════════════════════
def render_tab2(hist, pc):
    st.subheader("📈 Lịch sử VNIndex – Đỉnh/Đáy & Xu hướng")

    # Sidebar filter
    st.sidebar.header("🔧 Lọc Tab 2")
    years = sorted(hist['Date'].dt.year.unique())
    year_range = st.sidebar.select_slider("Khoảng thời gian", options=years, value=(max(years)-10, max(years)))
    show_arrows = st.sidebar.checkbox("Hiện mũi tên giữa đỉnh/đáy", True)
    show_pct = st.sidebar.checkbox("Hiện % thay đổi trên mũi tên", True)

    hist_f = hist[(hist['Date'].dt.year >= year_range[0]) & (hist['Date'].dt.year <= year_range[1])]
    pc_f = pc[(pc['StartDate'].dt.year >= year_range[0]) | (pc['EndDate'].dt.year <= year_range[1]+1)]

    fig = go.Figure()

    # Main price line
    fig.add_trace(go.Scatter(
        x=hist_f['Date'], y=hist_f['Close'],
        mode='lines', name='VNIndex',
        line=dict(color='#58a6ff', width=1.5),
        hovertemplate='%{x|%Y-%m-%d}<br>VNIndex: <b>%{y:.2f}</b><extra></extra>'
    ))

    # UP/DOWN shaded regions
    for _, row in pc_f.iterrows():
        color = 'rgba(63,185,80,0.08)' if row['Type'] == 'UP' else 'rgba(248,81,73,0.08)'
        fig.add_vrect(
            x0=row['StartDate'], x1=row['EndDate'],
            fillcolor=color, layer='below', line_width=0
        )

    # Peaks and troughs markers
    peak_dates, peak_prices, trough_dates, trough_prices = [], [], [], []
    for _, row in pc_f.iterrows():
        if row['Type'] == 'UP':
            trough_dates.append(row['StartDate'])
            trough_prices.append(row['StartPrice'])
            peak_dates.append(row['EndDate'])
            peak_prices.append(row['EndPrice'])
        else:
            peak_dates.append(row['StartDate'])
            peak_prices.append(row['StartPrice'])
            trough_dates.append(row['EndDate'])
            trough_prices.append(row['EndPrice'])

    fig.add_trace(go.Scatter(
        x=peak_dates, y=peak_prices,
        mode='markers', name='Đỉnh',
        marker=dict(symbol='triangle-up', size=12, color='#f85149', line=dict(color='#ff6b6b', width=1.5)),
        hovertemplate='<b>Đỉnh</b><br>%{x|%Y-%m-%d}<br>%{y:.2f}<extra></extra>'
    ))
    fig.add_trace(go.Scatter(
        x=trough_dates, y=trough_prices,
        mode='markers', name='Đáy',
        marker=dict(symbol='triangle-down', size=12, color='#3fb950', line=dict(color='#56d364', width=1.5)),
        hovertemplate='<b>Đáy</b><br>%{x|%Y-%m-%d}<br>%{y:.2f}<extra></extra>'
    ))

    # Arrows + annotations between consecutive peaks/troughs
    if show_arrows:
        prev_end_date = None
        prev_end_price = None
        for _, row in pc_f.iterrows():
            if prev_end_date is not None:
                mid_x = prev_end_date + (row['StartDate'] - prev_end_date) / 2
                pct = row['ChangePct'] * 100
                days = int(row['Days']) if pd.notna(row['Days']) else 0
                color = '#3fb950' if row['Type'] == 'UP' else '#f85149'
                sign = '+' if pct > 0 else ''

                # Arrow annotation
                fig.add_annotation(
                    x=row['EndDate'], y=row['EndPrice'],
                    ax=row['StartDate'], ay=row['StartPrice'],
                    xref='x', yref='y', axref='x', ayref='y',
                    arrowhead=2, arrowsize=1.2, arrowwidth=1.5, arrowcolor=color,
                    showarrow=True
                )
                if show_pct:
                    fig.add_annotation(
                        x=mid_x,
                        y=(row['StartPrice'] + row['EndPrice']) / 2,
                        text=f"<b>{sign}{pct:.1f}%</b><br><span style='font-size:10px'>{days}ngày</span>",
                        showarrow=False,
                        font=dict(size=10, color=color),
                        bgcolor='rgba(22,27,34,0.85)',
                        bordercolor=color, borderwidth=1, borderpad=3,
                        xref='x', yref='y'
                    )
            prev_end_date = row['EndDate']
            prev_end_price = row['EndPrice']

    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
        title=dict(text="VNIndex – Lịch sử Đỉnh/Đáy", font=dict(size=18, color='#e6edf3')),
        xaxis=dict(showgrid=True, gridcolor='#21262d', title=''),
        yaxis=dict(showgrid=True, gridcolor='#21262d', title='VNIndex', side='right'),
        legend=dict(bgcolor='#161b22', bordercolor='#30363d', borderwidth=1),
        height=600,
        hovermode='x unified',
        margin=dict(l=20, r=60, t=60, b=40)
    )
    st.plotly_chart(fig, use_container_width=True)

    # Stats table
    st.markdown("### 📊 Thống kê các đợt")
    pc_disp = pc_f.copy()
    pc_disp['Loại'] = pc_disp['Type'].map({'UP': '🟢 UP', 'DOWN': '🔴 DOWN'})
    pc_disp['Từ'] = pc_disp['StartDate'].dt.strftime('%Y-%m-%d')
    pc_disp['Đến'] = pc_disp['EndDate'].dt.strftime('%Y-%m-%d')
    pc_disp['Điểm đầu'] = pc_disp['StartPrice'].round(2)
    pc_disp['Điểm cuối'] = pc_disp['EndPrice'].round(2)
    pc_disp['Thay đổi'] = (pc_disp['ChangePct'] * 100).map(lambda x: f"{x:+.1f}%")
    pc_disp['Số ngày'] = pc_disp['Days'].fillna(0).astype(int)
    st.dataframe(
        pc_disp[['Loại', 'Từ', 'Đến', 'Điểm đầu', 'Điểm cuối', 'Thay đổi', 'Số ngày']],
        use_container_width=True, hide_index=True, height=350
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 – INSIGHT: QUY LUẬT CỔ PHIẾU
# ═══════════════════════════════════════════════════════════════════════════════
def render_tab3(pc, cont_old, cont):
    st.subheader("🔍 Insight – Quy luật & Xác suất Cổ phiếu dẫn dắt VNIndex")
    st.markdown("""
    > **Mục tiêu**: Tìm cổ phiếu xuất hiện nhiều lần, đóng góp đáng kể trong các đợt UP/DOWN.
    > Khi VNIndex xác nhận xu hướng mới, bạn có thể ưu tiên giao dịch theo xác suất đóng góp lịch sử.
    """)

    # Build full contribution df across all periods
    all_rows = []
    periods_with_data = pc[pc['ContribData'].str.contains('Available in|Need to calculate', na=False, case=False)]

    for _, row in periods_with_data.iterrows():
        df = build_period_contribution(cont_old, cont, row)
        if df.empty:
            continue
        for _, r in df.iterrows():
            all_rows.append({
                'Period': f"{row['StartDate'].strftime('%Y-%m-%d')}→{row['EndDate'].strftime('%Y-%m-%d')}",
                'PeriodType': row['Type'],
                'StartDate': row['StartDate'],
                'EndDate': row['EndDate'],
                'ChangePct': row['ChangePct'] * 100,
                'StockCode': r['StockCode'],
                'InfluenceIndex': r['InfluenceIndex'],
                'ContribType': r.get('Type', 'Unknown')
            })

    if not all_rows:
        st.warning("Không đủ dữ liệu để phân tích.")
        return

    df_all = pd.DataFrame(all_rows)
    total_periods = df_all['Period'].nunique()
    total_up = df_all[df_all['PeriodType'] == 'UP']['Period'].nunique()
    total_down = df_all[df_all['PeriodType'] == 'DOWN']['Period'].nunique()

    # Sidebar filters
    st.sidebar.header("🔧 Lọc Tab 3")
    insight_type = st.sidebar.radio("Xu hướng phân tích", ["UP", "DOWN", "Tất cả"])
    top_k = st.sidebar.slider("Top K cổ phiếu", 10, 50, 20)
    min_periods = st.sidebar.slider("Xuất hiện ít nhất N đợt", 1, min(10, total_periods), 2)

    if insight_type != "Tất cả":
        df_f = df_all[df_all['PeriodType'] == insight_type]
        n_total = total_up if insight_type == 'UP' else total_down
    else:
        df_f = df_all
        n_total = total_periods

    # Aggregate
    agg = df_f.groupby('StockCode').agg(
        TotalContrib=('InfluenceIndex', 'sum'),
        AvgContrib=('InfluenceIndex', 'mean'),
        NumPeriods=('Period', 'nunique'),
        NumPositive=('InfluenceIndex', lambda x: (x > 0).sum()),
        NumNegative=('InfluenceIndex', lambda x: (x < 0).sum()),
    ).reset_index()
    agg['AppearRate'] = (agg['NumPeriods'] / n_total * 100).round(1)
    agg['PosRate'] = (agg['NumPositive'] / agg['NumPeriods'] * 100).round(1)
    agg = agg[agg['NumPeriods'] >= min_periods]
    agg_top = agg.nlargest(top_k, 'TotalContrib')

    # ── KPI row ──────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    c1.metric("Tổng số đợt có dữ liệu", total_periods)
    c2.metric("Đợt UP", total_up)
    c3.metric("Đợt DOWN", total_down)

    st.divider()

    # ── Bar chart: Total contribution ────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 🏆 Tổng đóng góp tích lũy (Top cổ phiếu)")
        fig_bar = go.Figure(go.Bar(
            x=agg_top['StockCode'],
            y=agg_top['TotalContrib'],
            marker_color=['#3fb950' if v > 0 else '#f85149' for v in agg_top['TotalContrib']],
            hovertemplate='<b>%{x}</b><br>Tổng: %{y:.2f}<extra></extra>'
        ))
        fig_bar.update_layout(
            template='plotly_dark', paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
            height=380, margin=dict(l=20, r=20, t=10, b=40),
            xaxis=dict(tickangle=-45)
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col2:
        st.markdown("#### 📊 Tần suất xuất hiện & xác suất tích cực")
        fig_sc = go.Figure(go.Scatter(
            x=agg_top['AppearRate'],
            y=agg_top['PosRate'],
            mode='markers+text',
            text=agg_top['StockCode'],
            textposition='top center',
            marker=dict(
                size=agg_top['NumPeriods'] * 3,
                color=agg_top['TotalContrib'],
                colorscale='RdYlGn',
                showscale=True,
                colorbar=dict(title='Tổng đóng góp')
            ),
            hovertemplate='<b>%{text}</b><br>Tần suất: %{x:.1f}%<br>Xác suất +: %{y:.1f}%<extra></extra>'
        ))
        fig_sc.update_layout(
            template='plotly_dark', paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
            height=380, margin=dict(l=20, r=20, t=10, b=40),
            xaxis=dict(title='Tần suất xuất hiện (%)'),
            yaxis=dict(title='Xác suất đóng góp dương (%)'),
        )
        fig_sc.add_hline(y=50, line_dash='dash', line_color='#8b949e', opacity=0.5)
        fig_sc.add_vline(x=agg_top['AppearRate'].mean(), line_dash='dash', line_color='#8b949e', opacity=0.5)
        st.plotly_chart(fig_sc, use_container_width=True)

    # ── Heatmap: Contribution per period ────────────────────────────────────
    st.markdown("#### 🗺️ Heatmap đóng góp – Cổ phiếu × Đợt")
    top_stocks = agg_top.head(25)['StockCode'].tolist()
    df_heat = df_f[df_f['StockCode'].isin(top_stocks)]
    df_heat = df_heat.groupby(['StockCode', 'Period'])['InfluenceIndex'].sum().reset_index()
    pivot_h = df_heat.pivot(index='StockCode', columns='Period', values='InfluenceIndex').fillna(0)
    pivot_h = pivot_h.reindex(top_stocks)

    fig_heat = go.Figure(go.Heatmap(
        z=pivot_h.values,
        x=list(pivot_h.columns),
        y=list(pivot_h.index),
        colorscale='RdYlGn',
        zmid=0,
        hovertemplate='<b>%{y}</b><br>Đợt: %{x}<br>Đóng góp: %{z:.2f}<extra></extra>'
    ))
    fig_heat.update_layout(
        template='plotly_dark', paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
        height=500, margin=dict(l=80, r=20, t=20, b=120),
        xaxis=dict(tickangle=-45, tickfont=dict(size=9))
    )
    st.plotly_chart(fig_heat, use_container_width=True)

    # ── Ranking table ────────────────────────────────────────────────────────
    st.markdown("#### 📋 Bảng xếp hạng xác suất giao dịch")
    rank = agg.copy()
    rank['Score'] = rank['TotalContrib'] * rank['AppearRate'] / 100
    rank = rank.sort_values('Score', ascending=False).head(top_k).reset_index(drop=True)
    rank.index += 1
    rank['TotalContrib'] = rank['TotalContrib'].round(2)
    rank['AvgContrib'] = rank['AvgContrib'].round(2)
    rank['Score'] = rank['Score'].round(2)

    def color_score(val):
        if val > 0: return 'color: #3fb950; font-weight: bold'
        return 'color: #f85149; font-weight: bold'

    styled_rank = rank[['StockCode', 'TotalContrib', 'AvgContrib', 'NumPeriods', 'AppearRate', 'PosRate', 'Score']]\
        .rename(columns={
            'StockCode': 'Mã CP', 'TotalContrib': 'Tổng đóng góp',
            'AvgContrib': 'TB/đợt', 'NumPeriods': 'Số đợt',
            'AppearRate': 'Tần suất (%)', 'PosRate': 'Xác suất + (%)',
            'Score': 'Điểm tổng hợp'
        })\
        .style.map(color_score, subset=['Tổng đóng góp', 'TB/đợt', 'Điểm tổng hợp'])

    st.dataframe(styled_rank, use_container_width=True, height=450)

    # ── Interpretation helper ─────────────────────────────────────────────────
    st.divider()
    st.markdown("### 💡 Gợi ý giao dịch dựa trên xác suất lịch sử")
    current_trend = pc.iloc[-1]
    trend_label = "🟢 UP" if current_trend['Type'] == 'UP' else "🔴 DOWN"
    st.info(f"**Xu hướng hiện tại:** {trend_label} | Từ {current_trend['StartDate'].strftime('%Y-%m-%d')} | {current_trend['ChangePct']*100:+.1f}%")

    col_a, col_b = st.columns(2)
    # Candidates to BUY in UP trend
    up_stocks = df_all[(df_all['PeriodType'] == 'UP') & (df_all['ContribType'] == 'Gainers')]
    up_agg = up_stocks.groupby('StockCode').agg(
        AvgContrib=('InfluenceIndex', 'mean'),
        NumPeriods=('Period', 'nunique')
    ).reset_index()
    up_agg['AppearRate'] = (up_agg['NumPeriods'] / total_up * 100).round(1)
    up_agg = up_agg[up_agg['NumPeriods'] >= 2].sort_values('AvgContrib', ascending=False).head(10)

    down_stocks = df_all[(df_all['PeriodType'] == 'DOWN') & (df_all['ContribType'] == 'Losers')]
    down_agg = down_stocks.groupby('StockCode').agg(
        AvgContrib=('InfluenceIndex', 'mean'),
        NumPeriods=('Period', 'nunique')
    ).reset_index()
    down_agg['AppearRate'] = (down_agg['NumPeriods'] / total_down * 100).round(1)
    down_agg = down_agg[down_agg['NumPeriods'] >= 2].sort_values('AvgContrib').head(10)

    with col_a:
        st.markdown("**📈 Cổ phiếu nên MUA khi xác nhận đợt UP**")
        st.dataframe(
            up_agg.rename(columns={'StockCode':'Mã CP','AvgContrib':'TB đóng góp','NumPeriods':'Số đợt UP','AppearRate':'Tần suất %'}),
            use_container_width=True, hide_index=True
        )
    with col_b:
        st.markdown("**📉 Cổ phiếu nên BÁN/tránh khi xác nhận đợt DOWN**")
        st.dataframe(
            down_agg.rename(columns={'StockCode':'Mã CP','AvgContrib':'TB đóng góp','NumPeriods':'Số đợt DOWN','AppearRate':'Tần suất %'}),
            use_container_width=True, hide_index=True
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    # Header
    st.markdown("""
    <div style='background: linear-gradient(135deg,#1f6feb22,#238636aa); border:1px solid #30363d;
                border-radius:12px; padding:20px; margin-bottom:20px;'>
        <h1 style='color:#e6edf3; margin:0; font-size:28px'>📊 VNIndex Contribution Dashboard</h1>
        <p style='color:#8b949e; margin:4px 0 0'>Phân tích đỉnh/đáy và đóng góp cổ phiếu – HOSE Vietnam</p>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("Đang tải dữ liệu từ Google Sheets..."):
        hist, pc, cont_old, cont = load_data()

    # Show last update
    last_date = hist['Date'].max()
    st.sidebar.markdown(f"**📅 Dữ liệu đến:** {last_date.strftime('%d/%m/%Y')}")
    st.sidebar.markdown(f"**📈 VNIndex:** {hist.iloc[-1]['Close']:.2f}")
    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Làm mới dữ liệu"):
        st.cache_data.clear()
        st.rerun()

    tab1, tab2, tab3 = st.tabs([
        "📊 Bảng Thống Kê Contribution",
        "📈 Chart Lịch sử VNIndex",
        "🔍 Insight & Xác suất Giao dịch"
    ])

    with tab1:
        render_tab1(hist, pc, cont_old, cont)
    with tab2:
        render_tab2(hist, pc)
    with tab3:
        render_tab3(pc, cont_old, cont)


if __name__ == "__main__":
    main()
