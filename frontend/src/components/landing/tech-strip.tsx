import { motion } from "framer-motion";
import { Zap, Atom, Boxes, Type, Cpu } from "lucide-react";

const STACK = [
  { icon: Zap, name: "FastAPI" },
  { icon: Atom, name: "React" },
  { icon: Boxes, name: "ChromaDB" },
  { icon: Type, name: "sentence-transformers" },
  { icon: Cpu, name: "Local LLM inference" },
];

export function TechStrip() {
  const row = [...STACK, ...STACK];

  return (
    <section id="tech" className="relative mx-auto max-w-6xl px-6 py-20">
      <motion.p
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
        className="text-center text-xs font-semibold uppercase tracking-widest text-muted-foreground"
      >
        Built with
      </motion.p>

      <div className="relative mt-8 overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_10%,black_90%,transparent)]">
        <div className="flex w-max animate-marquee gap-4">
          {row.map((item, i) => (
            <div
              key={`${item.name}-${i}`}
              className="glass flex items-center gap-2.5 rounded-xl px-5 py-3 whitespace-nowrap"
            >
              <item.icon className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium text-muted-foreground">{item.name}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
