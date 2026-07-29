import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import vi from "./locales/vi.json";

// Lấy ngôn ngữ đã lưu từ localStorage hoặc mặc định là 'en'
const savedLanguage = localStorage.getItem("i18nextLng") || "en";

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      vi: { translation: vi },
    },
    lng: savedLanguage, // ngôn ngữ khởi tạo
    fallbackLng: "en",  // ngôn ngữ dự phòng

    interpolation: {
      escapeValue: false, // React đã tự escape XSS
    },
  });

export default i18n;
