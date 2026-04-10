# Báo Cáo Lab 7: Embedding & Vector Store

**Họ tên:** Lê Đức Anh
**Nhóm:** C401-B4
**Ngày:** 11/04/2026

---

## 1. Warm-up (5 điểm)

### Cosine Similarity (Ex 1.1)

**High cosine similarity nghĩa là gì?**
>Hai đoạn chunks có cosine similarity cao có nghĩa là 2 đoạn văn có nội dung về mặt ngữ nghĩa tương tự nhau (không mang tính từng trùng lặp từ ngữ).

**Ví dụ HIGH similarity:**
- Sentence A: "Nhiệt độ của Hà Nội của hôm nay là 39 độ C"
- Sentence B: "Hà Nội hôm nay nóng 39 độ C"
- Tại sao tương đồng: Cả 2 câu đều nói về nhiệt độ của Hà Nội vào ngày hôm nay và đều có cùng ý nghĩa.

**Ví dụ LOW similarity:**
- Sentence A: "Nhiệt độ của Hà Nội của hôm nay là 39 độ C"
- Sentence B: "Hôm nay trời mưa to"
- Tại sao khác: Cả 2 câu đều nói về thời tiết nhưng không có cùng ý nghĩa.

**Tại sao cosine similarity được ưu tiên hơn Euclidean distance cho text embeddings?**
> Euclidean distance bị ảnh hưởng nặng bởi độ dài do bản chất là khoảng cách. Trong khi cosine similarity chỉ quan tâm đến góc giữa hai vector, không quan tâm đến độ dài của chúng. Điều này làm cho cosine similarity trở nên phù hợp hơn với việc so sánh các văn bản có độ dài khác nhau.

### Chunking Math (Ex 1.2)

**Document 10,000 ký tự, chunk_size=500, overlap=50. Bao nhiêu chunks?**
> *Trình bày phép tính:* Số chunks = (10000 - 50) / 500 - 50 = 22.111
> *Đáp án:* 23 chunks

**Nếu overlap tăng lên 100, chunk count thay đổi thế nào? Tại sao muốn overlap nhiều hơn?**
> Nếu overlap tăng lên 100, số chunks sẽ giảm xuống còn 21. Lý do muốn tăng overlap là để tăng khả năng retrieval, vì khi overlap tăng, các chunks sẽ có nhiều thông tin chung hơn, giúp tăng khả năng tìm thấy thông tin liên quan.

---

## 2. Document Selection — Nhóm (10 điểm)

### Domain & Lý Do Chọn

**Domain:** Customer Support FAQ

**Tại sao nhóm chọn domain này?**
> Nhóm chọn domain này vì đây là một domain phổ biến và có nhiều tài liệu, giúp cho việc thực hành các kỹ năng chunking và retrieval trở nên dễ dàng hơn. Ngoài ra, domain này cũng có nhiều câu hỏi và câu trả lời, giúp cho việc thực hành các kỹ năng chunking và retrieval trở nên dễ dàng hơn.

### Data Inventory

| # | Tên tài liệu | Nguồn | Số ký tự | Metadata đã gán |
|---|--------------|-------|----------|-----------------|
| 1 |Thông báo Chính sách hỗ trợ Khách hàng chuyển đổi pin thuê sang pin mua các dòng xe ô tô điện VinFast Việt Nam| |2839| |
| 2 |Thông báo Chính sách ưu đãi sạc pin cho các dòng xe ô tô điện VinFast tại Việt Nam | | 2944| |
| 3 |Thông báo Chính sách bán hàng cho các dòng xe ô tô điện VinFast đã dừng sản xuất tại Việt Nam | | 3451| |
| 4 |Thông báo Chính sách hỗ trợ Khách hàng chuyển đổi từ xe xăng sang xe điện VinFast tại Việt Nam | | 1923 | |
| 5 |Thông báo Chính sách thúc đẩy bán hàng Ô tô điện VinFast tại Việt Nam | |5923 | |
| 6 | Thông báo Chính sách thúc đẩy bán hàng Ô tô điện VinFast tại Việt Nam||5895 ||

### Metadata Schema

| Trường metadata | Kiểu | Ví dụ giá trị | Tại sao hữu ích cho retrieval? |
|----------------|------|---------------|-------------------------------|
|`doc_code` | string | `20260212_ThongbaoCShotroKHchuyendoipinthuesangpinmuaotoVinFastVN` | định danh để tránh lẫn lộn |
| `effective_date` | date | `2026-02-12` | ưu tiên các chính sách, quyết định mới |
| `policy_type` | string | `sales` | lọc các chính sách theo loại |
| `model` | string | `VF3` | filter |
| `is_active`| boolean | `true` | đánh dấu chính sách còn hiệu lực |


---

## 3. Chunking Strategy — Cá nhân chọn, nhóm so sánh (15 điểm)

### Baseline Analysis

Chạy `ChunkingStrategyComparator().compare()` trên 2-3 tài liệu:

