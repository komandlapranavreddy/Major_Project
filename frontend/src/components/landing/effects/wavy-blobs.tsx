import { motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/utils";

interface WavyBlobsProps {
  className?: string;
}

const BLOBS = [
  {
    size: 560,
    top: "-15%",
    left: "-8%",
    duration: 20,
    className: "bg-gradient-to-br from-violet-500/30 to-fuchsia-500/10",
  },
  {
    size: 460,
    top: "10%",
    left: "62%",
    duration: 26,
    className: "bg-gradient-to-br from-cyan-400/25 to-blue-500/10",
  },
  {
    size: 420,
    top: "55%",
    left: "18%",
    duration: 23,
    className: "bg-gradient-to-br from-fuchsia-500/20 to-violet-400/10",
  },
];

const BORDER_RADII = [
  "60% 40% 30% 70% / 60% 30% 70% 40%",
  "30% 60% 70% 40% / 50% 60% 30% 60%",
  "50% 50% 40% 60% / 40% 60% 40% 60%",
  "60% 40% 30% 70% / 60% 30% 70% 40%",
];

/**
 * Soft, slowly morphing blobs — the "wavy floating" ambient background.
 * Pure Framer Motion (no WebGL): animates border-radius, drift, and a
 * gentle rotation so the shapes feel organic rather than mechanical.
 */
export function WavyBlobs({ className }: WavyBlobsProps) {
  const reduceMotion = useReducedMotion();
  return (
    <div className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}>
      {BLOBS.map((blob, i) => (
        <motion.div
          key={i}
          className={cn("absolute blur-3xl", blob.className)}
          style={{ width: blob.size, height: blob.size, top: blob.top, left: blob.left, borderRadius: BORDER_RADII[0] }}
          animate={reduceMotion ? undefined : {
            borderRadius: BORDER_RADII,
            x: [0, 40, -30, 0],
            y: [0, -35, 25, 0],
            rotate: [0, 12, -8, 0],
          }}
          transition={{
            duration: blob.duration,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  );
}
