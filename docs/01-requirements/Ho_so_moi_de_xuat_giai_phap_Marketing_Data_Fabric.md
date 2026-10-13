# Hồ sơ nhu cầu xây dựng hệ thống dữ liệu Marketing

**Chủ đề:** Campaign Intelligence & Customer Behavior  
**Mục đích:** Mời đơn vị cung cấp khảo sát và đề xuất giải pháp dữ liệu, ứng dụng phân tích Marketing  
**Ngày:** 27/09/2026

## 1. Bối cảnh doanh nghiệp và các phòng ban

Doanh nghiệp kinh doanh bán lẻ trực tuyến nhiều nhóm sản phẩm. Marketing triển khai chiến dịch theo kênh, thời điểm và nhóm sản phẩm; CRM chăm sóc khách hàng; Bán hàng vận hành giao dịch; Tài chính quản lý chi phí và giá vốn. Ban quản lý muốn biết chiến dịch nào gắn với kết quả mua hàng, nhóm khách nào mua, sản phẩm nào bán tốt và ngân sách có được sử dụng hiệu quả hay không.

Hiện mỗi bộ phận chỉ nhìn rõ dữ liệu do mình quản lý. Để trả lời câu hỏi **“Chiến dịch vừa qua mang lại kết quả gì, với nhóm khách nào và chi phí bao nhiêu?”**, nhân sự phải lấy dữ liệu từ nhiều nơi và ghép báo cáo thủ công. Chúng tôi cần một nền dữ liệu và ứng dụng phân tích thống nhất phục vụ quyết định Marketing.

| Nhóm người dùng | Quyết định cần hỗ trợ | Vai trò |
|---|---|---|
| **UG01 — Campaign Marketing / Marketing Analyst** | Phân tích chiến dịch, kênh, sản phẩm và ưu đãi để điều chỉnh hoạt động Marketing | **Key user chính** |
| **UG02 — CRM / Customer Marketing** | Phân khúc, chọn nhóm khách mục tiêu, giữ chân và tái kích hoạt khách | **Key user** |
| **UG03 — Marketing Manager** | So sánh danh mục chiến dịch, định hướng sản phẩm và phân bổ ngân sách | **Key user ra quyết định** |
| **UG04 — Finance / Business Controller** | Đối soát ngân sách, chi phí và mức đóng góp tài chính | Nhóm phối hợp |

Bán hàng, đội vận hành website và bộ phận quản lý sản phẩm là các **chủ nguồn dữ liệu**, tham gia xác nhận định nghĩa nghiệp vụ.

## 2. Quy trình, hệ thống và dữ liệu đang có

**Quy trình hiện tại:** Marketing tạo kế hoạch chiến dịch và ưu đãi trong các ứng dụng nghiệp vụ. Hệ thống thương mại điện tử ghi nhận đơn hàng, CRM quản lý hồ sơ khách, Tài chính chốt chi phí và giá vốn. Cuối kỳ, các bộ phận xuất dữ liệu để đối chiếu bằng file. Các nguồn có tần suất cập nhật và mức chi tiết khác nhau.

| Hệ thống nguồn | Dạng nguồn và cách cập nhật | Dữ liệu chính | Chủ sở hữu |
|---|---|---|---|
| **S1 — Bán hàng trực tuyến** | **Operational database**; giao dịch và dòng hàng được cập nhật khi phát sinh | Khách, đơn, ngày mua, SKU, category, số lượng, giá, trạng thái coupon | Bán hàng |
| **S2 — CRM** | **Database riêng**; hồ sơ cập nhật theo hoạt động chăm sóc khách | ID khách, địa điểm, thời gian gắn bó, thuộc tính khách | CRM |
| **S3 — Quản lý chiến dịch** | **Ứng dụng nghiệp vụ cung cấp API**; cập nhật chiến dịch, mục tiêu và quy tắc ghi nhận kết quả | Campaign ID, kênh, kỳ chạy, mục tiêu, ngân sách, liên kết kết quả với đơn | Marketing |
| **S4 — Quản lý ưu đãi** | **API**; công bố kế hoạch coupon theo tháng và category | Mã coupon, mức giảm, category, tháng | Marketing |
| **S5 — Quảng cáo và chi phí** | **API nền tảng quảng cáo** trả chi phí campaign theo ngày; **CSV của Tài chính** tổng hợp chi tiêu online/offline | Chi phí campaign, tổng chi phí ngày, khoản chưa phân bổ | Marketing, Tài chính |
| **S6 — Sản phẩm / ERP** | **Database danh mục**; cập nhật thông tin SKU và giá vốn theo kỳ | SKU, category, giá vốn tham chiếu | Sản phẩm, Tài chính |
| **S7 — Danh mục thuế** | **Excel tham chiếu** có quản lý phiên bản | GST theo category | Tài chính |

