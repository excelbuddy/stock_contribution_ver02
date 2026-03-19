"""
app.py  -  Main entry point
===========================================================
Cau truc sidebar de phat trien them chuc nang:

  DANH MUC HIEN CO:
    Contribution Analysis  ->  contribution.py

  CHO PHAT TRIEN THEM (them vao PAGES ben duoi):
    - Screener
    - Portfolio Tracker
    - Market Overview
    - ...
===========================================================
"""

import streamlit as st
from data_loader import load_and_prep
import contribution as contrib_module
import stockprice as stockprice_module
import macro as macro_module
# import screener        (phat trien sau)
# import portfolio       (phat trien sau)

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="VNIndex Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    '<style>'
    'div[data-testid="stMetricValue"]{font-size:1.4rem!important}'
    '[data-testid="stSidebar"]{min-width:220px;max-width:220px}'
    '.sidebar-title{font-size:18px;font-weight:700;color:#4fc3f7;padding:8px 0 4px 0;}'
    '.sidebar-section{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;padding:12px 0 4px 0;}'
    '</style>',
    unsafe_allow_html=True)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
PAGES = {
    "Contribution":      ("📊", True),
    "Stock Price":        ("💹", True),
    "Vi mo & Hang hoa":   ("🌍", True),
    # "Screener":        ("🔍", False),  # TODO
    # "Portfolio":       ("💼", False),  # TODO
    # "Market Overview": ("🌐", False),  # TODO
}

with st.sidebar:
    st.markdown('<div class="sidebar-title">📈 VNIndex</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-title">Dashboard</div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown('<div class="sidebar-section">Chuc nang</div>', unsafe_allow_html=True)

    enabled = {k: v for k, v in PAGES.items() if v[1]}
    options  = [v[0] + " " + k for k, v in enabled.items()]
    sel      = st.radio("", options, label_visibility="collapsed")
    current  = sel.split(" ", 1)[1] if sel else ""

    st.markdown("---")
    st.markdown('<div class="sidebar-section">Sap ra mat</div>', unsafe_allow_html=True)
    st.markdown(
        '<div style="color:#555;font-size:12px;line-height:1.8;">'
        '🔍 Screener<br>💼 Portfolio<br>🌐 Market Overview<br></div>',
        unsafe_allow_html=True)
    st.markdown("---")
    st.markdown(
        '<div style="color:#444;font-size:11px;">'
        'Du lieu: HOSE<br>Nguon: Google Sheets<br>'
        'Khong phai tu van dau tu</div>',
        unsafe_allow_html=True)

# ── LOAD DATA ─────────────────────────────────────────────────────────────────
try:
    hist_df, pc_df, combined = load_and_prep()
except Exception as e:
    st.error("Khong tai duoc du lieu: " + str(e))
    st.stop()

# ── KPI BAR ───────────────────────────────────────────────────────────────────
last_row = hist_df.iloc[-1]
prev_row = hist_df.iloc[-2]
delta    = last_row["Close"] - prev_row["Close"]
delta_p  = delta / prev_row["Close"] * 100

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("VNIndex",
          "{:,.2f}".format(last_row["Close"]),
          "{:+.2f} ({:+.2f}%)".format(delta, delta_p))
k2.metric("Phien gan nhat", last_row["Date"].strftime("%d/%m/%Y"))
pc_latest = pc_df.iloc[-1]
k3.metric("Dot hien tai", pc_latest["Type"],
          "{:+.1f}% / {} ngay".format(pc_latest["Change_pct"], int(pc_latest["Days"])))
k4.metric("So dot co du lieu", str(pc_df["has_data"].sum()))
k5.metric("Tong CP tracking", str(combined["StockCode"].nunique()))

st.markdown("---")

# ── ROUTE ─────────────────────────────────────────────────────────────────────
if current == "Contribution":
    st.title("📊 Contribution Analysis")
    st.caption("Phan tich dong gop co phieu vao VNIndex theo cac dot tang/giam")

    tab1, tab2, tab3 = st.tabs([
        "Bang Contribution theo dot",
        "Chart lich su VNIndex",
        "Insights & Xac suat",
    ])
    with tab1:
        contrib_module.render_tab1(pc_df, combined)
    with tab2:
        contrib_module.render_tab2(hist_df, pc_df)
    with tab3:
        contrib_module.render_tab3(pc_df, combined)

elif current == "Stock Price":
    st.title("💹 Stock Price Tracker")
    st.caption("So sanh gia thi truong voi gia tri chot loi")
    stockprice_module.render()

elif current == "Vi mo & Hang hoa":
    st.title("🌍 Vi mo & Hang hoa")
    st.caption("Bieu do hang hoa, lai suat, ty gia va cac chi so vi mo")
    macro_module.render()

# elif current == "Screener":
#     import screener
#     screener.render(hist_df, pc_df, combined)

st.markdown("---")
st.caption("VNIndex Dashboard · Du lieu HOSE · Khong phai tu van dau tu")
