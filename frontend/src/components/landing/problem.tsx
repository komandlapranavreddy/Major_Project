import { motion } from "framer-motion";
import { Ban, Scale, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

const CALLOUTS = [
  {
    icon: Ban,
    eyebrow: "Manual review",
    stat: "Clause by clause",
    detail: "A trained reviewer works through every page by hand, and easy-to-miss cross-page conflicts slip through anyway.",
    accent: "text-slate-400",
  },
  {
    icon: Scale,
    eyebrow: "LLM-only pipelines",
    stat: "Every clause, every call",
    detail: "Sending every single clause comparison to a large model doesn't scale — cost and latency compound as contracts grow.",
    accent: "text-red-400",
  },
  {
    icon: Sparkles,
    eyebrow: "EdgeLegal",
    stat: "Evidence-backed, on demand",
    detail: "Only the clauses that actually matter get retrieved and reasoned over, with every verdict traced back to its source.",
    accent: "text-violet-400",
  },
];

export function Problem() {
  return (
    <section className="relative mx-auto max-w-6xl px-6 py-24">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5 }}
        className="mx-auto max-w-2xl text-center"
      >
        <h2 className="text-balance text-3xl font-bold tracking-tight sm:text-4xl">
          Contract review is stuck between two bad options
        </h2>
        <p className="mt-4 text-balance leading-relaxed text-muted-foreground">
          Manual review is slow and expensive. Routing every clause through a large
          language model is fast to build but doesn't scale. EdgeLegal is built
          around a third path.
        </p>
      </motion.div>

      <div className="mt-14 grid grid-cols-1 gap-5 md:grid-cols-3">
        {CALLOUTS.map((item, i) => (
          <motion.div
            key={item.eyebrow}
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{ duration: 0.5, delay: i * 0.1 }}
            className="glass rounded-2xl p-6"
          >
            <item.icon className={cn("h-6 w-6", item.accent)} />
            <p className="mt-4 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {item.eyebrow}
            </p>
            <p className="mt-2 text-xl font-bold tracking-tight">{item.stat}</p>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              {item.detail}
            </p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
