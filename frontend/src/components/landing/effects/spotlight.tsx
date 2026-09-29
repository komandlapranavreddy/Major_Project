import { cn } from "@/lib/utils";

interface SpotlightProps {
  className?: string;
}

// Replicates Aceternity UI's Spotlight effect: a large, softly blurred
// gradient ellipse that fades/scales in behind the hero content.
export function Spotlight({ className }: SpotlightProps) {
  return (
    <svg
      className={cn(
        "pointer-events-none absolute z-0 h-[169%] w-[138%] animate-spotlight opacity-0 lg:w-[84%]",
        className
      )}
      viewBox="0 0 3787 2842"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <g filter="url(#spotlight-blur)">
        <ellipse
          cx="1924.71"
          cy="273.501"
          rx="1924.71"
          ry="273.501"
          transform="matrix(-0.822377 -0.568943 -0.568943 0.822377 3631.88 2291.09)"
          fill="url(#spotlight-gradient)"
          fillOpacity="0.6"
        />
      </g>
      <defs>
        <filter
          id="spotlight-blur"
          x="0.860352"
          y="0"
          width="3785.16"
          height="2841.34"
          filterUnits="userSpaceOnUse"
          colorInterpolationFilters="sRGB"
        >
          <feFlood floodOpacity="0" result="BackgroundImageFix" />
          <feBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape" />
          <feGaussianBlur stdDeviation="151" result="effect1_foregroundBlur" />
        </filter>
        <linearGradient
          id="spotlight-gradient"
          x1="0"
          y1="0"
          x2="1"
          y2="1"
          gradientUnits="objectBoundingBox"
        >
          <stop stopColor="#a78bfa" />
          <stop offset="0.5" stopColor="#22d3ee" />
          <stop offset="1" stopColor="#a78bfa" stopOpacity="0" />
        </linearGradient>
      </defs>
    </svg>
  );
}