Trước mắt, dữ liệu cần tiếp nhận từ **database, API và file theo lô**. Chưa có yêu cầu bắt buộc về streaming; nhà cung cấp có thể đề xuất nếu xác định được trường hợp kinh doanh cần xử lý tức thời. **Phụ lục A** chỉ ra file Excel tương ứng để dựng từng nguồn và kiểm thử tích hợp.

## 3. Vấn đề hiện tại và ảnh hưởng đến kinh doanh

| Vấn đề | Biểu hiện | Ảnh hưởng |
|---|---|---|
| **Không có góc nhìn chiến dịch thống nhất** | Giao dịch ban đầu không có Campaign ID; chi phí ban đầu chỉ tổng hợp theo ngày và online/offline. Thông tin chiến dịch, đơn và chi phí nằm ở các hệ thống khác nhau. | Marketing khó biết chiến dịch gắn với bao nhiêu đơn, khách và mặt hàng; quản lý khó so sánh hiệu suất theo kênh. |
| **Chưa hiểu hành vi mua theo nhóm khách** | Hồ sơ ở CRM, lịch sử mua ở Sales; khóa định danh và thời điểm chốt báo cáo chưa thống nhất. | Khó nhận diện khách mua lần đầu, khách quay lại, khách giá trị cao hoặc lâu chưa mua để chọn hướng chăm sóc. |
| **Số đơn và giá trị có thể không khớp** | **1.319 `Transaction_ID` xuất hiện ở nhiều khách**; 25.061 mã giao dịch nhưng 26.631 cặp khách–mã. Chưa rõ công thức doanh thu sau ưu đãi và hoàn trả. | Dễ đếm sai số đơn, tần suất mua, giá trị theo chiến dịch; các phòng ban công bố số khác nhau. |
| **Ưu đãi khó đối chiếu** | **400 dòng bán hàng** không nối được kế hoạch coupon theo tháng–category; **126 dòng** trong đó có trạng thái `Used`. Không có mã coupon thực dùng và số tiền giảm trên dòng bán hàng. | Không giải thích đầy đủ tác dụng ưu đãi hoặc tính được tiền giảm thực tế. |
| **Chi phí và kết quả khác mức chi tiết** | Chi phí theo ngày/campaign, doanh số theo dòng hàng, mục tiêu theo chiến dịch; chi phí campaign nằm trong tổng chi phí online. | Nối sai mức hoặc cộng hai lần chi phí làm sai chỉ số hiệu suất và quyết định ngân sách. |
| **Thiếu định nghĩa và dấu vết dùng chung** | Bộ phận tự xuất file và tính chỉ số; thay đổi sau kỳ báo cáo khó truy lại. | Tốn thời gian đối soát, khó giải thích vì sao hai báo cáo khác nhau. |

Dữ liệu hiện có chưa đủ để chứng minh **doanh thu tăng thêm do quảng cáo**, xác định khách mới trước toàn bộ lịch sử doanh nghiệp hoặc tính **lợi nhuận ròng**. Báo cáo phải thể hiện rõ phạm vi và công thức của từng chỉ số.

## 4. Mục tiêu cải thiện và các tính năng mong muốn

Chúng tôi cần hệ thống tiếp nhận dữ liệu từ các nguồn, thống nhất định danh và chỉ số, phát hiện ngoại lệ, sau đó cung cấp báo cáo để Marketing, CRM và Finance cùng sử dụng. Người dùng phải xem được từ kết quả chiến dịch xuống đơn hàng, sản phẩm và nguồn chi phí.

