import { useMemo } from "react";
import { cn } from "@/lib/utils";

interface MeteorsProps {
  number?: number;
  className?: string;
}

// Replicates Aceternity UI's Meteors effect: a scattering of streaking
// gradient trails drifting across the hero backdrop.
export function Meteors({ number = 16, className }: MeteorsProps) {
  const meteors = useMemo(
    () =>
      Array.from({ length: number }, (_, i) => ({
        id: i,
        left: `${Math.floor(Math.random() * 100)}%`,
        delay: `${Math.random() * 6}s`,
        duration: `${5 + Math.random() * 4}s`,
      })),
    [number]
  );

  return (
    <>
      {meteors.map((meteor) => (
        <span
          key={meteor.id}
          className={cn(
            "pointer-events-none absolute top-1/2 left-1/2 h-0.5 w-0.5 rotate-[215deg] animate-meteor rounded-full bg-violet-300 shadow-[0_0_0_1px_#ffffff10] dark:bg-violet-200",
            "before:absolute before:top-1/2 before:h-[1px] before:w-[60px] before:-translate-y-1/2 before:transform before:bg-gradient-to-r before:from-violet-300 before:to-transparent before:content-['']",
            className
          )}
          style={{
            top: 0,
            left: meteor.left,
            animationDelay: meteor.delay,
            animationDuration: meteor.duration,
          }}
        />
      ))}
    </>
  );
}
