# Benchmark & Observability Report — Day 14

**Họ tên:** Đào Huy Hoàng · 2A202603451  
**Ngày chạy:** 25/11/2026  
**Môi trường:** Ubuntu 24.04 trên WSL2, Python 3.12.3, Docker Desktop. WSL báo 12 CPU logic và 7,6 GiB RAM. Docker đang tải và build image trong lúc benchmark local, nên có thể có nhiễu tài nguyên.

## 1. SLO của agent

| SLI | SLO | Lý do |
|---|---:|---|
| p95 latency `/ask` | < 500 ms | Ngưỡng của load test cho phần lớn request tương tác |
| Error rate `/ask` | < 2% | Ngưỡng của load test để đánh giá độ tin cậy |
| Accuracy trên golden dataset sau sửa | 100% và 0 regression | Giữ nguyên các ca đã đúng và yêu cầu đủ 23 ca đạt |

## 2. Benchmark hiệu năng

### 2.1 Concurrency vs latency (agent v2)

Mỗi lần gửi 300 request. Số liệu gốc nằm trong [reports/](reports/).

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---:|---:|---:|---:|---:|---|
| 1 | 4.63 | 192.1 | 221.2 | 1679.5 | 1.33% | PASS |
| 10 | 38.28 | 196.1 | 226.4 | 1700.9 | 1.00% | PASS |
| 50 | 101.40 | 202.7 | 316.2 | 1707.9 | 1.00% | PASS |
| 100 | 61.64 | 379.9 | 2957.6 | 3248.0 | 0.67% | FAIL |

Trong lần chạy này, concurrency 50 cho RPS cao nhất trong bốn mức thử. Ở mức 100, p95 vượt ngưỡng 500 ms dù tỷ lệ lỗi vẫn dưới 2%. Docker cũng đang tải và build image, nên kết quả chưa đủ để xác định nút thắt.

### 2.2 Tail latency

Giữ concurrency 20, 300 request và `MOCK_ERROR_RATE=0.01`.

| `MOCK_SLOW_RATE` | Avg (ms) | p95 (ms) | p99 (ms) |
|---|---:|---:|---:|
| 0 | 195.6 | 226.3 | 245.6 |
| 0.03 (mặc định) | 229.6 | 234.1 | 1700.5 |
| 0.1 | 364.7 | 1690.6 | 1718.6 |

Khi slow rate tăng từ 0 lên 3%, avg chỉ tăng 34 ms còn p99 tăng 1454.9 ms. Ở 10%, request chậm chiếm đủ phần đuôi để p95 cũng tăng mạnh. Theo dõi p95 để đặt ngưỡng trải nghiệm và dùng p99 để phát hiện nhóm request chậm hiếm gặp.

## 3. Benchmark chất lượng

Tắt lỗi upstream mô phỏng và slow injection khi eval để đo ảnh hưởng của retrieval và thay đổi knowledge base.

| Chỉ số | Agent v1 | Agent v2 | Agent v2 sau sửa |
|---|---:|---:|---:|
| Accuracy | 1/23 (4.35%) | 21/23 (91.30%) | 23/23 (100%) |
| Avg tokens / câu | 56.3 | 109.0 | 113.5 |
| Tổng cost (USD) | 0.000394 | 0.000760 | 0.000789 |
| Cost / câu đúng (USD) | 0.00039375 | 0.00003619 | 0.00003430 |
| p95 latency eval (ms) | 183.2 | 219.4 | 213.3 |
| Quality gate | FAIL (80%) | PASS (80%) | PASS (100%, 0 regression) |

| ID | Keyword bị thiếu | Thay đổi |
|---|---|---|
| `security-02` | token, hết hạn, chữ ký | Bổ sung mục JWT và cơ chế server kiểm tra chữ ký, hạn sử dụng |
| `scaling-03` | cpu, memory, custom metrics | Bổ sung mục Kubernetes HPA và các tín hiệu autoscaling |

V2 dùng nhiều token hơn v1 và trả lời đúng nhiều câu hơn, nên chi phí trên mỗi câu đúng giảm. Khi chạy v1 với baseline v2, gate trả exit code 1 và báo 20 regression. V2 sau sửa dùng cùng baseline và đạt 0 regression.

