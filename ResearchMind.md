**ResearchMind — Document Review Engine**

**Kiến trúc Đa hồ sơ & Plugin (Multi-Profile & Plugin Architecture)**

**1. Kiến trúc tổng thể (Architecture Flow)**

Hệ thống vận hành dựa trên **một engine cốt lõi duy nhất**, sử dụng cơ chế Plugin và Knowledge Pack để xử lý đa dạng các loại tài liệu mà không cần fork code theo từng định dạng.

Plaintext

[ Document Upload ]

`      `│

`      `▼

[ Document Parser ] (Bóc tách XML, metadata, text)

`      `│

`      `▼

[ Document Model ] (Chuẩn hóa cấu trúc bộ nhớ)

`      `│

`      `▼

[ Profile Detector ] (AI tự động nhận diện loại tài liệu)

`      `│

`      `▼

[ Knowledge Pack Loader ] (Nạp Plugin: IEEE, ISO 9001, Proposal...)

`      `│

`      `▼

[ Rule Engine ] (Phân lớp: Syntax -> Semantic -> Cross -> AI)

`      `│

`      `▼

[ LLM Review ] (Suy luận dựa trên Rubric & Prompt từ Pack)

`      `│

`      `▼

[ Issue Engine ] (Tạo danh sách lỗi & evidence)

`      `│

`      `├──────────────────────────┐

`      `▼                          ▼

[ Score Engine ]           [ Auto Fix ]

`      `│                          │

`      `└────────────┬─────────────┘

`                   `▼

`           `[ Report Engine ]

`                   `│

`                   `▼

`          `[ History / Export ]

**2. Mô hình phân tách cấu hình (Decoupled Configuration)**

Để tránh một file Profile Config phình to gánh vác quá nhiều logic, cấu hình được thiết kế phân rã thành các module độc lập. Kiến trúc Plugin cho phép thêm mới các tiêu chuẩn (APA, IEEE, Nature, ISO) mà không can thiệp lõi Engine.

**Cấu trúc phân rã:**

- ProfileConfig: Quản lý định tuyến và gom nhóm các module.
- CategoryConfig: Bật/tắt các hạng mục kiểm tra (Format, Logic, Terminology...).
- RubricConfig: Quy định văn phong (Academic Objective, Persuasive, Imperative).
- PermissionConfig: Giới hạn quyền can thiệp (VD: Khóa mức hỗ trợ "diễn đạt lại").
- ChecklistConfig: Quản lý các thành phần cấu trúc bắt buộc.

**Cấu trúc thư mục Plugin:**

Plaintext

plugins/

├── academic/

│   ├── packs/

│   │   ├── nature\_guideline/

│   │   ├── ieee\_standard/

│   │   └── apa\_style/

├── business/

│   ├── proposal/

│   ├── pitch\_deck/

│   └── exec\_summary/

└── sop/

`    `├── iso\_9001/

`    `└── fda\_compliance/

**3. Ma trận Profile & Hệ sinh thái Knowledge Pack**

*Lưu ý: "Journal" không còn là một Profile độc lập. Nó được xem là một biến thể của Profile Academic kết hợp với các Knowledge Pack đặc thù.*

|**Profile Gốc**|**Biến thể (Document Type)**|**Knowledge Pack / Cấu hình đặc thù**|
| :- | :- | :- |
|**Academic**|Thesis, Dissertation, Journal Article, Conference Paper|APA Pack, IEEE Pack, Nature Guideline, Elsevier Standard|
|**Business**|Business Report, Proposal, Pitch Deck, Exec Summary|Persuasive Rubric, ROI Checklist, Brand Tone Config|
|**SOP**|Manufacturing SOP, IT Procedure, Medical Protocol|ISO 9001 Pack, FDA Compliance, Imperative Tone, Safety Checklist|

**4. Chi tiết các thành phần cốt lõi**

**4.1. Lớp Categories (Mở rộng)**

Hệ thống phân tích sâu thông qua danh sách Category toàn diện:

- **Định dạng & Kỹ thuật:** Format, Technical, File Structure.
- **Ngôn ngữ & Văn phong:** Writing Style, Grammar, Spelling, Terminology, Readability.
- **Nội dung & Logic:** Structure, Logic, Consistency, Data, Figures, Tables, Equation, Compliance.
- **Học thuật:** Citation, Reference Integrity, Plagiarism.

**4.2. Phân lớp Rule Engine**

Rule Engine không chạy đồng phẳng mà xử lý theo đường ống (pipeline) từ tĩnh đến động:

1. **Syntax Rule:** Kiểm tra lỗi cơ học, cú pháp, heading, font, margin.
1. **Semantic Rule:** Bắt lỗi ngữ nghĩa cơ bản, regex, đối chiếu thuật ngữ.
1. **Cross Rule:** Kiểm tra chéo giữa các thành phần (VD: Hình ảnh có trong bài nhưng thiếu trong danh mục, Reference Integrity giữa text và bibliography).
1. **AI Rule:** Chuyển giao cho LLM đánh giá các yếu tố phức tạp (văn phong, tính logic, độ thuyết phục).

**4.3. Độc lập Score Engine**

Quá trình chấm điểm và đánh giá được tách biệt khỏi khâu phát hiện lỗi:

