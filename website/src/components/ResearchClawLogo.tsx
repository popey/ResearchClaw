/**
 * ResearchClaw logo: symbol only.
 */
import { LogoIcon } from "./LogoIcon";

interface ResearchClawLogoProps {
  variant?: "full" | "mark";
  size?: number;
  animated?: boolean;
  className?: string;
}

export function ResearchClawLogo({
  variant = "full",
  size = 48,
  animated: _animated = false,
  className = "",
}: ResearchClawLogoProps) {
  const markSize = variant === "mark" ? size : Math.round(size * 1.1);
  return (
    <span
      className={className}
      style={{ display: "inline-flex", alignItems: "center", lineHeight: 1 }}
    >
      <LogoIcon size={markSize} />
    </span>
  );
}
