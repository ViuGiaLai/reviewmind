import type { Page } from "./domain/types";

export const PAGE_LABELS: Record<Page, string> = {
  landing: "common.brand", home: "nav.home", reviews: "nav.reviews", "review-new": "nav.new_review",
  "review-detail": "nav.current_review", documents: "nav.documents", templates: "nav.templates",
  history: "nav.history", profiles: "nav.profiles", kbpacks: "nav.kbpacks", ai: "nav.ai", settings: "nav.settings",
};
export function breadcrumb(page: Page, translate: (key: string) => string, docName?: string): { label: string; page?: Page }[] {
  const crumbs: { label: string; page?: Page }[] = [{ label: translate("nav.home"), page: "home" }];
  if (page === "home") return crumbs;
  if (page === "reviews" || page === "review-new" || page === "review-detail") {
    crumbs.push({ label: translate("nav.reviews"), page: "reviews" });
    if (page === "review-new") crumbs.push({ label: translate("nav.new_review") });
    else if (page === "review-detail" && docName) crumbs.push({ label: docName });
    return crumbs;
  }
  crumbs.push({ label: translate(PAGE_LABELS[page]) });
  return crumbs;
}