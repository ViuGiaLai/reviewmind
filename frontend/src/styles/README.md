# Styles architecture

`../styles.css` is the only stylesheet entry imported by the application. It
loads these modules in numeric order so the existing cascade remains stable.

- `01`–`05`: design tokens, base rules, application shell, and shared UI primitives.
- `06`–`14`: feature styles for dashboard, reviews, profiles, review workflow,
  assistant, settings, issue inspection, insights, and overlays.
- `15`–`21`: responsive compatibility, workspace/landing experiences, the
  current product refresh, reference templates, and final responsive overrides.
- `brand-logo.css` is a component-owned shared module loaded directly after the
  base layer. Other named files remain after the numbered compatibility chain.

When adding UI:

1. Put feature-specific selectors in that feature's module.
2. Put reusable controls in `05-primitives.css` and design values in
   `01-tokens.css`.
3. Add responsive rules beside the feature when possible. Keep `15` and `21`
   for compatibility overrides that intentionally depend on the full cascade.
4. Import new modules only from `../styles.css`; do not add CSS imports to
   `main.tsx` or page components.
