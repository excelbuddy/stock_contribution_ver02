# 📊 VNIndex Contribution Dashboard

Dashboard phân tích đỉnh/đáy VNIndex và đóng góp của cổ phiếu vào chỉ số HOSE (Vietnam Stock Exchange).

## 🌐 Live Demo
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io)

## 📋 Tính năng

### Tab 1 – Bảng Thống Kê Contribution
- Bảng pivot hiển thị đóng góp của từng cổ phiếu trong mỗi đợt tăng/giảm
- Phân loại **Gainers** (kéo tăng) và **Losers** (kéo giảm)
- Tổng hợp thông tin VNIndex theo từng đợt (điểm đầu, điểm cuối, % thay đổi, số ngày)

### Tab 2 – Chart Lịch sử VNIndex
- Biểu đồ toàn bộ lịch sử VNIndex từ 2000 đến nay
- **Đánh dấu đỉnh** (▲ đỏ) và **đáy** (▼ xanh) theo phân loại
- **Mũi tên nối** giữa các đỉnh/đáy liên tiếp kèm:
  - % tăng/giảm
  - Số ngày của đợt
- Vùng màu UP (xanh) / DOWN (đỏ) để dễ nhận biết xu hướng

### Tab 3 – Insight & Xác suất Giao dịch
- **Top cổ phiếu dẫn dắt** VNIndex trong các đợt UP/DOWN
- **Heatmap** đóng góp: Cổ phiếu × Đợt
- **Scatter plot**: Tần suất xuất hiện vs Xác suất đóng góp dương
- **Bảng xếp hạng** theo điểm tổng hợp (tần suất × tổng đóng góp)
- **Gợi ý MUA/BÁN** khi xác nhận xu hướng mới dựa trên xác suất lịch sử

## 🗂️ Cấu trúc dữ liệu (Google Sheets)

```
Sheet ID: 1vxAlLu79JEKN-q6R2-6zxFKC2BrsfrUJjOzbstpA2kc
├── hose-history        # Lịch sử VNIndex từ 28/07/2000 (cập nhật hàng ngày)
├── hose-history-PC     # Phân loại đợt UP/DOWN ≥10%, cập nhật hàng ngày
├── Contribution_old    # Contribution tổng hợp 17 đợt lịch sử (theo đợt)
└── Contribution        # Contribution từ 02/01/2024 (theo ngày, cập nhật hàng ngày)
```

## 🚀 Cài đặt & Chạy

### Cài đặt dependencies
```bash
pip install -r requirements.txt
```

### Chạy local
```bash
streamlit run app.py
```

### Deploy lên Streamlit Cloud
1. Fork repo này lên GitHub
2. Vào [share.streamlit.io](https://share.streamlit.io)
3. Kết nối GitHub repo → chọn `app.py`
4. Deploy!

> **Lưu ý:** Google Sheet phải ở chế độ **"Anyone with the link can view"** để đọc dữ liệu không cần xác thực.

## 📖 Hướng dẫn sử dụng

### Khi VNIndex xác nhận xu hướng UP mới:
- Xem **Tab 3 → "Cổ phiếu nên MUA"**
- Ưu tiên cổ phiếu có **tần suất > 60%** và **xác suất dương > 70%**
- Những cổ phiếu này lịch sử thường dẫn dắt VNIndex trong đợt UP

### Khi VNIndex xác nhận xu hướng DOWN mới:
- Xem **Tab 3 → "Cổ phiếu nên tránh/bán"**
- Ưu tiên bán/short cổ phiếu có đóng góp âm nhiều nhất lịch sử

## 🛠️ Tech Stack
- **Python 3.10+**
- **Streamlit** – Web framework
- **Plotly** – Interactive charts
- **Pandas** – Data processing
- **Google Sheets CSV API** – Real-time data (no auth required)

## 📄 License
MIT
