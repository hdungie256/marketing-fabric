# Phân công — Marketing Data Fabric Demo

> Chi tiết story: `epics.md` · Thời gian: ~4 tuần

## 1. Vai trò

| Người | Story chính | Vai trò | Thư mục sở hữu |
|---|---:|---|---|
| **P1** | **13** | Platform | `compose/` `contracts/` `fabric_control/` `mock_api/` `governance/mappings/` `pipelines/{dags,io}` `pipelines/jobs/ingest` · `pipelines/jobs/marts/shared/exceptions` |
| **P2** | **12** | Campaign + UI shell + Demo | `pipelines/jobs/unified/{campaigns,attribution,coupon_plan,campaign_targets}` · `pipelines/jobs/marts/{campaign,shared/campaign_attributed_daily}` · `app/shell` `app/*/{campaign,changes}` · `docs/demo-script.md` |
| **P3** | **11** | Sales/Customer + Catalog + Sources | `sources/` · `pipelines/jobs/unified/{orders,order_lines,customers,products,product_cost,ref_category_map}` · `pipelines/jobs/marts/customer` · `app/*/{customer,catalog}` · trang DQ/Exceptions trong `app/*/governance` |
| **P4** | **12** | Finance + Policy + Ops + Benchmark | `pipelines/jobs/unified/campaign_spend` · `pipelines/jobs/marts/finance` và spend shared marts · `governance/{tags,access_matrix,baselines}` · các trang policy/access trong `app/*/governance` · `app/*/{finance,ops}` · `benchmark/` |

## 2. Kế hoạch phối hợp theo tuần

Story nằm ở cột **Owner chính** chỉ được tính cho người đó. Người ở cột **Phối hợp/bàn giao** chỉ sửa phần thuộc thư mục của mình và gửi PR qua contract hoặc stub đã thống nhất.

### Tuần 1 — Dựng nền và tạo dữ liệu đầu vào

| Nhịp | Owner chính | Story | Chạy sau | Phối hợp/bàn giao |
|---|---|---|---|---|
| 1. Mở khóa | P1 | **1.1** Scaffold repo + stub `fabric_control` | Bắt đầu dự án | Bàn giao skeleton, profile `dev`, contract stub và quy tắc owner cho P2–P4 |
| 2. Song song | P1 | **1.2, 1.3** Spike S1–S6 | 1.1 | Chốt storage, lineage và orchestration; công bố quyết định để các job không tự chọn cách tích hợp |
| 2. Song song | P3 | **1.4** Seed nguồn từ Excel | 1.1 + source contract stub | Bàn giao source tables/files và fault toggles cho P1 ingest |
| 2. Song song | P2 | **1.11, 1.12** Shell, login, role switcher, metric/badges | 1.1 + fixture/stub | Làm với profile `dev`; chỉ tích hợp DB thật sau khi P1 hoàn tất views ở tuần 2 |
| 3. Nối dữ liệu | P1 | **1.5** Raw ingest | 1.2–1.4 | Công bố raw contract và fixture; P3 kiểm tra seed → raw reconciliation |
| 4. Song song | P3 | **1.6** Unified sales/customer/product | 1.5 + unified contracts | P1 duyệt contract/IO, duy trì `governance/mappings/category.yml` và cung cấp fixture |
| 4. Song song | P2 | **1.7** Unified campaign/attribution/target | 1.5 + unified contracts | P4 làm `campaign_spend` trong thư mục P4; P1 duyệt contract/IO |

**Gate cuối tuần:** raw ingest chạy được; contracts của unified đã merge; 1.6 và 1.7 có transform/test độc lập; shell chạy được bằng fixture. Chưa qua gate này thì không bắt đầu shared marts.

### Tuần 2 — Hợp nhất dữ liệu, metadata và governance

