import { cn } from "@/lib/utils";

interface GridBackgroundProps {
  className?: string;
}

// Faint grid-pattern backdrop, radially masked so it fades toward the edges.
export function GridBackground({ className }: GridBackgroundProps) {
  return (
    <div
      className={cn(
        "pointer-events-none absolute inset-0 bg-grid",
        "[mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,black_40%,transparent_100%)]",
        className
      )}
    />
  );
}
