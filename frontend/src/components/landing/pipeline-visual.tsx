import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { FileText, Search, Brain, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

type Phase = "parse" | "retrieve" | "reason" | "verdict";

const PHASES: { id: Phase; label: string; icon: typeof FileText; duration: number }[] = [
  { id: "parse", label: "Parse", icon: FileText, duration: 2200 },
  { id: "retrieve", label: "Retrieve", icon: Search, duration: 2200 },
  { id: "reason", label: "Reason", icon: Brain, duration: 2000 },
  { id: "verdict", label: "Verdict", icon: XCircle, duration: 3400 },
];

function useCountUp(target: number, active: boolean) {
  const [value, setValue] = useState(0);
  const frame = useRef<number>(0);

  useEffect(() => {
    if (!active) {
      setValue(0);
      return;
    }
    const start = performance.now();
    const durationMs = 800;
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / durationMs);
      setValue(Math.round(target * (1 - Math.pow(1 - progress, 3))));
      if (progress < 1) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame.current);
  }, [active, target]);

  return value;
}

export function PipelineVisual() {
  const [phaseIndex, setPhaseIndex] = useState(0);
  const phase = PHASES[phaseIndex].id;

  useEffect(() => {
    const timer = setTimeout(() => {
      setPhaseIndex((i) => (i + 1) % PHASES.length);
    }, PHASES[phaseIndex].duration);
    return () => clearTimeout(timer);
  }, [phaseIndex]);

  const confidence = useCountUp(94, phase === "verdict");

  const isRetrieveOrLater = phase === "retrieve" || phase === "reason" || phase === "verdict";
  const isReasonOrLater = phase === "reason" || phase === "verdict";
  const isVerdict = phase === "verdict";

  return (
    <div className="glass-strong relative overflow-hidden rounded-3xl p-6 shadow-2xl shadow-primary/10">
      <div className="mb-4 flex items-center gap-2 border-b border-border/60 pb-4">
        <FileText className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium text-muted-foreground">
          vendor_master_agreement.pdf
        </span>
        <span className="ml-auto text-xs text-muted-foreground">Page 14 of 42</span>
      </div>

      {/* Clause block, with a scanning sweep during the parse phase */}
      <div className="relative space-y-3 overflow-hidden text-sm leading-relaxed text-muted-foreground">
        {phase === "parse" && (
          <motion.div
            className="pointer-events-none absolute inset-x-0 top-0 h-12 bg-gradient-to-b from-transparent via-cyan-400/10 to-transparent blur-[2px]"
            animate={{ y: ["-20%", "220%"] }}
            transition={{ duration: 1.4, repeat: Infinity, ease: "linear" }}
          />
        )}

        <motion.p
          animate={{ opacity: phase === "parse" ? [0.4, 1] : 1 }}
          transition={{ duration: 0.6 }}
        >
          <span className="font-semibold text-foreground">§4.2 —</span>{" "}
          "Either party may terminate this Agreement with{" "}
          <span
            className={cn(
              "rounded px-1 py-0.5 font-medium ring-1 transition-all duration-500",
              isReasonOrLater
                ? "bg-red-500/15 text-red-500 ring-red-500/40 shadow-[0_0_12px_-2px_rgba(239,68,68,0.6)]"
                : "bg-red-500/10 text-red-500/80 ring-red-500/20"
            )}
          >
            thirty (30) days
          </span>{" "}
          written notice."
        </motion.p>

        <motion.p
          animate={{ opacity: phase === "parse" ? [0.4, 1] : 1 }}
          transition={{ duration: 0.6, delay: 0.15 }}
        >
          <span className="font-semibold text-foreground">§11.5 —</span>{" "}
          "...notwithstanding Section 4.2, this Agreement requires{" "}
          <span
            className={cn(
              "rounded px-1 py-0.5 font-medium ring-1 transition-all duration-500",
              isReasonOrLater
                ? "bg-red-500/15 text-red-500 ring-red-500/40 shadow-[0_0_12px_-2px_rgba(239,68,68,0.6)]"
                : "bg-red-500/10 text-red-500/80 ring-red-500/20"
            )}
          >
            ninety (90) days
          </span>{" "}
          prior written notice of termination."
        </motion.p>

        {/* Decoy clause — visually demonstrates noise-filtered retrieval */}
        <motion.p
          animate={{
            opacity: isRetrieveOrLater ? 0.25 : 1,
            filter: isRetrieveOrLater ? "blur(0.4px) grayscale(0.6)" : "none",
          }}
          transition={{ duration: 0.5 }}
        >
          <span className="font-semibold text-foreground">§7.1 —</span> "Confidentiality
          obligations survive termination for five (5) years."
        </motion.p>
      </div>

      {/* Status line for the active phase */}
      <div className="mt-5 h-[86px]">
        <AnimatePresence mode="wait">
          {phase === "retrieve" && (
            <motion.div
              key="retrieve"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.3 }}
              className="flex items-center gap-3 rounded-2xl border border-border bg-secondary/60 p-4"
            >
              <Search className="h-5 w-5 shrink-0 animate-pulse text-cyan-500" />
              <div>
                <p className="text-sm font-semibold">Retrieving relevant evidence…</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Filtering out clauses that don't bear on this hypothesis.
                </p>
              </div>
            </motion.div>
          )}

          {phase === "reason" && (
            <motion.div
              key="reason"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.3 }}
              className="flex items-center gap-3 rounded-2xl border border-border bg-secondary/60 p-4"
            >
              <Brain className="h-5 w-5 shrink-0 text-primary" />
              <div className="flex items-center gap-1.5">
                <p className="text-sm font-semibold">Reasoning over evidence</p>
                <span className="flex gap-0.5">
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce-dot"
                      style={{ animationDelay: `${i * 0.15}s` }}
                    />
                  ))}
                </span>
              </div>
            </motion.div>
          )}

          {isVerdict && (
            <motion.div
              key="verdict"
              initial={{ opacity: 0, scale: 0.92 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.35, ease: "easeOut" }}
              className="flex items-start gap-3 rounded-2xl border border-red-500/20 bg-red-500/[0.06] p-4"
            >
              <motion.div
                initial={{ rotate: -90, scale: 0.5 }}
                animate={{ rotate: 0, scale: 1 }}
                transition={{ type: "spring", stiffness: 300, damping: 15 }}
              >
                <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-500" />
              </motion.div>
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-red-500">Contradiction detected</p>
                  <span className="rounded-full border border-red-500/30 px-2 py-0.5 text-[10px] font-medium text-red-500">
                    LLM-verified · {confidence}%
                  </span>
                </div>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  Termination notice period conflicts between §4.2 (30 days) and §11.5
                  (90 days). Cited: page 14, page 22.
                </p>
              </div>
            </motion.div>
          )}

          {phase === "parse" && (
            <motion.div
              key="parse"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.3 }}
              className="flex items-center gap-3 rounded-2xl border border-border bg-secondary/60 p-4"
            >
              <FileText className="h-5 w-5 shrink-0 animate-pulse text-muted-foreground" />
              <div>
                <p className="text-sm font-semibold">Segmenting into clauses…</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Structure-aware parsing, not blind text chunks.
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Live step indicator — mirrors the actual pipeline */}
      <div className="mt-5 flex items-center justify-between border-t border-border/60 pt-4">
        {PHASES.map((p, i) => {
          const active = i === phaseIndex;
          const done = i < phaseIndex || (isVerdict && i <= phaseIndex);
          return (
            <div key={p.id} className="flex flex-1 items-center gap-2">
              <motion.div
                animate={{
                  scale: active ? 1.15 : 1,
                  opacity: active || done ? 1 : 0.35,
                }}
                className={cn(
                  "flex h-6 w-6 items-center justify-center rounded-full text-white",
                  active || done ? "bg-gradient-brand" : "bg-muted"
                )}
              >
                <p.icon className="h-3 w-3" />
              </motion.div>
              <span
                className={cn(
                  "text-[11px] font-medium transition-colors",
                  active ? "text-foreground" : "text-muted-foreground/60"
                )}
              >
                {p.label}
              </span>
              {i < PHASES.length - 1 && (
                <div className="h-px flex-1 bg-border" />
              )}
            </div>
          );
        })}
      </div>

      {/* Ambient glow behind the panel */}
      <div className="pointer-events-none absolute -inset-8 -z-10 rounded-[2.5rem] bg-gradient-to-br from-violet-500/20 via-fuchsia-500/10 to-cyan-400/10 blur-2xl" />
    </div>
  );
}
