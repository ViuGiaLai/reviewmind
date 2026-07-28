Mình nghĩ UI của tài liệu này còn có thể nâng cấp rất nhiều. Thay vì chỉ mô tả chức năng, bạn nên bổ sung một chương **"UI/UX Design Specification"** để khi lập trình hoặc thiết kế Figma sẽ không phải suy nghĩ lại.

-----
**1. Profile Selection (Bước 0)**

Thay vì card đơn giản, dùng **Visual Card**.

┌──────────────────────────────┐

🎓 Academic Review

──────────────────────────────

✔ Citation

✔ Academic Writing

✔ Structure

✔ Reference

Best for:

Thesis, Paper, Dissertation

`          `[ Select ]

Mỗi profile có:

- Icon
- Mô tả
- Category sẽ dùng
- Estimated time
- Recommended for
-----
**2. Capability Preview**

Sau khi chọn Profile

Hiện ngay

ResearchMind sẽ kiểm tra

✓ Structure

✓ Citation

✓ Writing

✓ Grammar

✓ Figures

✓ Tables

Không kiểm tra

✕ Compliance

✕ Safety

Người dùng biết AI sẽ làm gì.

-----
**3. AI Permission Matrix**

Thay vì chỉ có nút.

Làm thành bảng.

Category          Detect Explain Suggest Rewrite

Structure          ✓       ✓        ✓        ✕

Citation           ✓       ✓        ✕        ✕

Writing            ✓       ✓        ✓        ✓

Grammar            ✓       ✓        ✓        Auto

Rất dễ hiểu.

-----
**4. Knowledge Pack**

Nếu Academic

Academic

──────────────

Style

○ APA 7

○ IEEE

● ACM

○ Nature

○ Springer

Nếu SOP

ISO 9001

FDA

WHO

Hospital SOP

Company SOP

-----
**5. Review Pipeline**

Trong lúc AI chạy

Reading document

████████░░░

Parsing

██████░░░░

Citation

██████████

Writing Review

████░░░░░░

Score

██░░░░░░░░

Thay vì

Loading...

-----
**6. Issue Card**

Thêm nhiều metadata hơn

High

Citation

98%

Auto Fix

Rule Engine

Estimated 10s

History

Detected 3 scans

-----
**7. Evidence Preview**

Hover

Page 15

Paragraph 3

\-------------------

"...text..."

Click

↓

Word/PDF

Highlight ngay vị trí.

-----
**8. Compare Before / After**

Original

xxxxxxxx

↓

Suggestion

yyyyyyyy

Rất giống GitHub Diff.

-----
**9. Review Timeline**

Scan #1

72

↓

Scan #2

81

↓

Scan #3

90

Thấy tiến bộ.

-----
**10. Quality Radar**

Thay vì

85

Hiển thị

Structure

90

Writing

72

Citation

95

Grammar

100

Format

88

Radar Chart.

-----
**11. Knowledge Explanation**

Mỗi lỗi có

Why?

Academic Rule

IEEE Rule

ResearchMind Explanation

Người dùng học luôn.

-----
**12. AI Confidence**

Confidence

98%

Rule

100%

LLM

68%

External

92%

Giúp người dùng biết mức tin cậy.

-----
**13. Review History**

Yesterday

15 issues

Today

9 issues

Improved

6 issues

New

2 issues

-----
**14. Export**

Không chỉ PDF.

PDF

DOCX

Markdown

HTML

JSON

CSV

-----
**15. Plugin Store (tương lai)**

Installed

APA

IEEE

Nature

ISO

Hospital SOP

Finance Report

Legal Review

...

-----
**16. AI Assistant Panel**

Ở bên phải luôn có panel

ResearchMind

Summary

Top 5 issues

Quick Fix

Ask AI

-----
**Theo mình, giao diện hoàn chỉnh nên có luồng:**

Upload

`    `│

`    `▼

Profile Selection

`    `│

`    `▼

Knowledge Pack

`    `│

`    `▼

Preset

`    `│

`    `▼

Permission Matrix

`    `│

`    `▼

Review Pipeline

`    `│

`    `▼

Dashboard

`    `│

`    `├── Overall Score

`    `├── Radar Chart

`    `├── Timeline

`    `├── Issue List

`    `├── AI Assistant

`    `├── History

`    `└── Export

Điểm mình muốn nhấn mạnh nhất là **Knowledge Pack**, **Permission Matrix**, **Review Pipeline**, **AI Assistant Panel** và **Review History**. Năm thành phần này sẽ tạo cảm giác ResearchMind là một nền tảng review tài liệu chuyên nghiệp, khác biệt rõ so với các công cụ chỉ hiển thị danh sách lỗi.

