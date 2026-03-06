/**
 * ResearchClaw branding icon (symbol).
 */
interface LogoIconProps {
  size: number;
  className?: string;
}

const LOGO_SRC = `${import.meta.env.BASE_URL}researchclaw-symbol.png`;

export function LogoIcon({ size, className = "" }: LogoIconProps) {
  return (
    <img
      src={LOGO_SRC}
      alt=""
      width={size}
      height={size}
      className={className}
      style={{
        display: "block",
        margin: "0 auto",
        objectFit: "contain",
      }}
      aria-hidden
    />
  );
}
