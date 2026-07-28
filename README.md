# ReviewMind

> AI-powered document review platform for academic, business, technical, and professional documents.

ReviewMind is an intelligent document review platform that combines **rule-based validation**, **AI reasoning**, and **customizable review profiles** to help users review, analyze, and improve documents with confidence.

Unlike traditional grammar checkers, ReviewMind evaluates **document structure, formatting, citations, writing quality, compliance, and document-specific standards**.

---

## ✨ Features

- 📄 Multi-profile document review
  - Academic Papers
  - Thesis
  - Journal Manuscripts
  - Technical Reports
  - Standard Operating Procedures (SOP)
  - Business Reports
  - Project Proposals

- 🧠 AI-powered document analysis

- ⚙️ Rule-based validation engine

- 📚 Knowledge Pack architecture

- 📝 Writing quality assessment

- 📖 Citation & reference validation

- 📊 Review score dashboard

- 🔍 Evidence-backed issue detection

- 🤖 Auto Fix Engine

- 📤 Export reviewed documents

---

## 🚀 Roadmap

### Phase 1

- [x] Review Engine
- [x] Multi Profile
- [x] Rule Engine
- [x] Score Dashboard
- [ ] AI Summary
- [ ] Auto Fix Engine

### Phase 2

- [ ] DOCX Review
- [ ] PDF Review
- [ ] Citation Engine
- [ ] Report Export
- [ ] Review History

### Phase 3

- [ ] Knowledge Packs
- [ ] Journal Guidelines
- [ ] Organization Templates
- [ ] Plugin System
- [ ] Team Collaboration

---

## 🏗 Architecture

```text
                Upload Document
                       │
                       ▼
              Document Parser
                       │
                       ▼
               Document Model
                       │
                       ▼
              Profile Selection
                       │
                       ▼
           Knowledge Pack Loader
                       │
                       ▼
                Rule Engine
                       │
                       ▼
                 AI Reasoning
                       │
                       ▼
                 Issue Engine
                ┌──────────────┐
                ▼              ▼
          Score Engine     Auto Fix
                └──────┬───────┘
                       ▼
               Report Generator
                       │
                       ▼
                Review Dashboard
```

---

## 🧩 Review Profiles

- Academic Review
- Thesis Review
- Journal Review
- Technical Report Review
- SOP Review
- Business Report Review
- Proposal Review

---

## 🔍 Review Categories

- Document Structure
- Formatting
- Grammar
- Writing Quality
- Citation & References
- Figures & Tables
- Technical Validation
- Compliance & Safety
- Document Consistency

---

## 🤖 Auto Fix

ReviewMind can automatically fix supported issues, including:

- Heading styles
- Table of contents
- Numbering
- Page numbers
- Font formatting
- Margins
- Spacing
- Figure captions
- Table captions
- Reference formatting
- Cross references
- Document metadata

ReviewMind always previews changes before applying them.

---

## 🛠 Tech Stack

### Frontend

- React
- TypeScript
- Vite
- Tailwind CSS

### Backend

- FastAPI
- Python

### Database

- SQLite (Development)
- PostgreSQL (Production)

### AI

- Gemini
- OpenAI
- Anthropic
- Ollama

---

## 📂 Project Structure

```text
reviewmind/

├── frontend/
├── backend/
├── docs/
├── storage/
├── docker/
└── README.md
```

---

## 🎯 Vision

ReviewMind aims to become a professional AI-powered document review platform that goes beyond grammar checking by understanding document structure, quality, compliance, and domain-specific standards.

---

## 📄 License

MIT License