| Nhịp | Owner chính | Story | Chạy sau | Phối hợp/bàn giao |
|---|---|---|---|---|
| 1. Mở khóa | P2 | **1.8** Shared campaign mart | 1.6 + 1.7 | P2 làm `campaign_attributed_daily`; P4 làm hai spend marts; P1 duyệt shared contracts/IO |
| 2. Serving | P1 | **1.9** Policy views | 1.8 + migrations của các owner | P4 bàn giao tags/access; P2 xác nhận shell nối được `*_v` |
| 2. Song song | P3 | **2.1** Glossary/tags sync | Các dataset IDs ổn định | P3 điều phối glossary; P1 làm `sync_glossary()`/`sync_tags()`; P4 duyệt tag standard |
| 3. Integration | P1 | **1.10** Bootstrap | 1.9 + sync functions/files của 2.1 | Chạy đủ migrations → tags → glossary → refresh → policies; các owner sửa lỗi trong đúng slice của mình |
| 3. Metadata | P1 | **2.2** Catalog/metadata read API | 2.1 files + offline stub | Bàn giao API ổn định cho các trang P3; P3 không sửa `fabric_control/` |
| 3. Song song | P3 | **2.3, 2.4, 2.5** Lineage, Definition, Catalog & Search | Bắt đầu bằng 2.2 stub; tích hợp sau khi 2.2 merge | P2 cung cấp shell component, P3 sở hữu page/service/repository |
| 3. Song song | P2 | **1.13** Campaign Overview | 1.8 + 1.9 + 1.12 | P3 viết reconcile test độc lập |
| 3. DQ chain | P4 | **3.1** DQ rules | Unified/shared marts đã chạy | Công bố rule standard và review `dq/*.yml` của từng job owner |
| 3. DQ chain | P1 | **3.2** DQ gate + stale state | 3.1 | Bàn giao `ops.dq_results` và trạng thái stale cho P3 |
| 3. DQ chain | P1 | **3.3** Exceptions datasets/mart | 3.2 | Bàn giao `mart_shared_v.exceptions` và baseline 1,319 · 400/126 cho P3 |
| 3. DQ chain | P3 | **3.4** DQ & Exceptions page | 3.2 + 3.3 | P3 dùng riêng `test_br14_quality.py`; P4 chỉ review rule/status semantics |
| 3. Policy chain | P4 | **3.5 → 3.6** Masking/deny rồi Access Matrix | 1.9 + tags/access matrix | P1 làm `sync_policies()`/`verify_policies()`; P4 dùng riêng `test_br14_access.py` |

**Gate cuối tuần:** bootstrap chạy idempotent; Campaign Overview đọc từ view; metadata pages dùng chung Read API; DQ và policy tests tách file, đều xanh; nghiệm thu E2E BR01, BR13, BR14 theo mục 3. Chưa qua gate này thì các slice tuần 3 chỉ được code với fixture, chưa merge integration.

### Tuần 3 — Các business slice chạy song song

| Nhịp | Owner chính | Story | Chạy sau | Phối hợp/bàn giao |
|---|---|---|---|---|
| 1. Song song | P2 | **4.1–4.4** Campaign comparison/products/customer mix/targets | Gate tuần 2 | P3 viết reconcile cho 4.1–4.3; P4 viết reconcile cho 4.4 |
| 1. Song song | P3 | **5.1–5.4** RFM/win-back/audience/export lock | Gate tuần 2 | P4 viết reconcile; P1 sở hữu `can_export()` trong `fabric_control` |
| 1. Finance trước | P4 | **6.1 → 6.2** Budget & Spend rồi Contribution | 1.8 + gate tuần 2 | P2 viết reconcile; hoàn tất contract/scope trước khi P1 bắt đầu Epic 8 |
| 2. Ops sau | P4 | **7.1 → 7.2 → 7.3 → 7.4** Status, alerts, reload, performance | 1.10 + 3.2 | P1 cung cấp DAG/run telemetry; P3 cung cấp `break-source`; P2 cung cấp alert shell component |
| 2. Song song | P1 | **8.1 → 8.2** Spend API rồi dependency resolver | Contract từ Epic 4 + Epic 6 ổn định | P4 chốt finance scope; P2 chốt campaign scope và Change History contract |

**Gate cuối tuần:** Epic 4/5/6 reconcile và E2E xanh; nghiệm thu BR02, BR03, BR05, BR06, BR08, BR09, BR10, BR11, BR12; BR15 chạy đủ gây lỗi → alert → reload → reconcile; Spend API sinh event và `affected_by` trả đúng topological order/scope.

### Tuần 4 — Partial refresh, benchmark và tổng duyệt