| Mã | Tính năng cần có | Người dùng | Ưu tiên |
|---|---|---|---|
| **BR01** | Tổng quan chiến dịch: số đơn, số khách mua, giá trị hàng được gắn và giá trị đơn trung bình theo kỳ. | UG01 | **P1** |
| **BR02** | So sánh kết quả giữa chiến dịch, kênh và các kỳ có cùng định nghĩa chỉ số. | UG01, UG03 | **P1** |
| **BR03** | Xem SKU/category bán chạy và xu hướng tăng giảm theo thời gian, có lọc theo chiến dịch. | UG01 | **P1** |
| **BR04** | So sánh các trạng thái coupon `Used`, `Not Used`, `Clicked` và hiển thị phần không đối chiếu được. | UG01, UG02 | **P2** |
| **BR05** | Phân khúc RFM theo lần mua gần nhất, tần suất và giá trị mua tại ngày chốt. | UG02 | **P1** |
| **BR06** | Xem khách mua lần đầu trong lịch sử quan sát và khách quay lại theo chiến dịch. | UG01, UG02 | **P1** |
| **BR07** | Theo dõi tỷ lệ, thời gian và giá trị mua tiếp sau chiến dịch trên cửa sổ quan sát tương đương. | UG02 | **P2** |
| **BR08** | Lập nhóm khách mục tiêu theo phân khúc, category đã mua và lịch sử mua để lên kế hoạch chiến dịch. | UG02, UG01 | **P1** |
| **BR09** | Tìm nhóm khách từng mua thường xuyên hoặc giá trị cao nhưng lâu chưa quay lại. | UG02 | **P2** |
| **BR10** | Theo dõi ngân sách, chi phí, tỷ lệ giá trị hàng được gắn/chi phí và chi phí trên mỗi đơn được gắn. | UG04, UG03 | **P1** |
| **BR11** | Ước tính giá trị hàng của các đơn được gắn trừ giá vốn tham chiếu và chi phí chiến dịch, nêu các khoản chưa có. | UG04, UG03 | **P2** |
| **BR12** | Đánh giá mức đạt mục tiêu của chiến dịch để hỗ trợ quyết định tiếp tục, điều chỉnh hoặc dừng. | UG03 | **P1** |

**P1** ưu tiên nghiệm thu trước; **P2** tiếp tục trong cùng dự án khi chỉ số nền đã được thống nhất. Hệ thống còn cần cho biết chủ sở hữu, thời điểm cập nhật, chất lượng và nguồn gốc từng chỉ số. Nhà cung cấp cần giải thích năng lực nào trong kiến trúc đề xuất trực tiếp giải quyết các vấn đề dữ liệu phân tán nêu trên.

## 5. Phạm vi, ràng buộc và tiêu chí nghiệm thu

Phạm vi đề xuất gồm khảo sát nguồn; thiết kế cách tiếp nhận DB/API/file; thống nhất khóa khách, đơn, chiến dịch và category; quản lý chất lượng, metadata, lineage; xây dựng dữ liệu dùng chung và ứng dụng phân tích cho bốn nhóm người dùng. Nhà cung cấp trình bày công nghệ, cách vận hành, nhân lực, tiến độ, chi phí và các quy tắc nghiệp vụ cần doanh nghiệp xác nhận.

**Ràng buộc:** Giá trị hàng gắn với chiến dịch theo quy tắc ghi nhận **không đồng nghĩa doanh thu tăng thêm do quảng cáo**. Tỷ lệ giá trị hàng/chi phí chưa phải ROAS dựa trên doanh thu thuần; mức đóng góp ước tính chưa phải lợi nhuận ròng. Danh sách khách BR08 dùng cho lập kế hoạch; muốn gửi liên hệ cần dữ liệu quyền nhận Marketing và quy trình phê duyệt. AI hỗ trợ diễn giải kết quả và đề xuất chiến dịch là tính năng mở rộng sau khi các chỉ số nền được chốt.

