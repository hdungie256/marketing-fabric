# Bộ tài liệu chia sẻ — Marketing Data Fabric Demo

Dự án này là gói chia sẻ độc lập, tập hợp các tài liệu cần thiết để thành viên dự án nắm được yêu cầu, dữ liệu mẫu, kiến trúc, thiết kế trải nghiệm và kế hoạch triển khai. Tài liệu nằm trong `docs/`, còn dữ liệu mẫu nằm trong `data/` ở thư mục gốc dự án. Các đường dẫn bên dưới được tính từ thư mục `docs/` chứa README này. Các đường dẫn như `contracts/`, `app/` hoặc `pipelines/` mô tả artifact mà team sẽ tạo trong mã nguồn, không phải tài liệu bị thiếu khỏi gói.

## Thứ tự đọc đề xuất

1. `01-requirements/Ho_so_moi_de_xuat_giai_phap_Marketing_Data_Fabric.md` — bối cảnh, nhu cầu và tiêu chí nghiệm thu.
2. `01-requirements/prd.md` — phạm vi sản phẩm và yêu cầu chức năng/phi chức năng (bản tiếng Anh).
3. `../data/Data_Description_Campaign_Intelligence.md` — tổng quan dữ liệu, khóa nối và giới hạn phân tích.
4. `../data/00_Data_Guide.xlsx` — hướng dẫn chi tiết về nguồn, quy tắc nối, giả định và mức độ hỗ trợ các yêu cầu nghiệp vụ.
5. `02-architecture/ARCHITECTURE-SPINE.md` — kiến trúc và các nguyên tắc kỹ thuật bắt buộc (bản tiếng Anh).
6. `03-ux-design/EXPERIENCE.md` và `03-ux-design/DESIGN.md` — luồng trải nghiệm và hệ thống thiết kế.
7. `04-planning/epics.md` và `04-planning/team-assignment.md` — backlog và phân công thực hiện.

## Nội dung thư mục

```text
data-fabric-marketing-project/
├── data/
│   ├── 00_Data_Guide.xlsx
│   ├── 01_Sales_Operational.xlsx
│   ├── 02_CRM_Customers.xlsx
│   ├── 03_Marketing_Campaigns.xlsx
│   ├── 04_Finance_Costs.xlsx
│   └── Data_Description_Campaign_Intelligence.md
└── docs/
    ├── README.md
    ├── 01-requirements/
    ├── 02-architecture/
    ├── 03-ux-design/
    │   └── mockups/
    └── 04-planning/
```

### `01-requirements`

- Hồ sơ nhu cầu giải pháp Marketing Data Fabric.
- PRD tiếng Anh.

### `../data`

- Tài liệu mô tả bộ dữ liệu.
- `00_Data_Guide.xlsx`: bản đồ nguồn, khóa nối, giả định, kiểm tra và phạm vi hỗ trợ business requirement.
- `01_Sales_Operational.xlsx`: dữ liệu dòng bán hàng.
- `02_CRM_Customers.xlsx`: dữ liệu khách hàng CRM.
- `03_Marketing_Campaigns.xlsx`: chiến dịch, mục tiêu, attribution và kế hoạch coupon.
- `04_Finance_Costs.xlsx`: chi tiêu, đối soát, giá vốn và thuế.

Các workbook là dữ liệu mẫu phục vụ thiết kế/demo. Cần thay dữ liệu tham chiếu bằng dữ liệu nghiệp vụ đã được xác nhận trước khi dùng để tính toán thực tế.

### `02-architecture`

- Tài liệu kiến trúc tiếng Anh, là nguồn chính thức duy nhất về tech stack của dự án.
- Bản trực quan kiến trúc dạng HTML, có thể mở trực tiếp bằng trình duyệt.

### `03-ux-design`

- Tài liệu trải nghiệm và quy chuẩn thiết kế.
- Các mockup HTML trong `mockups/`; mở trực tiếp bằng trình duyệt. Liên kết từ hai tài liệu thiết kế đến mockup vẫn giữ nguyên theo cấu trúc thư mục này.

### `04-planning`

- Danh sách epic/story và tiêu chí nghiệm thu.
- Phân công công việc, thứ tự phụ thuộc và quy tắc tránh xung đột.
- `data_fabric_task_tracker_with_dates.xlsx`: bảng theo dõi công việc và lịch thực hiện.

## Lưu ý khi chia sẻ

- Giữ nguyên cấu trúc thư mục để các liên kết tương đối tới mockup hoạt động.
- Không coi bảng `Attribution` là log quảng cáo đã hiển thị hoặc được nhấp.
- Không cộng trực tiếp chi tiêu chiến dịch với tổng online spend nếu chưa kiểm tra quy tắc đối soát trong `00_Data_Guide.xlsx`.
- `prd.md` và `ARCHITECTURE-SPINE.md` tiếng Anh là hai tài liệu chính thức về yêu cầu và kiến trúc
