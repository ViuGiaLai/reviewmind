import { Suspense, useEffect, useState, type ComponentProps } from "react";
import { createRoot } from "react-dom/client";
import { ClerkProvider } from "@clerk/clerk-react";
import { dark } from "@clerk/themes";
import { Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import "./i18n";
import "./styles.css";
import { App } from "./App";
import { CLERK_PUBLISHABLE_KEY } from "./lib/config";
import { safeGetItem } from "./lib/storage";
import { BrandLogo } from "./components/BrandLogo";

type ClerkLocalization = ComponentProps<typeof ClerkProvider>["localization"];

function RootApp() {
  const { i18n } = useTranslation();
  const [clerkLocalization, setClerkLocalization] = useState<ClerkLocalization>();

  useEffect(() => {
    if (i18n.resolvedLanguage !== "vi") {
      setClerkLocalization(undefined);
      return;
    }
    let active = true;
    void import("@clerk/localizations/vi-VN").then(({ viVN }) => {
      if (active) setClerkLocalization(viVN);
    });
    return () => { active = false; };
  }, [i18n.resolvedLanguage]);
  const storedTheme = safeGetItem("theme");
  const prefersDark = typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const useDarkTheme = storedTheme === "dark" || (!storedTheme && prefersDark);
  return <ClerkProvider publishableKey={CLERK_PUBLISHABLE_KEY} afterSignOutUrl="/" localization={clerkLocalization} appearance={{ baseTheme: useDarkTheme ? dark : undefined, layout: { logoImageUrl: useDarkTheme ? "/logo_reviewmind_brand_dark.png" : "/logo_reviewmind_brand.png" } }}>
    <Suspense fallback={<div className="app-loading"><BrandLogo variant="mark" className="loading-brand-logo" /><Loader2 className="spin" size={18} /></div>}><App /></Suspense>
  </ClerkProvider>;
}

const root = document.getElementById("root");
if (!root) throw new Error("Root element not found");
createRoot(root).render(<RootApp />);