Để dùng phép kiểm tra này trong CI, khởi động v2 với `MOCK_ERROR_RATE=0`, đợi `/health`, rồi chạy `python eval/run_eval.py --min-accuracy 0.85`. Nếu đặt job làm required status check, exit code 1 sẽ chặn merge.

## 4. Observability stack (production)

### Exercise 7.1 và 7.4

- Counter `http_requests_total` đếm request theo route, method và status. Gauge `agent_in_flight_requests` đo request đang xử lý. Histogram `http_request_duration_seconds` cho phép tính percentile qua các bucket.
- Route template và giá trị `unmatched` gom URL lạ vào một nhóm. Dùng mỗi URL làm label sẽ tạo nhiều time series, tăng RAM và làm truy vấn chậm. Metric mới `agent_question_length_chars` dùng bucket cố định để đo phân bố độ dài câu hỏi.
- Sau một lượt eval 23 câu, `/metrics` báo `agent_question_length_chars_count 23.0` và `agent_question_length_chars_sum 1066.0`.
- Golden Signals trên dashboard gồm throughput (request/s), lỗi (tỷ lệ 5xx), latency (percentile) và saturation (in-flight). Prometheus scrape trực tiếp từng agent. Grafana đọc Prometheus và Jaeger nhận span qua OTLP.

Trong lượt 30 users, ramp-up 5 users/giây, Prometheus ghi nhận p95 **296,2 ms** và avg **244,5 ms** trên cửa sổ 45 giây. p95 cao hơn trung bình khoảng 52 ms, cho thấy nhóm request chậm kéo phần đuôi lên. Hai instance nhận **8,55** và **8,47 req/s** `/ask`, gần cân bằng.

Input khoảng **1.244,6 token/s**, output khoảng **659,9 token/s**. Prompt gồm system prompt, câu hỏi và context truy xuất, còn output chỉ chứa câu trả lời. Qua Nginx, `GET /metrics` trả 404 vì cấu hình giữ endpoint này trong mạng nội bộ dành cho Prometheus.

### 4.1 Screenshot

- [Grafana khi có tải](screenshots/grafana-dashboard.png) cho thấy cả bốn Golden Signals, trong đó traffic là 44,8 req/s, error rate 1,43% và p95 703,86 ms tại thời điểm ảnh được chụp.
- [Trace chậm trong Jaeger](screenshots/jaeger-slow-trace.png) cho thấy phần lớn thời gian nằm trong span gọi mock LLM.
- [Trace lỗi trong Jaeger](screenshots/jaeger-error-trace.png) cho thấy response 503 và event `exception` trong span gọi mock LLM.
- [Trang Alerts của Prometheus](screenshots/prometheus-alert-firing.png) cho thấy `AgentHighErrorRate`, `AgentHighLatencyP95` và `LLMCostBurnRateHigh` cùng firing.

### 4.2 Thí nghiệm

