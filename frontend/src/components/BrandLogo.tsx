type BrandLogoProps = {
  className?: string;
  responsive?: boolean;
  variant?: "full" | "mark";
  tone?: "auto" | "on-dark" | "on-light";
};

function LogoPair({ kind }: { kind: "full" | "mark" }) {
  const suffix = kind === "full" ? "brand" : "mark";
  return (
    <span className={`brand-logo__pair brand-logo__pair--${kind}`} aria-hidden="true">
      <img className="brand-logo__image brand-logo__image--light" src={`/logo_reviewmind_${suffix}.png`} alt="" decoding="async" />
      <img className="brand-logo__image brand-logo__image--dark" src={`/logo_reviewmind_${suffix}_dark.png`} alt="" decoding="async" />
    </span>
  );
}

export function BrandLogo({ className = "", responsive = false, tone = "auto", variant = "full" }: BrandLogoProps) {
  const classes = [
    "brand-logo",
    `brand-logo--${variant}`,
    responsive ? "brand-logo--responsive" : "",
    tone !== "auto" ? `brand-logo--${tone}` : "",
    className,
  ].filter(Boolean).join(" ");

  return (
    <span className={classes} role="img" aria-label="ReviewMind">
      <LogoPair kind={variant} />
      {responsive && variant === "full" ? <LogoPair kind="mark" /> : null}
    </span>
  );
}
