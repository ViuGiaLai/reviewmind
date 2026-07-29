import { useEffect, useId } from "react";
import { SignIn, SignUp } from "@clerk/clerk-react";
import { FileCheck2, ShieldCheck, Sparkles, WandSparkles, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { BrandLogo } from "./BrandLogo";

export type AuthMode = "sign-in" | "sign-up";

type AuthModalProps = {
  mode: AuthMode;
  onClose: () => void;
  onSwitch: (mode: AuthMode) => void;
};

const clerkAppearance = {
  variables: {
    colorPrimary: "var(--primary)",
    colorText: "var(--text)",
    colorTextSecondary: "var(--text2)",
    colorBackground: "transparent",
    colorInputBackground: "var(--surface)",
    colorInputText: "var(--text)",
    borderRadius: "0.85rem",
    fontFamily: "var(--font)",
  },
  elements: {
    rootBox: "rm-auth-clerk-root",
    cardBox: "rm-auth-clerk-card-box",
    card: "rm-auth-clerk-card",
    logoBox: "rm-auth-clerk-logo",
    header: "rm-auth-clerk-header",
    headerTitle: "rm-auth-clerk-title",
    headerSubtitle: "rm-auth-clerk-subtitle",
    socialButtonsRoot: "rm-auth-social-root",
    socialButtonsBlockButton: "rm-auth-social-button",
    dividerRow: "rm-auth-divider",
    dividerLine: "rm-auth-divider-line",
    dividerText: "rm-auth-divider-text",
    form: "rm-auth-form",
    formFieldLabel: "rm-auth-field-label",
    formFieldInput: "rm-auth-field-input",
    formFieldInputShowPasswordButton: "rm-auth-password-button",
    formFieldErrorText: "rm-auth-field-error",
    formButtonPrimary: "rm-auth-primary-button",
    footer: "rm-auth-clerk-footer",
    footerAction: "rm-auth-clerk-footer-action",
    badge: "rm-auth-hidden",
    socialButtonsBlockButtonBadge: "rm-auth-hidden",
    avatarBox: "rm-auth-hidden",
    userPreviewAvatarBox: "rm-auth-hidden",
  },
};

export function AuthModal({ mode, onClose, onSwitch }: AuthModalProps) {
  const { t } = useTranslation();
  const titleId = useId();
  const isSignIn = mode === "sign-in";

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);

  const benefits = [
    { Icon: ShieldCheck, text: t("auth.private_data") },
    { Icon: FileCheck2, text: t("auth.reference_ready") },
    { Icon: WandSparkles, text: t("auth.controlled_ai") },
  ];

  return (
    <div className="rm-auth-overlay" onMouseDown={event => event.target === event.currentTarget && onClose()}>
      <div className="rm-auth-dialog" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <button className="rm-auth-close" type="button" onClick={onClose} aria-label={t("auth.close")}>
          <X size={20} />
        </button>

        <aside className="rm-auth-story">
          <div className="rm-auth-story-glow" />
          <BrandLogo tone="on-dark" className="rm-auth-logo" />
          <div className="rm-auth-story-content">
            <div className="rm-auth-eyebrow"><Sparkles size={14} /> {t("auth.eyebrow")}</div>
            <h2 id={titleId}>{t(isSignIn ? "auth.sign_in_story_title" : "auth.sign_up_story_title")}</h2>
            <p>{t(isSignIn ? "auth.sign_in_story_desc" : "auth.sign_up_story_desc")}</p>
            <div className="rm-auth-benefits">
              {benefits.map(({ Icon, text }) => (
                <div className="rm-auth-benefit" key={text}><span><Icon size={17} /></span>{text}</div>
              ))}
            </div>
          </div>
          <div className="rm-auth-trust"><ShieldCheck size={15} /> {t("auth.trust_note")}</div>
        </aside>

        <section className="rm-auth-form-panel">
          <div className="rm-auth-mobile-brand"><BrandLogo /></div>
          <div className="rm-auth-clerk-slot" key={mode}>
            {isSignIn ? (
              <SignIn routing="virtual" appearance={clerkAppearance} oauthFlow="popup" />
            ) : (
              <SignUp routing="virtual" appearance={clerkAppearance} oauthFlow="popup" />
            )}
          </div>
          <div className="rm-auth-switch">
            <span>{t(isSignIn ? "auth.switch_signup_prompt" : "auth.switch_signin_prompt")}</span>
            <button type="button" onClick={() => onSwitch(isSignIn ? "sign-up" : "sign-in")}>
              {t(isSignIn ? "auth.switch_signup_action" : "auth.switch_signin_action")}
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
