# Deployment Information

## URL public và nền tảng

Trạng thái hiện tại: đã kiểm tra local, chưa xác minh triển khai cloud. Cấu hình nằm trong [railway.toml](06-lab-complete/railway.toml) và [render.yaml](06-lab-complete/render.yaml).

| Thông tin cần điền sau khi deploy | Giá trị |
|---|---|
| Nền tảng và tên project/service | Chưa ghi nhận |
| URL public của agent | Chưa xác minh |
| Ngày kiểm tra | Chưa xác minh |

## Cấu hình service

Tạo service Docker với thư mục gốc `06-lab-complete/` và một Redis cùng môi trường. Đặt `ENVIRONMENT=production`, `LOG_LEVEL=INFO`, `RATE_LIMIT_PER_MINUTE=10` và `MONTHLY_BUDGET_USD=10`. Tạo `AGENT_API_KEY` trong nền tảng và đặt `REDIS_URL` theo kết nối Redis đã cấp. Container đọc `PORT` do nền tảng cấp. Dùng `/health` cho health check và thử riêng `/ready` để xác nhận kết nối Redis.

Với Railway CLI đã liên kết project, tạo Redis trước, rồi chọn service agent khi upload từ gốc repo bằng `railway up ./06-lab-complete --path-as-root --service day14-agent`. Đặt `REDIS_URL` của agent bằng reference tới biến `REDIS_URL` của service Redis. [Tài liệu upload bằng CLI](https://docs.railway.com/cli/deploying) · [Tài liệu Redis trên Railway](https://docs.railway.com/databases/redis)

## Kiểm tra URL public

Đặt `BASE` thành URL public và nạp `AGENT_API_KEY` vào terminal trước khi chạy. Ghi mã thực tế sau khi kiểm tra. Giữ giá trị API key và URL kết nối Redis trong môi trường triển khai.

| Lượt gọi | HTTP kỳ vọng | HTTP trên cloud |
|---|---:|---|
| `GET /health` | 200 | Chưa kiểm tra |
| `GET /ready` | 200 | Chưa kiểm tra |
| `POST /ask` thiếu key | 401 | Chưa kiểm tra |
| `POST /ask` có key hợp lệ | 200 | Chưa kiểm tra |

```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'
```

## Bằng chứng triển khai

Đang chờ service public để chụp `dashboard.png`, `running.png` và `test.png`.
