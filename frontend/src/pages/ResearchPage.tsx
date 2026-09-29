import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';
import { AlertCircle, AlertTriangle, Clock3, FlaskConical, RotateCw } from 'lucide-react';
import { AppHeader } from '@/components/AppHeader';
import { StatTile } from '@/components/StatTile';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { WavyBlobs } from '@/components/landing/effects/wavy-blobs';
import { API_BASE } from '@/lib/api';
import { easeOut, panelSurface } from '@/lib/design';
import { cn } from '@/lib/utils';
import type { ResearchMetrics } from '../types';

// Same validated categorical pair used on /analytics (Classifier/LLM):
// emerald-600 passes the dataviz skill's CVD/contrast checks in both
// themes without adjustment; --primary already adapts per theme.
const ACTUAL_COLOR = 'hsl(var(--primary))';
const COVERAGE_COLOR = 'hsl(var(--primary))';
const MACRO_F1_COLOR = '#059669';

type State = { data: ResearchMetrics; error: false } | { data: null; error: true } | null;

function pct(fraction: number | null, digits = 1) {
  return fraction === null ? '—' : `${(fraction * 100).toFixed(digits)}%`;
}

export function ResearchPage() {
  const [state, setState] = useState<State>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const ctrl = new AbortController();
    setState(null);
    fetch(`${API_BASE}/research/metrics`, { signal: ctrl.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: ResearchMetrics) => setState({ data, error: false }))
      .catch((err) => {
        if (ctrl.signal.aborted) return;
        console.error(err);
        setState({ data: null, error: true });
      });
    return () => ctrl.abort();
  }, [reload]);

  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-noise" />
      <WavyBlobs className="-z-10 opacity-30" />
      <AppHeader />

      <main className="relative mx-auto max-w-[1200px] p-4 sm:p-6">
        {state === null ? (
          <LoadingState />
        ) : state.error ? (
          <ErrorState onRetry={() => setReload((n) => n + 1)} />
        ) : (
          <Dashboard data={state.data} />
        )}
      </main>
    </div>
  );
}

function Dashboard({ data }: { data: ResearchMetrics }) {
  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, ease: easeOut }}>
        <h1 className="flex items-center gap-2 text-lg font-semibold">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-primary">
            <FlaskConical className="h-4 w-4" />
          </span>
          Research
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          The triage classifier's real evaluation on the ContractNLI dev split — not the live demo. Numbers
          below come from one inference pass over real labeled data; nothing here is estimated or projected.
        </p>
      </motion.div>

      {!data.triage_eval_available ? (
        <NotRunState />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
            <StatTile index={0} label="Dev accuracy" value={pct(data.accuracy, 2)} sublabel={`n = ${data.n_examples ?? '—'}`} />
            <StatTile index={1} label="Macro F1" value={data.macro_f1 !== null ? data.macro_f1.toFixed(4) : '—'} />
            <StatTile
              index={2}
              label="Calibration error (ECE)"
              value={data.ece !== null ? data.ece.toFixed(4) : '—'}
              sublabel="lower is better"
            />
            <StatTile index={3} label="Frozen threshold" value={pct(data.frozen_threshold, 0)} sublabel="selected on dev only" />
          </div>

          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: easeOut, delay: 0.1 }}>
            <Card className={cn('p-5', panelSurface)}>
              <h2 className="text-sm font-semibold">Reliability diagram</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Predicted confidence vs. actual accuracy, in 10 equal-width bins. The dashed line is perfect
                calibration — the closer the real points sit to it, the more trustworthy the classifier's
                confidence score is as a routing signal.
              </p>
              <ReliabilityChart bins={data.calibration_bins} />
            </Card>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: easeOut, delay: 0.15 }}>
            <Card className={cn('p-5', panelSurface)}>
              <h2 className="text-sm font-semibold">Threshold sweep</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Coverage (share of checks resolved without an LLM call) and macro F1 as the confidence
                threshold τ moves from 0.60 to 0.95. The frozen threshold — selected on dev only — is marked.
              </p>
              <ThresholdSweepChart sweep={data.threshold_sweep} frozenThreshold={data.frozen_threshold} />
            </Card>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: easeOut, delay: 0.2 }}>
            <Card className={cn('p-5', panelSurface)}>
              <h2 className="text-sm font-semibold">Config A/B/C comparison</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Accuracy, macro F1, LLM-call count, and latency across the three required pipeline
                configurations (backend/app/experiment_runner.py). Populated once each config has actually
                been run — never estimated.
              </p>
              <ConfigTable configs={data.configs} />
            </Card>
          </motion.div>
        </>
      )}
    </div>
  );
}