| Tài liệu | Strategy | Chunk Count | Avg Length | Preserves Context? |
|-----------|----------|-------------|------------|-------------------|
|Thông báo Chính sách thúc đẩy bán hàng Ô tô điện VinFast tại Việt Nam | FixedSizeChunker (`fixed_size`) | 39| 199.9 | Low |
|Thông báo Chính sách thúc đẩy bán hàng Ô tô điện VinFast tại Việt Nam | SentenceChunker (`by_sentences`) | 39 | 149.1 | Medium |
|Thông báo Chính sách thúc đẩy bán hàng Ô tô điện VinFast tại Việt Nam | RecursiveChunker (`recursive`) | 233 |24.1 | Low |

### Strategy Của Tôi

**Loại:** [FixedSizeChunker / SentenceChunker / RecursiveChunker / custom strategy]

**Mô tả cách hoạt động:**
> *Viết 3-4 câu: strategy chunk thế nào? Dựa trên dấu hiệu gì?*

**Tại sao tôi chọn strategy này cho domain nhóm?**
> *Viết 2-3 câu: domain có pattern gì mà strategy khai thác?*

**Code snippet (nếu custom):**
```python
# Paste implementation here
```

### So Sánh: Strategy của tôi vs Baseline

| Tài liệu | Strategy | Chunk Count | Avg Length | Retrieval Quality? |
|-----------|----------|-------------|------------|--------------------|
| | best baseline | | | |
| | **của tôi** | | | |

### So Sánh Với Thành Viên Khác

| Thành viên | Strategy | Retrieval Score (/10) | Điểm mạnh | Điểm yếu |
|-----------|----------|----------------------|-----------|----------|
| Tôi | | | | |
| [Tên] | | | | |
| [Tên] | | | | |

**Strategy nào tốt nhất cho domain này? Tại sao?**
> *Viết 2-3 câu:*

---

## 4. My Approach — Cá nhân (10 điểm)

Giải thích cách tiếp cận của bạn khi implement các phần chính trong package `src`.

### Chunking Functions

**`SentenceChunker.chunk`** — approach:
> *Viết 2-3 câu: dùng regex gì để detect sentence? Xử lý edge case nào?*

**`RecursiveChunker.chunk` / `_split`** — approach:
> *Viết 2-3 câu: algorithm hoạt động thế nào? Base case là gì?*

### EmbeddingStore

**`add_documents` + `search`** — approach:
> *Viết 2-3 câu: lưu trữ thế nào? Tính similarity ra sao?*

**`search_with_filter` + `delete_document`** — approach:
> *Viết 2-3 câu: filter trước hay sau? Delete bằng cách nào?*

### KnowledgeBaseAgent

**`answer`** — approach:
> *Viết 2-3 câu: prompt structure? Cách inject context?*

### Test Results

```
# Paste output of: pytest tests/ -v
```

**Số tests pass:** 42 / 42

---

## 5. Similarity Predictions — Cá nhân (5 điểm)

| Pair | Sentence A | Sentence B | Dự đoán | Actual Score | Đúng? |
|------|-----------|-----------|---------|--------------|-------|
| 1 | | | high / low | | |
| 2 | | | high / low | | |
| 3 | | | high / low | | |
| 4 | | | high / low | | |
| 5 | | | high / low | | |

**Kết quả nào bất ngờ nhất? Điều này nói gì về cách embeddings biểu diễn nghĩa?**
> *Viết 2-3 câu:*

---

## 6. Results — Cá nhân (10 điểm)

Chạy 5 benchmark queries của nhóm trên implementation cá nhân của bạn trong package `src`. **5 queries phải trùng với các thành viên cùng nhóm.**

### Benchmark Queries & Gold Answers (nhóm thống nhất)

| # | Query | Gold Answer |
|---|-------|-------------|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |

### Kết Quả Của Tôi

| # | Query | Top-1 Retrieved Chunk (tóm tắt) | Score | Relevant? | Agent Answer (tóm tắt) |
|---|-------|--------------------------------|-------|-----------|------------------------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

**Bao nhiêu queries trả về chunk relevant trong top-3?** __ / 5

---

## 7. What I Learned (5 điểm — Demo)

**Điều hay nhất tôi học được từ thành viên khác trong nhóm:**
> *Viết 2-3 câu:*

**Điều hay nhất tôi học được từ nhóm khác (qua demo):**
> *Viết 2-3 câu:*

**Nếu làm lại, tôi sẽ thay đổi gì trong data strategy?**
> *Viết 2-3 câu:*

---

## Tự Đánh Giá

| Tiêu chí | Loại | Điểm tự đánh giá |
|----------|------|-------------------|
| Warm-up | Cá nhân | / 5 |
| Document selection | Nhóm | / 10 |
| Chunking strategy | Nhóm | / 15 |
| My approach | Cá nhân | / 10 |
| Similarity predictions | Cá nhân | / 5 |
| Results | Cá nhân | / 10 |
| Core implementation (tests) | Cá nhân | / 30 |
| Demo | Nhóm | / 5 |
| **Tổng** | | **/ 100** |
