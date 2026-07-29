import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import vi from "./locales/vi.json";

const supportedLanguages = ["en", "vi"] as const;
type SupportedLanguage = (typeof supportedLanguages)[number];

function resolveLanguage(): SupportedLanguage {
  const saved = localStorage.getItem("i18nextLng")?.split("-")[0];
  if (supportedLanguages.includes(saved as SupportedLanguage)) return saved as SupportedLanguage;
  const browserLanguage = navigator.language.split("-")[0];
  return supportedLanguages.includes(browserLanguage as SupportedLanguage)
    ? (browserLanguage as SupportedLanguage)
    : "en";
}

i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, vi: { translation: vi } },
  lng: resolveLanguage(),
  fallbackLng: "en",
  supportedLngs: supportedLanguages,
  load: "languageOnly",
  returnNull: false,
  interpolation: { escapeValue: false },
});

i18n.on("languageChanged", (language) => {
  const normalized = language.split("-")[0] as SupportedLanguage;
  localStorage.setItem("i18nextLng", normalized);
  document.documentElement.lang = normalized;
});

document.documentElement.lang = i18n.resolvedLanguage || "en";

export default i18n;