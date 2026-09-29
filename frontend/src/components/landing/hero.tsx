import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Spotlight } from "@/components/landing/effects/spotlight";
import { Meteors } from "@/components/landing/effects/meteors";
import { GridBackground } from "@/components/landing/effects/grid-background";
import { WavyBlobs } from "@/components/landing/effects/wavy-blobs";
import { PipelineVisual } from "@/components/landing/pipeline-visual";

export function Hero() {
  return (
    <section className="relative flex min-h-screen items-center overflow-hidden pt-32 pb-20">
      <div className="absolute inset-0 -z-10 bg-noise" />
      <GridBackground className="-z-10" />
      <WavyBlobs className="-z-10" />
      <Spotlight className="-top-40 left-0 lg:left-40" />
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <Meteors number={14} />
      </div>

      <div className="mx-auto grid w-full max-w-6xl grid-cols-1 items-center gap-16 px-6 lg:grid-cols-2">
        {/* Copy */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        >
          <Badge variant="glass" className="mb-6">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse-glow" />
            Hybrid retrieval + AI reasoning
          </Badge>

          <h1 className="text-balance text-4xl font-bold leading-[1.1] tracking-tight sm:text-5xl lg:text-6xl">
            Catch contract{" "}
            <span className="text-gradient-brand">contradictions</span> before
            they cost you
          </h1>

          <p className="mt-6 max-w-lg text-balance text-lg leading-relaxed text-muted-foreground">
            EdgeLegal parses contracts into real legal clauses, retrieves only the
            evidence that matters, and reasons over it with a hybrid AI pipeline —
            so every verdict comes back with the exact clause and page it's based on.
          </p>

          <div className="mt-9 flex flex-col gap-4 sm:flex-row sm:items-center">
            <Button asChild size="lg">
              <Link to="/app">
                Try it now — no signup required
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
            <a
              href="#how-it-works"
              className="flex items-center justify-center gap-1.5 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground sm:justify-start"
            >
              See how it works
              <ChevronDown className="h-4 w-4" />
            </a>
          </div>
        </motion.div>

        {/* Live pipeline visual — mirrors the actual product flow */}
        <motion.div
          initial={{ opacity: 0, y: 32, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.7, ease: "easeOut", delay: 0.15 }}
        >
          <PipelineVisual />
        </motion.div>
      </div>
    </section>
  );
}