- **Issue Engine:** Trọng tâm duy nhất là tìm lỗi và trích xuất bằng chứng (Evidence).
- **Score Engine:** Chạy công thức chấm điểm độc lập (cho phép áp dụng trọng số khác nhau tùy thuộc vào Document Type và Knowledge Pack).
- **Recommendation & Learning Engine:** Đưa ra lộ trình sửa lỗi và lời khuyên dựa trên pattern sai sót của người dùng.

**5. Rủi ro & Điểm kiểm soát (Permission Overrides)**

**SOP Review (Compliance & Safety)**

Rủi ro cao nhất nằm ở việc AI tự ý thay đổi ngữ nghĩa quy trình.

- PermissionConfig **phải khóa cứng quyền diễn đạt lại (Paraphrase) ở mức 2**, chỉ cho phép giải thích và phát hiện lỗi.
- Bắt buộc nạp category Compliance: Kiểm tra tính mệnh lệnh rõ ràng, Cảnh báo an toàn, Bảng Revision History, và Chữ ký phê duyệt.

**Business & Proposal (Persuasiveness)**

- Áp dụng RubricConfig đảo ngược so với Academic. Hệ thống phải dùng rubric **Persuasiveness** để đánh giá tính thuyết phục, lời kêu gọi hành động (Call to Action), độ tự tin trong ngôn từ, thay vì văn phong khách quan.

**Academic & Journal (Fragmentation)**

- Được kiểm soát hoàn toàn bằng cơ chế Knowledge Pack Loader. Engine yêu cầu xác định bộ guideline (APA, IEEE, Nature...) trước khi quét để áp dụng đúng Rule về trích dẫn và template, thay vì sử dụng một profile học thuật chung chung.

**6. Schema Mẫu (YAML)**

*Minh họa cơ chế phân tách Module thay vì gom chung vào một file cấu hình:*

**1. profile\_business\_proposal.yaml (File định tuyến chính)**

YAML

id: business\_proposal

name: "Business Proposal"

base\_engine: standard\_pipeline

includes:

`  `- configs/categories/business\_extended.yaml

`  `- configs/rubrics/persuasive\_confident.yaml

`  `- configs/permissions/allow\_full\_rewrite.yaml

`  `- configs/checklists/proposal\_standard.yaml

**2. configs/rubrics/persuasive\_confident.yaml (Rubric độc lập)**

YAML

id: persuasive\_confident

rules:

`  `- avoid\_passive\_voice: true

`  `- highlight\_value\_proposition: true

`  `- measure\_confidence\_index: true

**3. configs/permissions/strict\_sop.yaml (Quyền can thiệp độc lập)**

YAML

id: strict\_sop\_override

max\_permission\_override:

`  `writing\_style: 2  # Chỉ giải thích lỗi, KHÔNG paraphrase

`  `format: 4         # Cho phép Auto-fix các lỗi kỹ thuật

**7. Thay đổi UI/UX (Luồng Nhận diện Thông minh)**

Quy trình trải nghiệm người dùng được tối ưu lại với cơ chế tự động nhận diện Document Type:

- **Bước 0 (Auto-Detect & Type Selection):** Người dùng upload tài liệu. Profile Detector phân tích nội dung và đưa ra phán đoán (VD: *"Hệ thống nhận diện đây là Báo cáo kỹ thuật. Xác nhận?"*). Người dùng có thể xác nhận hoặc tự chọn loại tài liệu khác.
- **Bước 1 (Knowledge Pack):** Nếu là Academic, hệ thống yêu cầu: *"Chọn Journal/Citation Guideline (Nature, IEEE, APA...)"*. Nếu là SOP, chọn *"Tiêu chuẩn ISO 9001, FDA..."*.
- **Bước 2 (Chế độ kiểm tra):** Hiển thị danh mục (Categories) đã được tinh chỉnh theo Plugin. Các giới hạn mức hỗ trợ (Permission) tự động vô hiệu hóa các nút không hợp lệ (VD: SOP sẽ ẩn nút "Diễn đạt lại").
- **Bước 3 (Review Report):** Hiển thị danh sách Issue, Evidence và Score dựa trên Engine tương ứng.

**8. Ngôn ngữ & Công nghệ đề xuất**

|**Lớp hệ thống**|**Đề xuất**|**Lý do**|
| :- | :- | :- |
|**Backend Core**|**Python** (FastAPI, python-docx, lxml)|Tối ưu cho I/O-bound, phân tích XML docx toàn diện nhất, đồng nhất stack với LLM fallback chain, dễ maintain mở rộng.|
|**Cấu hình (Config)**|**YAML**|Cấu trúc phân rã tốt, hỗ trợ comment, dễ đọc với con người, thích hợp để non-dev thiết lập Knowledge Pack sau này.|
|**Desktop Shell**|**Rust** (Tauri)|Chỉ dùng làm shell desktop để quản lý window, giao tiếp hệ thống cục bộ, tối ưu dung lượng và bảo mật.|
|**Frontend UI**|**TypeScript / React**|Phù hợp xử lý state phức tạp của UI đa hồ sơ, đồng nhất với kiến trúc Frontend hiện tại của Tauri.|

