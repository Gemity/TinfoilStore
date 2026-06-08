# Hướng Dẫn Quản Trị TinfoilStore

Trang quản trị: **http://180.93.35.196/docs**

Tài liệu này dành cho người vận hành shop hằng ngày. Mọi thao tác đều làm trên `/docs`, không cần chạy lệnh bash ở máy local.

## 1. Đăng nhập

1. Mở trình duyệt và vào `http://180.93.35.196/docs`
2. Nhấn nút **Authorize** ở góc trên bên phải
3. Tìm mục **HTTPBasic (HTTP, Basic)**
4. Nhập:

```text
Username: admin
Password: admin123
```

5. Nhấn **Authorize**
6. Nhấn **Close**

Sau đó bạn có thể dùng toàn bộ chức năng quản trị bên dưới.

## 2. Tạo User Mới

Mỗi người dùng Tinfoil cần một tài khoản riêng.

1. Tìm endpoint **POST /admin/users**
2. Nhấn **Try it out**
3. Nhập mẫu sau:

```json
{
  "username": "nguyen01",
  "email": "nguyen01@gmail.com",
  "password": "matkhau123",
  "role": "user"
}
```

4. Nhấn **Execute**
5. Nếu thấy **Code 201** là thành công
6. Ghi lại `id` của user để cấp subscription

Lưu ý:

- `username` không được trùng
- `email` phải đúng định dạng và không trùng
- `password` tối thiểu 6 ký tự
- `role` luôn để `"user"`

## 3. Xem Danh Sách User

1. Tìm endpoint **GET /admin/users**
2. Nhấn **Try it out**
3. Nhấn **Execute**

Bạn sẽ thấy:

- `id`
- `username`
- `is_active`
- `created_at`

## 4. Cấp Subscription

Sau khi tạo user, cần cấp subscription để họ tải game được.

1. Tìm endpoint **POST /admin/subscriptions/{user_id}/grant**
2. Nhấn **Try it out**
3. Dán `id` của user vào ô `user_id`
4. Nhập một trong các mẫu sau

Cấp 30 ngày:

```json
{
  "days": 30,
  "hours": 0,
  "minutes": 0
}
```

Cấp 1 năm:

```json
{
  "days": 365,
  "hours": 0,
  "minutes": 0
}
```

Cấp 5 phút để test:

```json
{
  "days": 0,
  "hours": 0,
  "minutes": 5
}
```

5. Nhấn **Execute**
6. Nếu thấy `effective_status = active` là xong

## 5. Gia Hạn Subscription

1. Tìm endpoint **POST /admin/subscriptions/{user_id}/extend**
2. Nhấn **Try it out**
3. Dán `id` của user vào ô `user_id`
4. Nhập ví dụ:

```json
{
  "days": 30,
  "hours": 0,
  "minutes": 0,
  "notes": "Gia han thang 4"
}
```

5. Nhấn **Execute**
6. Xem `ends_at` để biết hạn mới

## 6. Thu Hồi Subscription

1. Tìm endpoint **POST /admin/subscriptions/{user_id}/revoke**
2. Nhấn **Try it out**
3. Dán `id` của user vào ô `user_id`
4. Nhập ví dụ:

```json
{
  "reason": "Vi pham quy dinh"
}
```

5. Nhấn **Execute**
6. Nếu thấy `effective_status = revoked` là đã thu hồi

## 7. Xem Danh Sách Game

1. Tìm endpoint **GET /admin/content**
2. Nhấn **Try it out**
3. Nhấn **Execute**

Bạn sẽ thấy toàn bộ game đang có trong shop.

## 8. Cập Nhật Game Mới Từ Wasabi

Đây là cách chuẩn để thêm game mới vào shop.

Khi đã upload game lên Wasabi, chỉ cần chạy:

1. Tìm endpoint **POST /admin/sync**
2. Nhấn **Try it out**
3. Nếu muốn scan toàn bộ bucket thì để mặc định
4. Nếu muốn scan một thư mục riêng, nhập `prefix`
5. Nếu muốn xóa game đã bị xóa khỏi Wasabi, đặt `cleanup = true`
6. Nhấn **Execute**

Ví dụ:

Scan toàn bộ bucket:

```text
POST /admin/sync
```

Scan thư mục `games/`:

```text
POST /admin/sync?prefix=games/
```

Scan và xóa game stale:

```text
POST /admin/sync?cleanup=true
```

Sau khi chạy xong, hệ thống sẽ tự:

- quét Wasabi bucket hiện tại
- thêm game mới vào database
- xóa game stale nếu bật `cleanup`
- tự warm local icon cache

Response mẫu:

```json
{
  "message": "Sync completed and local icon cache warmed.",
  "sync": {
    "added": [],
    "removed": [],
    "total": 1,
    "scanned": 1
  },
  "asset_cache": {
    "titles": 1,
    "iconUrl": 1,
    "bannerUrl": 1
  }
}
```

Ý nghĩa:

- `sync.added`: game mới thêm vào DB
- `sync.removed`: game bị xóa khỏi DB khi dùng cleanup
- `sync.total`: tổng số game hiện có
- `sync.scanned`: số file quét được trên Wasabi
- `asset_cache`: số icon/banner đã được làm nóng cache local

## 9. Thêm Game Thủ Công

Chỉ dùng khi thật sự cần.

1. Tìm endpoint **POST /admin/content**
2. Nhấn **Try it out**
3. Nhập ví dụ:

```json
{
  "title": "Ten Game [0100XXXXXXXXXXXX][v0].nsp",
  "storage_key": "Ten Game [0100XXXXXXXXXXXX][v0].nsp",
  "size_bytes": 1000000000,
  "is_protected": true
}
```

Giải thích:

- `title`: tên file game
- `storage_key`: đường dẫn file trên Wasabi
- `size_bytes`: dung lượng file
- `is_protected`: để `true`

## 10. Gửi Thông Tin Shop Cho User

Sau khi tạo user và cấp subscription, gửi cho user:

```text
Protocol:  http
Host:      180.93.35.196
Port:      80
Path:      /shop/
Username:  (username da tao)
Password:  (password da tao)
Title:     TinfoilStore
```

Lưu ý:

- `Title` chỉ là tên hiển thị
- không nhập URL vào `Title`
- không nhập `admin:password@host` vào `Title`

## 11. Quy Trình Nhanh

```text
Bước 1: POST /admin/users
Bước 2: Copy id của user
Bước 3: POST /admin/subscriptions/{user_id}/grant
Bước 4: Upload game lên Wasabi
Bước 5: POST /admin/sync
Bước 6: Gửi cấu hình shop cho user
```

## 12. Mã Lỗi Thường Gặp

| Code | Nghĩa | Cách xử lý |
|------|------|------------|
| 200 | Thành công | OK |
| 201 | Tạo thành công | OK |
| 401 | Chưa đăng nhập | Authorize lại |
| 403 | Không có quyền | Chỉ admin mới dùng được |
| 404 | Không tìm thấy | Kiểm tra lại `user_id`, `content_id` hoặc endpoint |
| 409 | Bị trùng | Đổi username hoặc email |
| 422 | Sai định dạng dữ liệu | Kiểm tra lại JSON |

## 13. Ghi Nhớ Quan Trọng

- Không cần chạy lệnh bash trên máy local để sync game nữa
- Không cần `.env` local để vận hành shop
- Chỉ cần upload game lên Wasabi rồi dùng `POST /admin/sync`
- Icon game hiện được cache local trên VPS
- Nếu Tinfoil không thấy cover art, kiểm tra chế độ hiển thị có đang ở list/table view hay không