| Nhịp | Owner chính | Story | Chạy sau | Phối hợp/bàn giao |
|---|---|---|---|---|
| 1. Refresh chain | P1 | **8.3 → 8.4** Scoped write rồi `partial_refresh` | 8.1 + 8.2 | P2–P4 xác nhận scope/reconcile cho mart của mình; mục tiêu end-to-end < 2 phút |
| 2. Song song | P2 | **8.5 → 8.6** Spend edit/progress rồi Change History | 8.3 API ổn định; 8.4 để integration | P4 làm finance service/repository/page integration; P2 chỉ sửa shell/form/change pages |
| 2. Song song | P4 | **9.1 → 9.2 → 9.3** Spark–Flink, layer alternatives, warehouse baseline | Core stack ổn định | P3 cung cấp RFM benchmark; P1 giữ benchmark profile tách khỏi core |
| 3. Chốt cuối | P2 | **9.4** Performance report and demo readiness | 8.4–8.6 + 9.1–9.3 | P4 bàn giao kết quả; P1 cung cấp `make demo-ready`; cả nhóm chạy thử demo |

**Gate cuối dự án:** nghiệm thu E2E BR16 và hồi quy đủ 14 BR; `make test` xanh; `make demo-ready` xanh; không còn stale/alert/fault toggle; đủ SM1–SM5 và chạy trọn demo script trong 15 phút.

## 3. Lịch nghiệm thu end-to-end theo BR

Tuần 1–4 tính từ ngày khởi động dự án; chưa chốt ngày lịch cụ thể. Đây là mốc nghiệm thu mục tiêu, không phải trạng thái đã hoàn thành. Tuần 1 chỉ nghiệm thu nền tảng theo gate mục 2, chưa có BR hoàn chỉnh. BR04 và BR07 là stretch, không thuộc 14 BR cam kết và chưa có lịch nghiệm thu.

**Điều kiện chung:** chạy scenario trong PRD §8 trên stack `core` dựng bằng `docker compose`, dùng dữ liệu seed thật qua pipeline và serving views; không nghiệm thu bằng fixture/stub. Phải có bằng chứng UI, test tự động T-BR tương ứng, reconcile độc lập khi có số liệu, và `AppTest` smoke cho các trang liên quan. Trang đáp ứng < 3 giây và tuân thủ trạng thái/nhãn/quyền theo EXPERIENCE. Owner bàn giao chuẩn bị demo và bằng chứng; người kiểm tra là thành viên khác, không thay thế người nghiệm thu chính thức của môn học.

