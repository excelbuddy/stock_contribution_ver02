# VNIndex Contribution Dashboard

Dashboard phân tích đóng góp cổ phiếu vào VNIndex (HOSE).

## Cài đặt

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy lên Streamlit Cloud (miễn phí)

1. Push code lên GitHub repo
2. Vào https://share.streamlit.io → "New app"
3. Chọn repo, file `app.py`, bấm Deploy

## Cấu trúc 3 Tab

### Tab 1 — Bảng Contribution theo đợt
- Grid 4 cột hiển thị từng đợt UP/DOWN
- Mỗi ô có header (loại, ngày, số ngày, VNI start, % thay đổi)
- Bảng TOP TĂNG / TOP GIẢM với cổ phiếu & điểm đóng góp
- Filter theo loại (UP/DOWN), top N, chọn đợt cụ thể

### Tab 2 — Chart lịch sử VNIndex
- Biểu đồ đường toàn bộ lịch sử từ 2000
- Đánh dấu đỉnh (▲ đỏ) và đáy (▽ xanh) theo hose-history-PC
- Mũi tên nối đỉnh/đáy liên tiếp với % thay đổi và số ngày
- Range slider để zoom, filter theo năm
- Bảng tóm tắt các đợt bên dưới

### Tab 3 — Insights & Xác suất
- Bar chart cổ phiếu đóng góp nhiều nhất (UP) / kéo giảm nhiều nhất (DOWN)
- Heatmap: cổ phiếu × đợt (màu xanh/đỏ theo điểm đóng góp)
- Bảng xác suất: P(Tăng|UP)%, P(Giảm|DOWN)% cho mỗi cổ phiếu

## Nguồn dữ liệu

Google Sheet ID: `1vxAlLu79JEKN-q6R2-6zxFKC2BrsfrUJjOzbstpA2kc`
- `hose-history`: Lịch sử VNIndex từ 28/07/2000
- `hose-history-PC`: Các đợt tăng/giảm >10%
- `Contribution_old`: Dữ liệu contribution tổng hợp theo đợt (trước 2024)
- `Contribution`: Dữ liệu contribution theo ngày từ 02/01/2024

Dữ liệu tự động cache 1 giờ, refresh khi reload trang.
