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
| 1 | battery_0326 | https://vinfastauto.com/vn_vi/hop-dong-va-chinh-sach | 2839 | {"doc_code": "POL_BATT_0326", "effective_date": "2026-03-01", "policy_type": "battery", "model": "All EVs", "is_active": true} |
| 2 | charging_ev_0326 | https://vinfastauto.com/vn_vi/hop-dong-va-chinh-sach | 2944 | {"doc_code": "POL_CHAR_0326", "effective_date": "2026-03-01", "policy_type": "charging", "model": "All EVs", "is_active": true} |
| 3 | discontinued_models_0326 | https://vinfastauto.com/vn_vi/hop-dong-va-chinh-sach | 3451 | {"doc_code": "POL_DISC_0326", "effective_date": "2026-03-01", "policy_type": "support", "model": "Fadil, Lux", "is_active": true} |
| 4 | gas_to_ev_0326 | https://vinfastauto.com/vn_vi/hop-dong-va-chinh-sach | 1923 | {"doc_code": "PROMO_GAS2EV_0326", "effective_date": "2026-03-01", "policy_type": "promotion", "model": "All EVs", "is_active": true} |
| 5 | sales_0326 | https://vinfastauto.com/vn_vi/hop-dong-va-chinh-sach | 5923 | {"doc_code": "REP_SALES_0326", "effective_date": "2026-03-01", "policy_type": "sales", "model": "All", "is_active": false} |
| 6 | sales_0426 | https://vinfastauto.com/vn_vi/hop-dong-va-chinh-sach | 5895 | {"doc_code": "REP_SALES_0426", "effective_date": "2026-04-01", "policy_type": "sales", "model": "All", "is_active": true} |

### Metadata Schema

| Trường metadata | Kiểu | Ví dụ giá trị | Tại sao hữu ích cho retrieval? |
|----------------|------|---------------|-------------------------------|
|`doc_code` | string | `POL_BATT_0326` | định danh để tránh lẫn lộn |
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

**Loại:** RecursiveChunker

**Mô tả cách hoạt động:**
> RecursiveChunker hoạt động bằng cách chia nhỏ văn bản thành các đoạn nhỏ hơn dựa trên các ký tự phân tách. Nó bắt đầu với các ký tự phân tách cấp cao nhất, chẳng hạn như dòng trống, sau đó chuyển sang các ký tự phân tách cấp thấp hơn, chẳng hạn như dấu chấm câu, để chia nhỏ văn bản thành các đoạn nhỏ hơn. Nó cũng sử dụng các ký tự phân tách cấp thấp hơn, chẳng hạn như dấu chấm câu, để chia nhỏ văn bản thành các đoạn nhỏ hơn.

**Tại sao tôi chọn strategy này cho domain nhóm?**
> Vì bài toán của nhóm là về các chính sách, quyết định của VinFast, nên việc chunking theo theo strategy tách tuần tự của recursive sẽ giúp các chunks đảm bảo giữ được context.

### So Sánh: Strategy của tôi vs Baseline

| Tài liệu | Strategy | Chunk Count | Avg Length | Retrieval Quality? |
|-----------|----------|-------------|------------|--------------------|
| Thông báo Chính sách thúc đẩy bán hàng Ô tô điện VinFast tại Việt Nam | SentenceChunker (`by_sentences`) - best baseline | 39 | 149.1 | Medium-High |
| Thông báo Chính sách thúc đẩy bán hàng Ô tô điện VinFast tại Việt Nam | **RecursiveChunker (của tôi)** | 233 | 24.1 | Medium |

### So Sánh Với Thành Viên Khác

| Thành viên | Strategy | Retrieval Score (/10) | Điểm mạnh | Điểm yếu |
|-----------|----------|----------------------|-----------|----------|
| Tôi | RecursiveChunker (có tối ưu chunk + batch embedding) | 6/10 | - Top-3 retrieval đạt 5/5 query có chunk liên quan <br> - Bắt được đúng tài liệu nguồn cho các câu hỏi policy/sạc/pin | - Chunk còn khá nhỏ nên một số câu trả lời thiếu số liệu cụ thể <br> - Đôi lúc LLM trả lời an toàn kiểu "không đủ ngữ cảnh" dù thông tin nằm rải rác ở nhiều chunk |
| Trang |FixedSizeChunker |8/10 |- Giữ được context giữa các chunk nhờ overlap <br> - Cải thiện độ chính xác retrieval so với không overlap | - Tăng số lượng chunk → tốn tài nguyên hơn <br> - Có thể lặp lại thông tin |
| Chi | RecursiveChunker | 8/10 | Lấy trọn vẹn ngữ cảnh của từng tính năng. Vượt qua 80% bài test thực tế, cung cấp dữ liệu cực chuẩn cho AI mà không bị lẫn lộn thông số. | Sẽ hơi dư thừa text một chút nếu người dùng chỉ hỏi một câu rất ngắn gọn (như chỉ hỏi về giá). |