| Mốc nghiệm thu | BR | Story/phụ thuộc bắt buộc | Owner bàn giao | Kiểm tra chéo | Scenario và điều kiện đạt chính |
|---|---|---|---|---|---|
| Cuối tuần 2 | BR01 | 1.1–1.13; 2.1–2.4 để mở định nghĩa/lineage | P2 | P3 | Overview lọc campaign/period; KPI khớp truy vấn độc lập; toàn kỳ có 1,290 attributed orders; mở được lineage từ metric; T-BR01 xanh |
| Cuối tuần 2 | BR13 | 2.1–2.5; 1.9, 1.11–1.12 | P3 | P2 | Tìm “Attributed Value / Spend Ratio”; hiện định nghĩa, công thức, source columns, owner, “not ROAS” và nhãn synthetic; T-BR13 xanh |
| Cuối tuần 2 | BR14 | 3.1–3.6; 1.9; 2.2 | P3 (DQ/Exceptions) + P4 (Access Matrix) | P2 | Liệt kê 1,319 mã transaction trùng, 400 coupon-mismatch (126 Used); score/status đúng FR-7, matrix đúng FR-20; T-BR14 xanh, tách quality/access test |
| Cuối tuần 3 | BR02 | 4.1; gate tuần 2 | P2 | P3 | So sánh 5 campaign/channel cùng kỳ; cột dùng chung glossary, mở định nghĩa từ header; T-BR02 xanh |
| Cuối tuần 3 | BR03 | 4.2; gate tuần 2 | P2 | P3 | Top SKU/category lọc theo campaign khớp dữ liệu chi tiết; Nest/Nest-USA/Nest-Canada tách riêng; T-BR03 xanh |
| Cuối tuần 3 | BR05 | 5.1; gate tuần 2 | P3 | P4 | RFM as-of 2019-12-31, scoring/segment theo R18; tổng segment bằng số khách đã mua; frequency theo order_key; T-BR05 xanh |
| Cuối tuần 3 | BR06 | 4.3; gate tuần 2 | P2 | P3 | New + returning bằng số khách mua trong campaign; có nhãn “first within observed history”; T-BR06 xanh |
| Cuối tuần 3 | BR08 | 5.3–5.4; 5.1; policy và can_export() | P3 | P4 | Chọn segment/category/lịch sử mua, lưu audience thành công; export contacts bị khóa với lý do thiếu consent; T-BR08 xanh |
| Cuối tuần 3 | BR09 | 5.1–5.2; gate tuần 2 | P3 | P4 | Win-back liệt kê đủ và chỉ khách (F=5 hoặc M=5) và R=1 theo R18; masking đúng role; T-BR09 xanh |
| Cuối tuần 3 | BR10 | 6.1; 1.8; gate tuần 2 | P4 | P2 | Budget tách khỏi cost; allocated + unallocated bằng daily online cost, discrepancy 0; tỷ số đúng glossary; T-BR10 xanh |
| Cuối tuần 3 | BR11 | 6.2; 6.1; 3.5 | P4 | P2 | UG04 thấy SKU cost; đổi UG03 chỉ thấy aggregate; contribution khớp tính toán, có nhãn estimate và danh sách thiếu cost; T-BR11 xanh |
| Cuối tuần 3 | BR12 | 4.4; 4.3; 6.1; gate tuần 2 | P2 | P4 | 5 campaign so với target riêng; Continue/Adjust/Stop đúng ngưỡng FR-31; target có nhãn retrospective synthetic; T-BR12 xanh |
| Cuối tuần 3 | BR15 | 7.1–7.4; 1.10; 3.2; reload DAG và break-source | P4 | P3 | Gây lỗi nguồn → alert nêu failing step → khôi phục nguồn/reload → run thành công và row counts khớp baseline; T-BR15 xanh |
| Cuối tuần 4 | BR16 | 8.1–8.6; Epic 4 + Epic 6 đã nghiệm thu; lineage | P1 (refresh) + P2 (form/Change History), P4 phối hợp finance | P3 | UG04 sửa spend một ngày/campaign → refresh BR10/BR11/BR12 đúng scope < 2 phút; metric khác giữ timestamp; hiện progress, lineage và old/new trong Change History; T-BR16 xanh |
| Cuối tuần 4 | Hồi quy 14 BR | 9.4; mọi gate trước đã đạt | P2 điều phối, cả nhóm bàn giao | Cả nhóm kiểm tra chéo | Chạy lại đủ T-BR01–03, 05–06, 08–16; make test và make demo-ready xanh; demo script hoàn tất trong 15 phút |

**Bằng chứng mỗi buổi nghiệm thu:** ghi BR, commit/version, ngày chạy, role và bộ lọc, log test/reconcile, ảnh hoặc video scenario, người kiểm tra và kết quả đạt/chưa đạt. Chỉ cập nhật story sang `done` khi đủ Definition of Done; lịch này không tự thay đổi trạng thái backlog trong `sprint-status.yaml`.

**Nếu trượt gate:** ghi nguyên nhân và story phụ thuộc, cập nhật mốc nghiệm thu liên quan trước khi tích hợp tiếp. BR12 phải chờ BR10 và dữ liệu BR06; BR16 phải chờ campaign/finance scope ổn định. Tuần 4 dành cho BR16, hồi quy và tổng duyệt, không mặc định dồn mọi BR chưa đạt sang tuần 4.

## 4. Quy tắc không conflict

1. **Chỉ sửa thư mục của mình.** Người làm chính điều phối story; phần phối hợp = PR riêng trong thư mục của người phối hợp.
2. **Làm theo contract trước.** Schema `unified`/`mart_shared` công bố trong `contracts/` trước khi code; chưa có thì dùng stub `fabric_control` + profile `dev`.
3. **File dùng chung tách theo người:** `contracts/datasets/<slice>.yml`, `governance/glossary/<slice>.yml`, `governance/tags/<slice>.yml`, `app/pages/<slice>/registry.py`.
4. **Số migration theo dải:** P1 `001–099` · P2 `100–199` · P3 `200–299` · P4 `300–399` (tên `NNN_<owner>_<desc>.sql`).
5. **PR cần chủ duyệt:** `contracts/`, `fabric_control/`, `pipelines/io/` (P1) · `app/shell/` (P2).
6. **Reconcile test do người khác viết:** P2 → P3 · P3 → P4 · P4 → P2 · P1 → P2/P3/P4.
7. **`make test` xanh trước khi merge `main`.**
