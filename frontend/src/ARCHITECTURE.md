# Frontend module boundaries

- `main.tsx`: application bootstrap only (providers, global styles, root render).
- `App.tsx`: authenticated workspace orchestration, account-scoped state, and routing shell.
- `pages/`: one module per product page or closely related page group; private pages are lazy-loaded.
- `components/`: reusable feature components that do not own application routing.
- `domain/types.ts`: shared business and API types. Components must not import types from `main.tsx` or pages.
- `lib/`: infrastructure helpers such as runtime configuration and safe browser storage.
- `navigation.ts`: page identifiers, labels, and breadcrumb rules.

New pages must not be implemented in `main.tsx`. User-facing text must use i18n; `npm run check:i18n` enforces literal key coverage and English/Vietnamese catalog parity.