**Strategy nào tốt nhất cho domain này? Tại sao?**
> Với domain này, recursive strategy tìm những điểm ngắt tự nhiên để cắt mà không làm nát ngữ nghĩa của văn bản. Đặc biệt bởi policy ảnh hưởng trực tiếp tới quyền lợi của khách hàng, cũng như sự phát triển của doanh nghiệp, không được hiểu nhầm thông tin.

---

## 4. My Approach — Cá nhân (10 điểm)

### Chunking Functions

**`SentenceChunker.chunk`** — approach:
> Hàm tách văn bản thành câu bằng regex theo các dấu kết câu (`.`, `!`, `?`) và xuống dòng, sau đó gom theo từng nhóm `max_sentences_per_chunk`. Cách này giúp mỗi chunk giữ được mạch ý ở mức câu, thay vì cắt cứng theo số ký tự. Cuối cùng mình `strip()` để làm sạch khoảng trắng trước khi đưa vào embedding.
**`RecursiveChunker.chunk` / `_split`** — approach:
> `chunk()` gọi `_split()` đệ quy với thứ tự separator từ mức lớn đến nhỏ (`\n\n` → `\n` → `. ` → ` ` → `""`). Ở mỗi mức, đoạn văn sẽ được `split` theo separator hiện tại, rồi từng mảnh tiếp tục đệ quy với danh sách separator còn lại. Base case là khi độ dài đoạn `<= chunk_size` hoặc đã hết separator, lúc đó trả về luôn đoạn hiện tại.

### EmbeddingStore

**`add_documents` + `search`** — approach:
> `add_documents` tạo vector embedding cho nội dung từng document/chunk rồi lưu vào store dưới dạng record gồm `id`, `content`, `embedding`, `metadata`; nếu embedder có `embed_many` thì chạy theo batch để giảm số request. `search` embed câu hỏi thành query vector, tính cosine similarity với toàn bộ vector đã lưu, sau đó sort giảm dần theo điểm. Kết quả trả về là top-k record có score cao nhất.

**`search_with_filter` + `delete_document`** — approach:
> `search_with_filter` lọc metadata trước (exact match theo từng key-value trong `metadata_filter`), rồi mới tính similarity trên tập đã lọc để kết quả đúng ngữ cảnh hơn. Cách này giảm nhiễu vì không phải so sánh với toàn bộ chunk trong kho. `delete_document` xóa record theo `id` bằng list comprehension và trả về `True/False` để báo có xóa được dữ liệu hay không.

### KnowledgeBaseAgent

**`answer`** — approach:
> Trong `answer`, agent gọi `store.search(question, top_k)` để lấy các chunk liên quan nhất trước. Sau đó mình nối nội dung các chunk thành phần `Context`, rồi tạo prompt theo khung `Context -> Question -> Answer`. Prompt này được truyền vào `llm_fn` để sinh câu trả lời bám trên ngữ cảnh đã truy xuất.

### Test Results