function ReliabilityChart({ bins }: { bins: ResearchMetrics['calibration_bins'] }) {
  if (bins.length === 0) {
    return <p className="mt-4 text-sm text-muted-foreground">No calibration bins in this result.</p>;
  }

  const total = bins.reduce((sum, b) => sum + b.count, 0);
  const largest = bins.reduce((a, b) => (b.count > a.count ? b : a));

  const diagonal = [
    { confidence: 0, accuracy: 0 },
    { confidence: 1, accuracy: 1 },
  ];

  return (
    <div className="mt-4">
      <div className="h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="hsl(var(--border))" />
          <XAxis
            type="number"
            dataKey="confidence"
            name="Predicted confidence"
            domain={[0, 1]}
            ticks={[0, 0.25, 0.5, 0.75, 1]}
            tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
            axisLine={{ stroke: 'hsl(var(--border))' }}
            tickLine={false}
            label={{ value: 'Predicted confidence', position: 'insideBottom', offset: -6, fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
          />
          <YAxis
            type="number"
            dataKey="accuracy"
            name="Actual accuracy"
            domain={[0, 1]}
            ticks={[0, 0.25, 0.5, 0.75, 1]}
            tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
            axisLine={{ stroke: 'hsl(var(--border))' }}
            tickLine={false}
            width={44}
          />
          <ZAxis dataKey="count" range={[60, 260]} name="Examples in bin" />
          <Tooltip
            cursor={{ stroke: 'hsl(var(--border))' }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const row = payload[0].payload as ResearchMetrics['calibration_bins'][number];
              return (
                <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-lg">
                  <p className="font-semibold text-foreground">
                    {Math.round(row.confidence * 100)}% confidence → {Math.round(row.accuracy * 100)}% accurate
                  </p>
                  <p className="mt-0.5 text-foreground/70">n = {row.count}</p>
                </div>
              );
            }}
          />
          <Line
            data={diagonal}
            dataKey="accuracy"
            stroke="hsl(var(--muted-foreground))"
            strokeDasharray="4 4"
            strokeWidth={1.5}
            dot={false}
            activeDot={false}
            legendType="none"
            isAnimationActive={false}
          />
          <Scatter
            data={bins}
            dataKey="accuracy"
            fill={ACTUAL_COLOR}
            stroke="hsl(var(--card))"
            strokeWidth={2}
            shape="circle"
            legendType="none"
          />
        </ScatterChart>
      </ResponsiveContainer>
      </div>
      <p className="mt-1 text-center text-[11px] text-muted-foreground">
        <span className="mr-3 inline-flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: ACTUAL_COLOR }} /> Actual (dot size = examples in bin)
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-0 w-3 border-t border-dashed border-muted-foreground" /> Perfect calibration
        </span>
      </p>
      <p className="mt-2 text-xs text-muted-foreground">
        {largest.count.toLocaleString()} of {total.toLocaleString()} examples fall in the{' '}
        {Math.round(largest.confidence * 100)}%-confidence bin. Bins with only a handful of examples are
        statistically noisy — read them as individual cases, not a trend.
      </p>
    </div>
  );
}

function ThresholdSweepChart({
  sweep,
  frozenThreshold,
}: {
  sweep: ResearchMetrics['threshold_sweep'];
  frozenThreshold: number;
}) {
  if (sweep.length === 0) {
    return <p className="mt-4 text-sm text-muted-foreground">No sweep data in this result.</p>;
  }

  // Values cluster near the top; a 0-100% axis flattens every difference.
  const lowest = Math.min(...sweep.flatMap((p) => [p.coverage, p.macro_f1]));
  const yMin = Math.max(0, Math.floor((lowest - 0.02) * 20) / 20);
  const yTicks = Array.from({ length: Math.round((1 - yMin) / 0.025) + 1 }, (_, i) =>
    Math.round((yMin + i * 0.025) * 1000) / 1000
  );

  return (
    <div className="mt-4 h-[320px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={sweep} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="hsl(var(--border))" />
          <XAxis
            dataKey="tau"
            type="number"
            domain={[0.6, 0.95]}
            ticks={[0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]}
            tickFormatter={(v: number) => v.toFixed(2)}
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
            axisLine={{ stroke: 'hsl(var(--border))' }}
            tickLine={false}
            label={{ value: 'Confidence threshold (τ)', position: 'insideBottom', offset: -6, fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
          />
          <YAxis
            domain={[yMin, 1]}
            ticks={yTicks}
            tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`}
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
            axisLine={{ stroke: 'hsl(var(--border))' }}
            tickLine={false}
            width={52}
          />
          <Tooltip
            cursor={{ stroke: 'hsl(var(--border))' }}
            content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null;
              return (
                <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-lg">
                  <p className="font-semibold text-foreground">τ = {Number(label).toFixed(2)}</p>
                  {payload.map((p) => (
                    <p key={p.dataKey as string} className="mt-0.5" style={{ color: p.color }}>
                      {p.name}: <span className="font-semibold text-foreground">{((p.value as number) * 100).toFixed(1)}%</span>
                    </p>
                  ))}
                </div>
              );
            }}
          />
          <Legend
            verticalAlign="top"
            align="left"
            height={28}
            iconType="plainline"
            wrapperStyle={{ fontSize: 12, color: 'hsl(var(--muted-foreground))' }}
          />
          <ReferenceLine
            x={frozenThreshold}
            stroke="hsl(var(--muted-foreground))"
            strokeDasharray="4 4"
            label={{ value: `frozen τ = ${frozenThreshold.toFixed(2)}`, position: 'insideBottomRight', offset: 8, fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
          />
          <Line type="monotone" dataKey="coverage" name="Coverage" stroke={COVERAGE_COLOR} strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
          <Line type="monotone" dataKey="macro_f1" name="Macro F1" stroke={MACRO_F1_COLOR} strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function ConfigTable({ configs }: { configs: ResearchMetrics['configs'] }) {
  const completed = configs.filter((c) => c.status === 'complete');
  const anyNotPaperGrade = completed.some((c) => c.paper_grade === false);
  const anyErrored = completed.some((c) => (c.errored_pairs ?? 0) > 0);

  // Configs are only comparable when run over the same (document, hypothesis)
  // pairs — Project Guide §6.1 requires the same test split for all three.
  // Different n_pairs means these rows came from different-sized runs and
  // must NOT be read against each other.
  const pairCounts = new Set(
    completed.map((c) => c.n_pairs).filter((n): n is number => n !== null)
  );
  const mismatchedSplits = pairCounts.size > 1;

  return (
    <div className="mt-4">
      {mismatchedSplits && (
        <div className="mb-3 flex items-start gap-2 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs">
          <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0 text-red-600 dark:text-red-500" />
          <p className="text-foreground/80">
            <span className="font-semibold text-foreground">Not comparable.</span> These rows were run
            over different numbers of pairs ({[...pairCounts].sort((a, b) => a - b).join(' vs ')}), so
            the configs below are <em>not</em> measuring the same thing. Project Guide §6.1 requires all
            three configs on the same test split — re-run them together before drawing any conclusion
            from this table.
          </p>
        </div>
      )}
      {anyNotPaperGrade && (
        <div className="mb-3 flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs">
          <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0 text-amber-600 dark:text-amber-500" />
          <p className="text-foreground/80">
            <span className="font-semibold text-foreground">Not paper-grade.</span> Runs marked below
            used the cloud LLM (Groq), not local Ollama. A cloud GPU can't demonstrate the inference
            cost the triage layer exists to cut, and it breaks the local/private claim — re-run on
            Ollama before using these numbers in the write-up.
          </p>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[680px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="pb-2 pr-4 font-semibold">Config</th>
              <th className="pb-2 pr-4 font-semibold">Accuracy</th>
              <th className="pb-2 pr-4 font-semibold">Macro F1</th>
              <th className="pb-2 pr-4 font-semibold">LLM calls</th>
              <th className="pb-2 pr-4 font-semibold">Avg. latency</th>
              <th className="pb-2 font-semibold">Run</th>
            </tr>
          </thead>
          <tbody>
            {configs.map((c) => (
              <tr key={c.config} className="border-b border-border/60 last:border-0">
                <td className="py-2.5 pr-4 font-medium">{c.label}</td>
                {c.status === 'pending' ? (
                  <td colSpan={5} className="py-2.5">
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-secondary/40 px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                      <Clock3 className="h-3 w-3" />
                      Pending — not yet run
                    </span>
                  </td>
                ) : (
                  <>
                    <td className="py-2.5 pr-4 tabular-nums">{pct(c.accuracy, 2)}</td>
                    <td className="py-2.5 pr-4 tabular-nums">{c.macro_f1?.toFixed(4) ?? '—'}</td>
                    <td className="py-2.5 pr-4 tabular-nums">
                      {c.llm_call_count ?? '—'}
                      {c.n_pairs ? (
                        <span className="text-muted-foreground"> / {c.n_pairs}</span>
                      ) : null}
                    </td>
                    <td className="py-2.5 pr-4 tabular-nums">
                      {c.avg_latency_s !== null ? `${c.avg_latency_s.toFixed(2)}s` : '—'}
                    </td>
                    <td className="py-2.5">
                      <div className="flex flex-wrap items-center gap-1.5">
                        {c.paper_grade === false && (
                          <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-700 dark:text-amber-500">
                            <AlertTriangle className="h-3 w-3" />
                            Groq
                          </span>
                        )}
                        {(c.errored_pairs ?? 0) > 0 && (
                          <span className="inline-flex items-center rounded-full border border-border bg-secondary/40 px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                            {c.errored_pairs} errored
                          </span>
                        )}
                        {c.run_at && (
                          <span className="text-[11px] tabular-nums text-muted-foreground">
                            {c.run_at.replace('T', ' ').replace('+00:00', 'Z')}
                          </span>
                        )}
                      </div>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {anyErrored && (
        <p className="mt-2 text-xs text-muted-foreground">
          Errored pairs failed mid-run (most often a provider rate limit) and are excluded from the
          metrics above rather than counted as wrong — so accuracy reflects only pairs that actually
          produced a prediction.
        </p>
      )}
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-6" aria-busy>
      <span className="sr-only" role="status">Loading research data</span>
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Card key={i} className={cn('space-y-2 p-4', panelSurface)}>
            <div className="skeleton h-3 w-24" />
            <div className="skeleton h-7 w-16" />
          </Card>
        ))}
      </div>
      <Card className={cn('space-y-3 p-5', panelSurface)}>
        <div className="skeleton h-3.5 w-32" />
        <div className="skeleton h-64 w-full" />
      </Card>
    </div>
  );
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-border/70 bg-secondary/50">
        <AlertCircle className="h-6 w-6 text-red-500" />
      </div>
      <p className="text-sm font-medium">Couldn't load research data</p>
      <p className="max-w-xs text-xs text-muted-foreground">
        The backend didn't respond. Make sure it's running, then try again.
      </p>
      <Button variant="outline" size="sm" onClick={onRetry}>
        <RotateCw className="h-4 w-4" />
        Retry
      </Button>
    </div>
  );
}

function NotRunState() {
  return (
    <Card className={cn('flex flex-col items-center gap-3 p-8 text-center', panelSurface)}>
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-border/70 bg-secondary/50">
        <FlaskConical className="h-6 w-6 text-muted-foreground" />
      </div>
      <p className="text-sm font-medium">No evaluation results yet</p>
      <p className="max-w-md text-xs text-muted-foreground">
        Run the checkpoint verification script to generate real dev-set accuracy, calibration, and threshold
        sweep data for this page.
      </p>
      <code className="mt-1 rounded-lg border border-border bg-secondary/40 px-3 py-1.5 text-xs">
        python -m backend.app.triage_model.verify_checkpoint
      </code>
    </Card>
  );
}
