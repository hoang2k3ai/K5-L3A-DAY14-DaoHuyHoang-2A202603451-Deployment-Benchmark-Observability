# Day 14 Lab — Mission Answers

## Part 1 — Localhost vs Production

### Exercise 1.1 — Anti-patterns

1. API key và thông tin đăng nhập DB nằm trong mã nguồn (`develop/app.py`, dòng 17–18). Nếu là credential thật, bất kỳ ai đọc được repo hoặc lịch sử Git cũng có thể lấy.
2. `DEBUG` và `MAX_TOKENS` được gán cố định (dòng 21–22), nên đổi môi trường cần sửa mã.
3. `print` ghi trực tiếp câu hỏi, câu trả lời và cả key (dòng 33–38), vừa rò thông tin vừa thiếu cấu trúc để lọc log.
4. App thiếu probe chuyên dụng để nền tảng biết lúc nào process còn sống và lúc nào có thể nhận traffic.
5. Uvicorn bind `localhost`, cố định cổng 8000 và bật reload (dòng 50–53). Container cần lắng nghe trên mọi interface và đọc port từ môi trường.
6. `POST /ask` trên bản develop không yêu cầu xác thực.

### Exercise 1.2 — Chạy bản develop

```text
GET /                                  → HTTP/1.1 200 OK
{"message":"Hello! Agent is running on my machine :)"}
POST /ask?question=What%20is%20Docker%3F → HTTP/1.1 200 OK
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

### Exercise 1.3 — So sánh

| Hạng mục | Develop | Production | Tác dụng |
|---|---|---|---|
| Config | Hằng số trong app | `Settings` đọc env và kiểm tra key production | Cùng một bản build chạy trên nhiều môi trường |
| Log | In câu hỏi, đáp án và key | Dùng logging và ghi theo sự kiện | Lọc và theo dõi sự cố |
| Health / readiness | Thiếu probe | Có `/health` và `/ready` | Tách sống và sẵn sàng |
| Bind / debug | Localhost, 8000, reload | Host/port/debug đọc từ env | Chạy sau proxy và trong container |
| Shutdown | Không có cleanup riêng | Lifespan thực hiện startup/shutdown | Tạo điểm dọn tài nguyên khi dừng |

## Part 2 — Docker

### Exercise 2.1 — Dockerfile

1. Base image của develop là `python:3.11`.
2. Working directory là `/app`.
3. Copy `requirements.txt` trước rồi mới cài phụ thuộc. Khi chỉ đổi mã app, Docker có thể dùng lại layer cài đặt.
4. `ENTRYPOINT` đặt chương trình chính. `CMD` cung cấp lệnh hoặc đối số mặc định mà `docker run IMAGE ...` có thể thay thế. Dockerfile develop dùng `CMD ["python", "app.py"]`.

### Exercise 2.2–2.4 — Build, kích thước và Compose

Stack đi theo luồng `Client → Nginx → Agent`. Agent nhận cấu hình kết nối Redis và Qdrant qua mạng Compose. Redis phục vụ dữ liệu tạm và Qdrant phục vụ truy vấn vector khi tính năng RAG cần dùng. Multi-stage chỉ đưa phụ thuộc đã cài và mã vào runtime slim, loại công cụ build khỏi image cuối.

`docker image inspect --format '{{.Size}}'` ghi nhận develop **1 667 788 049 byte (1 667,79 MB)** và production **239 819 645 byte (239,82 MB)**. Mức giảm là **85,62%**, tính bằng `(develop − production) / develop × 100`. MB ở đây dùng 1 000 000 byte.

Bản develop trả `HTTP/1.1 200 OK` khi gọi `POST /ask?question=What%20is%20Docker%3F`. Qua Nginx của stack production, `GET /health` và `POST /ask` với JSON `{"question":"What is Docker?"}` đều trả `HTTP/1.1 200 OK`.

## Part 3 — Cloud Deployment

Part 6 đã qua kiểm tra local. URL public và kết quả kiểm tra trên cloud sẽ được ghi trong [DEPLOYMENT.md](DEPLOYMENT.md) sau khi deploy.

Railway dùng TOML để chọn Dockerfile builder và đặt đường dẫn health check cho service. Root Directory, Redis reference và API key được cấu hình trên project. Render dùng YAML để mô tả Docker web service, `rootDir`, health check và các biến môi trường. `generateValue` cấp API key và `sync: false` yêu cầu cung cấp URL Redis qua nền tảng.

### Exercise 3.3 — Cloud Run

1. Cloud Build cài phụ thuộc rồi chạy pytest.
2. Khi test qua, Docker build image và gắn tag commit SHA cùng tag `latest`.
3. Pipeline push các tag lên registry rồi triển khai tag commit SHA bằng `gcloud run deploy` tới `asia-southeast1`.
4. `service.yaml` mô tả cấu hình runtime như truy cập secret, probe và giới hạn autoscaling.

## Part 4 — API Security

### Exercise 4.1–4.3 — API key, JWT và rate limit

Bản develop trả 401 khi thiếu API key và 200 khi dùng key hợp lệ. Ở bản production mẫu, JWT lấy từ `POST /auth/token` được gửi qua header `Authorization: Bearer`. Lượt thứ 11 trong cùng cửa sổ 60 giây bị chặn.

```text
# API key: thiếu key rồi dùng key hợp lệ
HTTP/1.1 401 Unauthorized
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
HTTP/1.1 200 OK
{"question":"Docker","answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}

# JWT: request #1 và #11
HTTP/1.1 200 OK
{"question":"Docker","answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!","usage":{"requests_remaining":9,"budget_remaining_usd":1.8e-05}}
HTTP/1.1 429 Too Many Requests
retry-after: 59
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

### Exercise 4.4 — Cost guard

Part 6 giữ trước chi phí ước tính tối đa trong Redis rồi hoàn phần chênh lệch sau khi đếm token của câu trả lời. Lua gộp kiểm tra và giữ chỗ thành một thao tác, nên hai worker không thể cùng dùng một phần ngân sách còn lại. Thiếu ngân sách trả 402. Vượt số lượt trong 60 giây trả 429.

## Part 5 — Scaling & Reliability

1. `/health` cho biết process còn hoạt động. `/ready` cho biết instance sẵn sàng nhận traffic. Cả hai trả `HTTP/1.1 200 OK` trong lần chạy bản develop.
2. Gửi `POST /ask?question=Docker` rồi gửi SIGTERM sau 0,5 giây. Request đang xử lý trả 200, log ghi `Shutdown complete` và process thoát với mã 0.
3. Nếu giữ session trong RAM, request sang worker khác hoặc sau restart sẽ mất lịch sử. Redis giữ session dùng chung cho các instance.
4. Nginx phân phối request tới các replica của agent. Trường `served_by` cho biết instance đã trả lời.
5. Chạy `test_stateless.py` qua Nginx cổng 8085 để tránh xung đột với stack observability. Năm lượt gọi lần lượt đến `instance-eb3ebe`, `instance-be83f9`, `instance-76503e`, `instance-eb3ebe` và `instance-be83f9`. Đọc lại session từ Redis qua API nhận đủ 10 tin nhắn, gồm 5 câu hỏi và 5 câu trả lời.

## Part 6 — Checklist Deliverable

Chạy script chấm gốc với Docker và Redis thật trên Ubuntu WSL.

```text
📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

## AI log

- Yêu cầu Codex đọc Markdown và hỗ trợ hoàn thành lab. Codex triển khai agent Part 6, bổ sung metric Histogram và tài liệu JWT/HPA, soạn các mục giải thích, chạy kiểm thử qua Ubuntu WSL và lưu JSON từ công cụ benchmark/eval.
- Codex dùng Lua cho rate limit và cost guard để các worker chia sẻ state, dùng Redis lưu ngân sách theo kỳ UTC và bật hai Uvicorn worker trong Docker để kiểm thử shutdown qua process quản lý worker.
- Codex chạy eval trước và sau thay đổi, đối chiếu bảng với JSON/CSV và dùng script chấm gốc. Để thu bằng chứng Part 7, Codex sửa nơi cài dependencies trong Dockerfile observability và thêm `--no-deps` vào lệnh Locust để giữ đúng số replica.
- Lượt rà soát báo cáo: học viên yêu cầu làm rõ câu chữ và các mục cần tự bổ sung. Codex rút gọn phần giải thích, làm rõ giới hạn của phép đo và bổ sung chỗ ghi kết quả triển khai.
- **Phần kiểm tra và chỉnh sửa của mình:** Mình nhờ Codex chạy `python check_production_ready.py` trên WSL với Docker và Redis. Kết quả lưu trong bài là `PASS 12/12` với 43/43 kiểm tra. Codex cũng đối chiếu bảng benchmark với JSON và CSV rồi chỉnh câu chữ theo yêu cầu của mình. Đây là kết quả kiểm tra do Codex thực hiện trong workspace.
