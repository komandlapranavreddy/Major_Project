import { motion } from "framer-motion";
import { FileUp, Layers, Search, Brain, FileCheck2 } from "lucide-react";

const STEPS = [
  {
    icon: FileUp,
    title: "Upload your contract",
    description: "Drop in any PDF contract — NDAs, vendor agreements, MSAs.",
  },
  {
    icon: Layers,
    title: "Structure-aware parsing",
    description: "The document is segmented into real legal clauses, not blind text chunks.",
  },
  {
    icon: Search,
    title: "Noise-filtered retrieval",
    description: "Semantic search pulls only the clauses that actually matter for the question asked.",
  },
  {
    icon: Brain,
    title: "Hybrid AI reasoning",
    description: "A hybrid pipeline reasons over the retrieved evidence and returns a verdict.",
  },
  {
    icon: FileCheck2,
    title: "Evidence-backed report",
    description: "Every answer links back to the exact clause and page it came from.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="relative mx-auto max-w-6xl px-6 py-24">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5 }}
        className="mx-auto max-w-2xl text-center"
      >
        <h2 className="text-balance text-3xl font-bold tracking-tight sm:text-4xl">
          How it works
        </h2>
        <p className="mt-4 text-balance leading-relaxed text-muted-foreground">
          Five steps from a raw PDF to a verdict you can trust — and trace.
        </p>
      </motion.div>

      <div className="relative mt-16">
        <div className="absolute left-6 top-6 hidden h-px w-[calc(100%-3rem)] bg-gradient-to-r from-border via-border to-transparent md:block" />

        <div className="grid grid-cols-1 gap-10 sm:grid-cols-2 md:grid-cols-5 md:gap-6">
          {STEPS.map((step, i) => (
            <motion.div
              key={step.title}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="relative flex flex-col"
            >
              <div className="z-10 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-brand text-white shadow-lg shadow-primary/25 ring-4 ring-background">
                <step.icon className="h-5 w-5" />
              </div>
              <span className="mt-4 text-xs font-semibold text-muted-foreground">
                STEP {i + 1}
              </span>
              <h3 className="mt-1 text-base font-semibold tracking-tight">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {step.description}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