| Mã | Tiêu chí nghiệm thu |
|---|---|
| **AC01 — Tiếp nhận** | Đối chiếu được dữ liệu bán hàng, khách, coupon, chi phí và thuế với nguồn nhận ban đầu; không sửa đè bản nguồn. |
| **AC02 — Định danh** | Số đơn theo khóa được phê duyệt; mã giao dịch trùng giữa khách và dòng coupon không nối được xuất hiện trong danh sách ngoại lệ. |
| **AC03 — Nghiệp vụ** | Bốn nhóm người dùng kiểm thử được 12 BR; mỗi số tổng hợp đối chiếu được với dữ liệu chi tiết và công thức đã duyệt. |
| **AC04 — Chi phí** | Chi phí campaign không cộng trùng tổng chi phí online; xem được phần đã phân bổ và chưa phân bổ theo ngày. |
| **AC05 — Cập nhật, truy vết** | Thay đổi một khoản chi hoặc chiến dịch làm mới đúng kết quả liên quan; có nguồn, thời điểm và phiên bản để kiểm tra. |
| **AC06 — Quyền sử dụng** | Nhóm người dùng thấy dữ liệu phù hợp vai trò; không xuất danh sách liên hệ khách khi chưa có quyền nhận Marketing. |
| **AC07 — Vận hành** | Có quy trình nạp lại, cảnh báo lỗi, xử lý ngoại lệ và đo thời gian làm mới/phản hồi trên môi trường đã thống nhất. |

Hồ sơ phản hồi của nhà cung cấp cần có **bảng đáp ứng BR01–BR12**, sơ đồ nguồn và luồng dữ liệu, cách chứng minh AC01–AC07, các điểm cần xác nhận sau khảo sát, kế hoạch triển khai và báo giá.

## Phụ lục A — Ánh xạ hệ thống nguồn và file dữ liệu mẫu

Các file dưới đây là **dữ liệu mẫu để nạp vào từng hệ thống nguồn và kiểm thử kết nối**. Hệ thống cung cấp DB, API hoặc file theo đúng giao diện nêu ở mục 2.

| Hệ thống nguồn | File Excel / sheet tương ứng | Gốc dữ liệu và lưu ý |
|---|---|---|
| **S1 — Sales DB** | `01_Sales_Operational.xlsx` → `Sales_Lines` | Bổ sung ID dòng, ID đơn kỹ thuật và ngày ISO để đối chiếu. |
| **S2 — CRM DB** | `02_CRM_Customers.xlsx` → `Customers` | Giữ nguyên các trường nghiệp vụ trong bộ dữ liệu bàn giao. |
| **S3 — Campaign API** | `03_Marketing_Campaigns.xlsx` → `Campaigns`, `Targets`, `Attribution` | Thông tin chiến dịch, mục tiêu và bảng gắn đơn với chiến dịch; `Attribution` không phải log quảng cáo đã hiển thị hoặc được nhấp. |
| **S4 — Promotion API** | `03_Marketing_Campaigns.xlsx` → `Coupon_Plan` | Kế hoạch coupon theo tháng–category. |
| **S5 — Ad API / Finance CSV** | `04_Finance_Costs.xlsx` → `Campaign_Spend`, `Daily_Spend`, `Spend_Recon` | Gồm chi phí online và bảng phân bổ chi phí chiến dịch; phần campaign là một phần tổng online. |
| **S6 — Product/ERP DB** | `04_Finance_Costs.xlsx` → `Product_Costs` | Giá vốn tham chiếu theo SKU; cần thay bằng số liệu kế toán trước khi tính lợi nhuận thật. |
| **S7 — Tax Excel** | `04_Finance_Costs.xlsx` → `Tax_Rates` | Mức GST theo category. |

`00_Data_Guide.xlsx` ghi khóa nối, quy ước và giới hạn của bộ dữ liệu mẫu. Khi tiếp nhận, nhà cung cấp cần xác định bảng nào là nguồn nghiệp vụ và bảng nào là kết quả đối sánh/tính toán để tránh vòng lặp và cộng trùng khi triển khai.