| Thay đổi | Alert | Từ lúc áp dụng đến firing | Panel liên quan |
|---|---|---:|---|
| A · `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | 94,5 giây | Error rate và request 503 |
| B · `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | 154,2 giây | Latency p95/p99 |
| C · `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | Đã firing trước khi đổi model | Cost burn rate |
| D · Pause 1 instance | `AgentInstanceDown` | 43,9 giây | Instances up |
| E · `AGENT_VERSION=v1` | Các rule hiện tại không đo độ đúng | Gate v1 trả 1 và báo 20 regression | Agent version, Retrieval hit ratio và kết quả canary eval |

A và B được áp dụng cùng lúc trên ba replica để chụp được hai trạng thái firing. Thời gian đo bắt đầu ngay trước lệnh áp dụng cấu hình và kết thúc ở lần poll đầu tiên thấy firing. Nó gồm thời gian tạo lại container, bắt đầu có tải, cửa sổ PromQL, chu kỳ scrape/evaluate và `for` của rule.

Trong C, cảnh báo đã firing ở mức 4,02 USD/giờ trước khi đổi model. Sau lượt dùng model lớn, chỉ số chi phí mô phỏng là 19,15 USD/giờ. Cửa sổ 5 phút còn chứa traffic từ A và B, nên hai mẫu này chưa tách riêng được ảnh hưởng của model lên thời điểm firing.

Trong D, container bị pause vẫn có địa chỉ trong Docker DNS, nên Prometheus tiếp tục scrape và ghi `up=0`. Container được unpause sau phép đo. Trong E, `/health` qua Nginx vẫn trả `ok` với v1. Eval trên câu hỏi chuẩn mới cho thấy v1 chỉ đúng 1/23 câu.

`promtool` kiểm tra cú pháp thành công cả bốn rule và chạy file unit test với kết quả `SUCCESS`.

### 4.3 Debug bằng trace

- Trace chậm `dc16e983dd70946bef38ca82644ea523` trả HTTP 200. Tổng thời gian `POST /ask` là **1725,5 ms**. Span công việc dài nhất là `chat mock-llm-small`, **1699,4 ms (98,5%)**. Retrieval mất **19,5 ms**.
- Trace lỗi `2ec7a629ae88105ce85d8e6acbf44868` trả HTTP 503 trong **868,0 ms**. Span `chat mock-llm-small` kéo dài **843,5 ms** và có event `exception` với `utils.mock_llm.LLMError`.

```json
{"ts":"2026-11-25T10:05:44.923158+00:00","level":"INFO","service":"observable-agent","instance":"98b1bedccc25","event":"llm_call","trace_id":"dc16e983dd70946bef38ca82644ea523","span_id":"7774b5a5f006ef63","request_id":"5c477c17fa0b","model":"mock-llm-small","agent_version":"v2","input_tokens":95,"output_tokens":55,"cost_usd":4.7e-05,"llm_ms":1698.9}
{"ts":"2026-11-25T10:07:18.253765+00:00","level":"INFO","service":"observable-agent","instance":"5b9f75d52791","event":"llm_error","trace_id":"2ec7a629ae88105ce85d8e6acbf44868","span_id":"ce1431f6f2b9b9b4","request_id":"746311113475","error":"Upstream LLM error: 503 Service Unavailable (mock)"}
```

## 5. Benchmark scaling

Locust headless chạy 100 users, tăng 10 users/giây, trong 2 phút cho mỗi cấu hình. Dùng `docker compose run --no-deps` để Locust giữ nguyên số replica đã đặt. Bảng lấy dòng `POST /ask` trong hai CSV.

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---:|---:|---:|---:|---:|
| 1 | 52.09 | 210 | 1200 | 1700 | 88 / 6741 |
| 3 | 54.26 | 200 | 340 | 1700 | 73 / 7016 |

Khi tăng lên ba instance, p95 giảm từ 1200 xuống 340 ms và throughput tăng khoảng 4%. p99 vẫn ở 1700 ms, gần với độ trễ của nhóm request có slow injection. Vì Locust giữ số user và thời gian chờ cố định, mức tăng RPS ở lần chạy này chỉ mô tả workload đã thử.

File gốc [1 instance](benchmark-results/scale_1_stats.csv) và [3 instance](benchmark-results/scale_3_stats.csv).

## 6. Kết luận

1. Mức slow rate 3% thể hiện rõ ở p99. Nếu chỉ xem avg, chênh lệch chỉ là 34 ms.
2. Khi tăng số replica trong lượt Locust, p95 giảm còn p99 giữ nguyên. Trace chậm cho thấy riêng span mock LLM đã mất khoảng 1,7 giây.
3. V1 vẫn qua health check nhưng chỉ đúng 1/23 câu. Nếu triển khai thật, có thể chạy một bộ câu hỏi chuẩn định kỳ để phát hiện chất lượng giảm.

Điểm mình chú ý trong kết quả Locust là khi tăng từ 1 lên 3 replica, p95 giảm từ 1.200 xuống 340 ms, còn p99 vẫn ở 1.700 ms. Trace chậm cũng cho thấy riêng lượt gọi mock LLM đã mất khoảng 1,7 giây. Từ kết quả này, mình sẽ xem cả p95 lẫn p99 khi đánh giá việc tăng replica.
