# Báo cáo UI Module 09 - Smart Room

Ngày: 2026-09-27  
Trạng thái: **INCOMPLETE**. Các gate tự động PASS; chưa kiểm tra webcam vật lý và nhận diện người thật. Dừng trước Module 10.

## Phạm vi và môi trường

- Phạm vi gồm 13 trạng thái HTML có route thật: tổng quan Smart Room, hai terminal camera, danh sách/tạo/chi tiết hồ sơ nhận diện, quyền ra vào, lịch sử ra vào và trạng thái tenant chưa đủ điều kiện.
- Không migrate lại nhóm người ở cùng của Module 05.
- Interpreter dùng cho toàn bộ gate cuối: `D:\NDT_MOTEL_ENV\Scripts\python.exe`, Python `3.12.10`, Django `4.2.30`.
- `py -3` hiện trỏ tới Python `3.14.7`; không dùng để kết luận vì Django 4.2 test client lỗi copy context (`super ... dicts`) trên môi trường đó.
- Backup trước sửa được xác nhận tại `luu_tru/ban_sao_luu/before_module09_ui_20260927_144039`: 27 file, 685.895 byte. Backup có đủ 13 template, CSS tenant cũ, backend Smart Room, URL, model/rule, test và tài liệu liên quan.

## Thay đổi

- Thêm `static/css/smart_room.css` (110 dòng) và nạp đúng một lần trong cả 13 template Module 09. Các style cục bộ hiện hữu vẫn được giữ để tránh làm lệch layout/nghiệp vụ ngoài phạm vi.
- `templates/core/smart_access_control.html` bổ sung state `processing`, chỉ bật quét khi đã chọn phòng và camera có frame live, chống gửi lặp, khóa control khi request đang chạy, phục hồi state trong `finally`, timeout 30 giây bằng `AbortController`, xử lý camera bị ngắt và dừng track khi rời trang.
- Phục hồi đầy đủ dấu tiếng Việt cho các thông báo trạng thái mới của terminal Admin.
- Không sửa model, view, endpoint, decode ảnh, YuNet/SFace, cosine threshold `0.363`, truy vấn xác định profile/quyền/phòng hoặc quyết định cho phép/từ chối.
- Hợp đồng request được giữ nguyên: POST `face_id_xac_thuc`, trường `image`, `phong`, `loai_su_kien`, CSRF header; terminal Admin tiếp tục dùng URL-encoded body, terminal Face ID tiếp tục dùng `FormData`.
- Thêm audit explicit `core/tests/visual_module09_smart_room_audit.py`; file tên `visual_*` nên không tự chen vào normal full suite.

## Gate tự động

- `manage.py check`: PASS, 0 issue.
- `makemigrations --check --dry-run`: PASS, `No changes detected`.
- Smart Room/UI: PASS `37/37`, 1,959 giây.
- Full suite: PASS `311/311`, 46,297 giây; DB `test_ndt_motel` được tạo và hủy sau chạy.
- Visual QA: PASS `52/52` tổ hợp, gồm 13 màn x `1440x900`, `1024x768`, `768x900`, `390x844`. HTTP lỗi 0, overflow ngang cấp trang 0, ảnh hỏng 0, lỗi console/page 0, thiếu `smart_room.css` 0.
- Đã xem trực tiếp ảnh mobile của đủ 13 màn và ảnh desktop của các màn dashboard, hai terminal, quyền và lịch sử; không thấy overlap hoặc clipping ngoài vùng cuộn bảng có chủ đích.
- Playwright trong sandbox bị `WinError 5` khi tạo subprocess, giống Module 08. Lượt cuối chạy ngoài sandbox PASS trên DB test cô lập.

## Camera mock

Audit browser mock media/network PASS `1/1` và xác nhận:

- Nút xác thực vẫn khóa nếu chỉ chọn phòng mà chưa có frame; mở khi đồng thời có phòng và frame live.
- Hai lần kích hoạt trong lúc `processing` chỉ tạo một request.
- Request là POST đúng endpoint, có CSRF và đủ `image/phong/loai_su_kien`.
- Các control phòng/sự kiện/camera bị khóa trong request và phục hồi đúng sau phản hồi hoặc timeout.
- Timeout vẫn là 30 giây; thông báo nhắc kiểm tra lịch sử trước khi thử lại vì request phía server có thể đã bắt đầu xử lý.
- Sự kiện rời trang gọi `stop()` trên camera track ở cả hai luồng.

Đây là mock camera và mock response, không phải bằng chứng YuNet/SFace đã nhận diện đúng trên webcam thật.

## Dữ liệu và artifact

- Live read-only: `Phong/DatPhong/HopDong/LichSuThanhToan/ThanhToanCocDatPhong/NguoiThue = 86/10/6/3/0/20`.
- Smart Room live: `FaceProfile/QuyenRaVao/LichSuRaVao = 7/2/11`.
- Gallery: `86/86`, missing cover `0`, mismatch `0`.
- Artifact ngoài allowlist ở project root: `0`.
- Source `__pycache__` dưới `core`, `templates`, `static`, `motel_management`, `tools`: `0` sau khi xóa 6 cache do test sinh.
- Toàn bộ bằng chứng Module 09 nằm dưới `luu_tru/kiem_thu/module_09/`: 52 PNG, 2 JSON và 11 log.

## Bằng chứng

- Visual: `luu_tru/kiem_thu/module_09/visual_qa/results.json` và 52 PNG.
- Camera mock: `luu_tru/kiem_thu/module_09/camera_mock/results.json`.
- Môi trường, Django gate, test, live/gallery và artifact: `luu_tru/kiem_thu/module_09/logs/`.

## Blocker và kết luận

**MANUAL BLOCKER:** chưa có phiên dùng webcam vật lý với người thật để kiểm tra quyền trình duyệt, frame thực, chất lượng ảnh, model YuNet/SFace và kết quả cấp/từ chối quyền end-to-end. Không dùng camera mock để thay thế gate này.

**Kết luận: Module 09 INCOMPLETE.** Mọi gate tự động và visual QA cô lập đều PASS, nhưng chưa nhận PASS cho nhận diện thực tế. Chưa bắt đầu Module 10.