```
tests/test_solution.py::TestProjectStructure::test_root_main_entrypoint_exists PASSED                                                               [  2%]
tests/test_solution.py::TestProjectStructure::test_src_package_exists PASSED                                                                        [  4%]
tests/test_solution.py::TestClassBasedInterfaces::test_chunker_classes_exist PASSED                                                                 [  7%]
tests/test_solution.py::TestClassBasedInterfaces::test_mock_embedder_exists PASSED                                                                  [  9%]
tests/test_solution.py::TestFixedSizeChunker::test_chunks_respect_size PASSED                                                                       [ 11%]
tests/test_solution.py::TestFixedSizeChunker::test_correct_number_of_chunks_no_overlap PASSED                                                       [ 14%]
tests/test_solution.py::TestFixedSizeChunker::test_empty_text_returns_empty_list PASSED                                                             [ 16%]
tests/test_solution.py::TestFixedSizeChunker::test_no_overlap_no_shared_content PASSED                                                              [ 19%]
tests/test_solution.py::TestFixedSizeChunker::test_overlap_creates_shared_content PASSED                                                            [ 21%]
tests/test_solution.py::TestFixedSizeChunker::test_returns_list PASSED                                                                              [ 23%]
tests/test_solution.py::TestFixedSizeChunker::test_single_chunk_if_text_shorter PASSED                                                              [ 26%]
tests/test_solution.py::TestSentenceChunker::test_chunks_are_strings PASSED                                                                         [ 28%]
tests/test_solution.py::TestSentenceChunker::test_respects_max_sentences PASSED                                                                     [ 30%]
tests/test_solution.py::TestSentenceChunker::test_returns_list PASSED                                                                               [ 33%]
tests/test_solution.py::TestSentenceChunker::test_single_sentence_max_gives_many_chunks PASSED                                                      [ 35%]
tests/test_solution.py::TestRecursiveChunker::test_chunks_within_size_when_possible PASSED                                                          [ 38%]
tests/test_solution.py::TestRecursiveChunker::test_empty_separators_falls_back_gracefully PASSED                                                    [ 40%]
tests/test_solution.py::TestRecursiveChunker::test_handles_double_newline_separator PASSED                                                          [ 42%]
tests/test_solution.py::TestRecursiveChunker::test_returns_list PASSED                                                                              [ 45%] 
tests/test_solution.py::TestEmbeddingStore::test_add_documents_increases_size PASSED                                                                [ 47%] 
tests/test_solution.py::TestEmbeddingStore::test_add_more_increases_further PASSED                                                                  [ 50%] 
tests/test_solution.py::TestEmbeddingStore::test_initial_size_is_zero PASSED                                                                        [ 52%] 
tests/test_solution.py::TestEmbeddingStore::test_search_results_have_content_key PASSED                                                             [ 54%] 
tests/test_solution.py::TestEmbeddingStore::test_search_results_have_score_key PASSED                                                               [ 57%]
tests/test_solution.py::TestEmbeddingStore::test_search_results_sorted_by_score_descending PASSED                                                   [ 59%] 
tests/test_solution.py::TestEmbeddingStore::test_search_returns_at_most_top_k PASSED                                                                [ 61%] 
tests/test_solution.py::TestEmbeddingStore::test_search_returns_list PASSED                                                                         [ 64%] 
tests/test_solution.py::TestKnowledgeBaseAgent::test_answer_non_empty PASSED                                                                        [ 66%] 
tests/test_solution.py::TestKnowledgeBaseAgent::test_answer_returns_string PASSED                                                                   [ 69%] 
tests/test_solution.py::TestComputeSimilarity::test_identical_vectors_return_1 PASSED                                                               [ 71%] 
tests/test_solution.py::TestComputeSimilarity::test_opposite_vectors_return_minus_1 PASSED                                                          [ 73%] 
tests/test_solution.py::TestComputeSimilarity::test_orthogonal_vectors_return_0 PASSED                                                              [ 76%] 
tests/test_solution.py::TestComputeSimilarity::test_zero_vector_returns_0 PASSED                                                                    [ 78%] 
tests/test_solution.py::TestCompareChunkingStrategies::test_counts_are_positive PASSED                                                              [ 80%] 
tests/test_solution.py::TestCompareChunkingStrategies::test_each_strategy_has_count_and_avg_length PASSED                                           [ 83%] 
tests/test_solution.py::TestCompareChunkingStrategies::test_returns_three_strategies PASSED                                                         [ 85%] 
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_filter_by_department PASSED                                                        [ 88%] 
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_no_filter_returns_all_candidates PASSED                                            [ 90%] 
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_returns_at_most_top_k PASSED                                                       [ 92%] 
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_reduces_collection_size PASSED                                                [ 95%]
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_returns_false_for_nonexistent_doc PASSED                                      [ 97%] 
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_returns_true_for_existing_doc PASSED                                          [100%]
```

**Số tests pass:** 42 / 42

---

## 5. Similarity Predictions — Cá nhân (5 điểm)

| Pair | Sentence A | Sentence B | Dự đoán | Actual Score | Đúng? |
|------|-----------|-----------|---------|--------------|-------|
| 1 | VinFast hỗ trợ sạc miễn phí đến 30/06/2027. | Ưu đãi sạc pin được áp dụng tới hết ngày 30/06/2027. | high | 0.2035 | Đúng |
| 2 | VF 9 được giảm giá 250 triệu trong chương trình. | Ưu đãi cho VF 9 là giảm giá 250.000.000 VNĐ. | high | 0.0728 | Sai |
| 3 | Khách hàng mua VF 8 ngày 15/02/2026 được ưu đãi sạc. | Pin thuê của VF e34 Gotion có giá 90 triệu. | low | 0.0355 | Đúng |
| 4 | Chương trình đổi xe xăng sang xe điện kết thúc 30/4/2026. | VinFast dừng chương trình chuyển đổi vào cuối tháng 4/2026. | high | 0.0128 | Sai |
| 5 | VinFast hỗ trợ đổi xe máy điện cũ sang VF 3. | Chính sách chỉ hỗ trợ đổi từ xe xăng sang xe điện. | low | -0.1442 | Đúng |


