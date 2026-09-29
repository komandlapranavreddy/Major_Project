import { motion } from "framer-motion";
import { Layers, Filter, Quote, ListChecks, Zap, ShieldCheck } from "lucide-react";
import { GridBackground } from "@/components/landing/effects/grid-background";
import { ShineBorder } from "@/components/landing/effects/shine-border";
import { TiltCard } from "@/components/landing/effects/tilt-card";

const FEATURES = [
  {
    icon: Layers,
    title: "Structure-aware clause parsing",
    description:
      "Contracts are segmented along real clause and section boundaries — numbering, headings, sub-clauses — not arbitrary character counts.",
  },
  {
    icon: Filter,
    title: "Noise-filtered semantic retrieval",
    description:
      "An adaptive relevance filter drops weakly-related clauses instead of forcing a fixed top-K, so the reasoning step sees signal, not noise.",
  },
  {
    icon: Quote,
    title: "Evidence citations, exactly located",
    description: "Every verdict links back to the precise clause and PDF page it came from.",
  },
  {
    icon: ListChecks,
    title: "17-rule NDA playbook + custom queries",
    description: "Check a contract against the standard playbook, or ask your own question.",
  },
  {
    icon: Zap,
    title: "Hybrid reasoning, minimal AI calls",
    description:
      "A fast triage layer resolves the obvious cases directly, reserving heavier reasoning for genuinely ambiguous ones.",
  },
  {
    icon: ShieldCheck,
    title: "Local-deployment-capable by design",
    description:
      "Built to run on local infrastructure for privacy-sensitive review — no requirement to ship contract text to a third party.",
  },
];

export function FeaturesBento() {
  return (
    <section id="features" className="relative mx-auto max-w-6xl px-6 py-24">
      <GridBackground className="opacity-60 [mask-image:radial-gradient(ellipse_70%_60%_at_50%_40%,black_20%,transparent_100%)]" />

      <motion.div
        className="pointer-events-none absolute left-1/2 top-10 -z-10 h-72 w-72 -translate-x-1/2 rounded-full bg-violet-500/10 blur-3xl"
        animate={{ x: [0, 40, 0], y: [0, -20, 0] }}
        transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
      />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5 }}
        className="relative mx-auto max-w-2xl text-center"
      >
        <h2 className="text-balance text-3xl font-bold tracking-tight sm:text-4xl">
          Everything the pipeline does, none of the busywork
        </h2>
        <p className="mt-4 text-balance leading-relaxed text-muted-foreground">
          Each piece has one job — parse, retrieve, reason, or cite — so the system
          stays fast where it can and careful where it must.
        </p>
      </motion.div>

      <div className="relative mt-14 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((feature, i) => (
          <motion.div
            key={feature.title}
            initial={{ opacity: 0, y: 28, scale: 0.94 }}
            whileInView={{ opacity: 1, y: 0, scale: 1 }}
            viewport={{ once: true, margin: "-40px" }}
            transition={{ duration: 0.5, delay: i * 0.07, ease: "easeOut" }}
          >
            <TiltCard>
              <div
                className="group relative h-full overflow-hidden rounded-2xl border border-border bg-card p-6 transition-shadow duration-300 hover:shadow-xl hover:shadow-primary/10"
                onMouseMove={(e) => {
                  const rect = e.currentTarget.getBoundingClientRect();
                  e.currentTarget.style.setProperty("--x", `${e.clientX - rect.left}px`);
                  e.currentTarget.style.setProperty("--y", `${e.clientY - rect.top}px`);
                }}
              >
                <ShineBorder />

                <div
                  className="pointer-events-none absolute -inset-px rounded-2xl opacity-0 transition-opacity duration-300 group-hover:opacity-100"
                  style={{
                    background:
                      "radial-gradient(280px circle at var(--x, 50%) var(--y, 50%), hsl(var(--primary) / 0.12), transparent 70%)",
                  }}
                />

                <div className="relative z-10 flex h-full flex-col" style={{ transform: "translateZ(30px)" }}>
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary transition-transform duration-300 group-hover:scale-110">
                    <feature.icon className="h-5 w-5" />
                  </div>
                  <h3 className="mt-4 text-base font-semibold tracking-tight">{feature.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    {feature.description}
                  </p>
                </div>
              </div>
            </TiltCard>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
