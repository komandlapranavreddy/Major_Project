import type { CSSProperties } from "react";
import { cn } from "@/lib/utils";

interface ShineBorderProps {
  className?: string;
}

/**
 * A 1.5px gradient ring that only becomes visible (and starts rotating)
 * when the parent `.group` is hovered. Built with the classic
 * padding-box/border-box mask-composite trick so only the ring itself
 * — not the card's fill — picks up the conic gradient.
 */
export function ShineBorder({ className }: ShineBorderProps) {
  return (
    <div
      className={cn(
        "pointer-events-none absolute inset-0 rounded-[inherit] opacity-0 transition-opacity duration-500 group-hover:opacity-100 group-hover:animate-border-spin",
        className
      )}
      style={{
        padding: "1.5px",
        background:
          "conic-gradient(from var(--angle, 0deg), transparent 0%, transparent 72%, #67e8f9 80%, #a78bfa 88%, #67e8f9 96%, transparent 100%)",
        WebkitMask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
        WebkitMaskComposite: "xor",
        maskComposite: "exclude",
      } as CSSProperties}
    />
  );
}
