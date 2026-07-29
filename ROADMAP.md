# ReviewMind Roadmap

ReviewMind tiếp tục giữ bốn nguyên tắc: hiểu tài liệu trước khi đánh giá, Rule-first/AI-assisted, mọi kết quả có thể giải thích, và người dùng quyết định thay đổi cuối cùng.

## Current baseline — Core platform

- Unified document model, parsers, profiles, Knowledge Packs và Rule Engine.
- Issue management, scoring, AI Review, Auto Fix và Insights.
- Plugin Extension API, permissions, lifecycle và Event Bus.
- Trust Layer: verified authentication, RBAC, audit chain, retention policy.
- Operations Layer: health probes, metrics, structured logs, containers, CI và backup/restore.

Release gate:

- Backend tests and frontend production build pass.
- No unsigned executable plugin is enabled.
- Production JWT and webhook signatures are verified.
- Readiness returns success only when database and storage are available.
- Backup integrity is verified before restore.

## Phase 1 — Stabilization

- Add parser fixtures for large DOCX/PDF documents.
- Add PostgreSQL integration tests and migration rollback tests.
- Run container builds and smoke tests in CI with PostgreSQL.
- Establish API, Rule, Prompt, Plugin and Knowledge Pack compatibility matrices.

Exit criteria: reproducible deployment, zero critical security findings, and documented recovery drill.

## Phase 2 — Productivity

- Batch Review and Batch Auto Fix.
- Team workspaces, comments and review assignments.
- Template library and workflow automation.
- Full document writer for DOCX/PDF export after verified fixes.

Exit criteria: measurable reduction in median manual review time and reliable multi-user ownership controls.

## Phase 3 — Intelligence

- Cross-section contradiction detection.
- Semantic search and context-aware recommendations.
- Domain-specific and local AI providers.
- Quality evaluation datasets for prompt/model regression.

Exit criteria: AI findings improve recall without reducing evidence accuracy or bypassing Rule Engine.

## Phase 4 — Ecosystem

- Signed Plugin and Knowledge Pack distribution.
- Marketplace review, revocation and update policies.
- Public SDK, CLI and headless review mode.
- Community contribution validation.

Exit criteria: third-party extensions operate without direct database, credential or filesystem access.

## Phase 5 — Enterprise

- Multi-tenancy and organization policies.
- Customer-managed encryption keys and regional data residency.
- SSO/SCIM, compliance center and audit analytics.
- Horizontal workers, queues and zero-downtime deployment.

Exit criteria: tenant isolation tests, recovery objectives, availability SLOs and compliance evidence are continuously verified.

## Product success metrics

- Median review time and time saved per document.
- Remaining high-severity issues after remediation.
- Auto Fix success, verification and revert rates.
- AI evidence accuracy and provider latency.
- Availability, error rate, MTTD and MTTR.
- API/Plugin/Knowledge Pack backward compatibility.
