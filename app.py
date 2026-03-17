 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/app.py b/app.py
index 2cbdfadfa35df15d419ed8be82457f4f3d397205..70f3b3c5b748cf17fd31c2b14408111ffb83e8cf 100644
--- a/app.py
+++ b/app.py
@@ -21,93 +21,125 @@ st.set_page_config(
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
+
+    def parse_numeric(series):
+        """Parse numeric values robustly for VN/Google Sheet formats.
+        Supports values like 1,234.56 | 1.234,56 | 12,5% | 12.5%.
+        """
+        raw = series.astype(str).str.strip()
+        has_pct = raw.str.contains('%', regex=False)
+
+        cleaned = (
+            raw
+            .str.replace('%', '', regex=False)
+            .str.replace(' ', '', regex=False)
+            .str.replace('\u00a0', '', regex=False)
+        )
+
+        # If both "," and "." exist, assume dots are thousand separators and comma is decimal.
+        both_sep = cleaned.str.contains(',', regex=False) & cleaned.str.contains('.', regex=False)
+        cleaned.loc[both_sep] = cleaned.loc[both_sep].str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
+
+        # If only comma exists, treat it as decimal separator.
+        comma_only = cleaned.str.contains(',', regex=False) & ~cleaned.str.contains('.', regex=False)
+        cleaned.loc[comma_only] = cleaned.loc[comma_only].str.replace(',', '.', regex=False)
+
+        out = pd.to_numeric(cleaned, errors='coerce')
+        out.loc[has_pct] = out.loc[has_pct] / 100
+        return out
     
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
-            pc[c] = pd.to_datetime(pc[c], errors='coerce')
+            pc[c] = pd.to_datetime(pc[c], dayfirst=True, errors='coerce')
         for c in ['StartPrice', 'EndPrice', 'ChangePct', 'Days']:
-            pc[c] = pd.to_numeric(pc[c], errors='coerce')
+            pc[c] = parse_numeric(pc[c])
+        # Normalize ChangePct to decimal ratio expected by the dashboard.
+        # If source is already ratio (e.g., 0.12), keep as-is; if source is percent (e.g., 12.0), scale down.
+        pc.loc[pc['ChangePct'].abs() > 1, 'ChangePct'] = pc.loc[pc['ChangePct'].abs() > 1, 'ChangePct'] / 100
+        pc['Type'] = pc['Type'].astype(str).str.strip().str.upper()
         pc = pc.dropna(subset=['StartDate', 'EndDate'])
 
         # Contribution_old
         cont_old = read_sheet("Contribution_old")
         cont_old.columns = ['StartDate', 'EndDate', 'StockCode', 'ClosePrice', 'InfluenceIndex', 'Type']
         for c in ['StartDate', 'EndDate']:
-            cont_old[c] = pd.to_datetime(cont_old[c], errors='coerce')
-        cont_old['InfluenceIndex'] = pd.to_numeric(cont_old['InfluenceIndex'], errors='coerce')
+            cont_old[c] = pd.to_datetime(cont_old[c], dayfirst=True, errors='coerce')
+        cont_old['InfluenceIndex'] = parse_numeric(cont_old['InfluenceIndex'])
         cont_old['StockCode'] = cont_old['StockCode'].astype(str).str.strip()
+        cont_old['Type'] = cont_old['Type'].astype(str).str.strip()
 
         # Contribution (daily)
         cont = read_sheet("Contribution")
         cont.columns = [c.strip() for c in cont.columns]
         cont = cont[['StockCode', 'ClosePrice', 'InfluenceIndex', 'Date', 'Type']].copy()
-        cont['Date'] = pd.to_datetime(cont['Date'], errors='coerce')
-        cont['InfluenceIndex'] = pd.to_numeric(cont['InfluenceIndex'], errors='coerce')
+        cont['Date'] = pd.to_datetime(cont['Date'], dayfirst=True, errors='coerce')
+        cont['InfluenceIndex'] = parse_numeric(cont['InfluenceIndex'])
         cont['StockCode'] = cont['StockCode'].astype(str).str.strip()
+        cont['Type'] = cont['Type'].astype(str).str.strip()
 
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
 
EOF
)