---

## 6. Results — Cá nhân (10 điểm)
### Benchmark Queries & Gold Answers (nhóm thống nhất)

| # | Query | Gold Answer |
|---|-------|-------------|
| 1 |Chương trình thu xăng đổi điện kết thúc vào ngày nào?"|30/4/2026|
| 2 |Tôi muốn mua lại pin thuê của xe VF e34 loại Gotion, giá năm 2025 là bao nhiêu?| 90.000.000 VND|
| 3 |Tôi mua xe VF 8 ngày 15/02/2026 thì được ưu đãi sạc pin như thế nào? |10 lần/tháng |
| 4 |VinFast có hỗ trợ đổi xe máy điện cũ sang ô tô điện VF 3 không? |Không, chỉ xe xăng được đổi |
| 5 |Ưu đãi giảm giá cho xe VF 9 sản xuất năm 2023 là bao nhiêu? |250.000.000 VNĐ |

### Kết Quả Của Tôi

| # | Query | Top-1 Retrieved Chunk (tóm tắt) | Score | Relevant? | Agent Answer (tóm tắt) |
|---|-------|--------------------------------|-------|-----------|------------------------|
| 1 | Chương trình thu xăng đổi điện kết thúc vào ngày nào? | Chunk nói về thời gian áp dụng đến hết 30/4/2026 và mốc dừng chương trình chuyển đổi. | 0.7383 | Partial | Agent trả lời không đủ ngữ cảnh để kết luận chắc chắn. |
| 2 | VinFast có hỗ trợ đổi xe máy điện cũ sang ô tô điện VF 3 không? | Chunk nêu rõ chính sách hỗ trợ chuyển đổi từ xe xăng sang xe điện VinFast. | 0.8338 | Yes | Agent trả lời không thấy thông tin hỗ trợ đổi xe máy điện cũ sang VF 3 trong ngữ cảnh. |
| 3 | Tôi muốn mua lại pin thuê của xe VF e34 loại Gotion, giá năm 2025 là bao nhiêu? | Chunk chứa nội dung về chính sách mua lại pin thuê và bảng giá theo loại pin. | 0.7611 | Yes | Agent xác nhận chính sách có hiệu lực trong 2025 nhưng chưa trích ra được giá cụ thể của VF e34 Gotion. |
| 4 | Ưu đãi giảm giá cho xe VF 9 sản xuất năm 2023 là bao nhiêu? | Chunk dạng bảng có mức giảm cho VF 9 Eco/VF 9 Plus. | 0.8399 | Yes | Agent nêu các mức giảm của VF 9 nhưng nói chưa có thông tin tách riêng theo năm sản xuất 2023. |
| 5 | Tôi mua xe VF 8 ngày 15/02/2026 thì được ưu đãi sạc pin như thế nào? | Chunk nêu khách mua xe từ 10/02/2026 được áp dụng ưu đãi sạc đến 30/06/2027. | 0.8123 | Yes | Agent trả lời rõ lộ trình ưu đãi sạc: đến 30/06/2027 do VinFast chi trả, sau đó đến 10/02/2029 do ông Phạm Nhật Vượng chi trả. |

**Bao nhiêu queries trả về chunk relevant trong top-3?** 5 / 5

---

## 7. What I Learned (5 điểm — Demo)

**Điều hay nhất tôi học được từ thành viên khác trong nhóm:**
> Tối ưu hóa 

**Điều hay nhất tôi học được từ nhóm khác (qua demo):**
> *Viết 2-3 câu:*

**Nếu làm lại, tôi sẽ thay đổi gì trong data strategy?**
> *Viết 2-3 câu:*

---

## Tự Đánh Giá

| Tiêu chí | Loại | Điểm tự đánh giá |
|----------|------|-------------------|
| Warm-up | Cá nhân | 5 / 5 |
| Document selection | Nhóm | 8 / 10 |
| Chunking strategy | Nhóm |  14/ 15 |
| My approach | Cá nhân | 9/ 10 |
| Similarity predictions | Cá nhân | 4/ 5 |
| Results | Cá nhân | 7/ 10 |
| Core implementation (tests) | Cá nhân | 24/ 30 |
| Demo | Nhóm | 5 / 5 |
| **Tổng** | | **80/ 100** |
