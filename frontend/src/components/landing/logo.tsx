import { cn } from "@/lib/utils";

interface LogoMarkProps {
  className?: string;
}

/**
 * EdgeLegal mark: an "E" built from aligned bars, with the middle bar broken
 * and offset — the top/bottom bars agree, the middle one doesn't. That
 * misalignment is literally the thing the product detects.
 */
export function LogoMark({ className }: LogoMarkProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      className={cn("h-5 w-5", className)}
      aria-hidden="true"
    >
      <rect x="3.5" y="3.5" width="3" height="17" rx="1.5" fill="white" />
      <rect x="3.5" y="3.5" width="15.5" height="3" rx="1.5" fill="white" />
      <rect x="3.5" y="17.5" width="15.5" height="3" rx="1.5" fill="white" />
      <rect x="3.5" y="10.5" width="8" height="3" rx="1.5" fill="white" fillOpacity="0.55" />
      <rect x="13.7" y="9.1" width="6.8" height="3" rx="1.5" fill="#67e8f9" />
    </svg>
  );
}

interface LogoProps {
  className?: string;
  markClassName?: string;
  showWordmark?: boolean;
}

export function Logo({ className, markClassName, showWordmark = true }: LogoProps) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <div
        className={cn(
          "flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-brand shadow-md shadow-primary/30",
          markClassName
        )}
      >
        <LogoMark />
      </div>
      {showWordmark && (
        <span className="text-base font-bold tracking-tight">EdgeLegal</span>
      )}
    </div>
  );
}
