import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GridBackground } from "@/components/landing/effects/grid-background";

export function FinalCta() {
  return (
    <section className="relative mx-auto max-w-6xl px-6 py-16">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.6 }}
        className="relative overflow-hidden rounded-3xl border border-border bg-gradient-to-br from-violet-600 via-fuchsia-500 to-cyan-500 px-6 py-16 text-center shadow-2xl shadow-primary/20 sm:px-16"
      >
        <GridBackground className="opacity-20 [mask-image:radial-gradient(ellipse_70%_70%_at_50%_50%,black_40%,transparent_100%)]" />
        <motion.div
          className="pointer-events-none absolute -inset-16 -z-10 bg-[radial-gradient(circle_at_30%_20%,rgba(255,255,255,0.25),transparent_45%)]"
          animate={{ opacity: [0.4, 0.8, 0.4] }}
          transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
        />
        <div className="relative">
          <h2 className="text-balance text-3xl font-bold tracking-tight text-white sm:text-4xl">
            See your contract's contradictions in minutes, not meetings
          </h2>
          <p className="mx-auto mt-4 max-w-lg text-balance text-violet-100">
            No account, no waitlist — upload a contract and get an evidence-backed
            report right now.
          </p>
          <div className="mt-8 flex justify-center">
            <Button
              asChild
              size="lg"
              className="bg-none bg-white text-violet-700 shadow-xl hover:brightness-100 hover:bg-violet-50"
            >
              <Link to="/app">
                Try Demo — no signup
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>
      </motion.div>
    </section>
  );
}
