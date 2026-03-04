/**
 * ResearchClaw mascot. Used in Hero and Nav.
 */
import { LogoIcon } from "./LogoIcon";

interface ResearchClawMascotProps {
  size?: number;
  className?: string;
}

export function ResearchClawMascot({
  size = 80,
  className = "",
}: ResearchClawMascotProps) {
  return <LogoIcon size={size} className={className} />;
}
