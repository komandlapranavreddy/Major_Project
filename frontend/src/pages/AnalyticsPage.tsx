import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { AlertCircle, BarChart3, Brain, RotateCw, ScanSearch, Zap } from 'lucide-react';
import { AppHeader } from '@/components/AppHeader';
import { StatTile } from '@/components/StatTile';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { WavyBlobs } from '@/components/landing/effects/wavy-blobs';
import { API_BASE } from '@/lib/api';
import { easeOut, panelSurface } from '@/lib/design';
import { cn } from '@/lib/utils';
import type { Analytics } from '../types';

// Classifier (emerald-600) validated against both card surfaces via the dataviz
// skill's palette validator; --primary already adapts per theme.
const CLASSIFIER_COLOR = '#059669';
const LLM_COLOR = 'hsl(var(--primary))';
const BAR_COLOR = 'hsl(var(--primary))';

type State = { data: Analytics; error: false } | { data: null; error: true } | null;

function pct(fraction: number) {
  return `${Math.round(fraction * 100)}%`;
}

export function AnalyticsPage() {
  const [state, setState] = useState<State>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const ctrl = new AbortController();
    setState(null);
    fetch(`${API_BASE}/analytics`, { signal: ctrl.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: Analytics) => setState({ data, error: false }))
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
      <WavyBlobs className="-z-10 opacity-60" />
      <AppHeader />

      <main className="relative mx-auto max-w-[1200px] p-4 sm:p-6">
        {state === null ? (
          <LoadingState />
        ) : state.error ? (
          <ErrorState onRetry={() => setReload((n) => n + 1)} />
        ) : state.data.total_analyses === 0 ? (
          <EmptyState />
        ) : (
          <Dashboard data={state.data} />
        )}
      </main>
    </div>
  );
}

function Dashboard({ data }: { data: Analytics }) {
  const total = data.classifier_count + data.llm_count;
  const classifierPct = total ? data.classifier_count / total : 0;
  const llmPct = total ? data.llm_count / total : 0;

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: easeOut }}
      >
        <h1 className="flex items-center gap-2 text-lg font-semibold">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-primary">
            <BarChart3 className="h-4 w-4" />
          </span>
          Analytics
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Across every contract checked so far. No accuracy or cost-saving claims — Configs A/B/C
          haven't been run yet.
        </p>
      </motion.div>

      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatTile index={0} label="Documents analyzed" value={data.documents_analyzed.toLocaleString()} />
        <StatTile
          index={1}
          label="Contradictions found"
          value={data.total_contradictions.toLocaleString()}
          sublabel={`${pct(data.contradiction_rate)} of all checks`}
        />
        <StatTile
          index={2}
          label="Avg. classifier confidence"
          value={data.avg_classifier_confidence !== null ? pct(data.avg_classifier_confidence) : '—'}
          sublabel="on classifier-resolved checks"
        />
        <StatTile index={3} label="Total checks run" value={data.total_analyses.toLocaleString()} />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: easeOut, delay: 0.15 }}
      >
        <Card className={cn('p-5', panelSurface)}>
          <h2 className="text-sm font-semibold">Resolution mix</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            How each check was resolved: directly by the triage classifier, or escalated to the LLM.
          </p>

          {total === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">No resolved checks yet.</p>
          ) : (
            <>
              <div className="mt-4 flex h-3 w-full gap-0.5 overflow-hidden rounded-full bg-secondary">
                <motion.div
                  initial={{ scaleX: 0 }}
                  animate={{ scaleX: classifierPct }}
                  transition={{ duration: 0.7, ease: easeOut, delay: 0.3 }}
                  style={{ transformOrigin: 'left', flexBasis: `${classifierPct * 100}%`, backgroundColor: CLASSIFIER_COLOR }}
                  className="h-full rounded-full"
                />
                <motion.div
                  initial={{ scaleX: 0 }}
                  animate={{ scaleX: llmPct }}
                  transition={{ duration: 0.7, ease: easeOut, delay: 0.35 }}
                  style={{ transformOrigin: 'left', flexBasis: `${llmPct * 100}%`, backgroundColor: LLM_COLOR }}
                  className="h-full rounded-full"
                />
              </div>

              <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <span aria-hidden className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: CLASSIFIER_COLOR }} />
                  <Zap className="h-3.5 w-3.5 text-muted-foreground" />
                  <dt className="text-muted-foreground">Classifier</dt>
                  <dd className="font-semibold tabular-nums">
                    {data.classifier_count.toLocaleString()} <span className="font-normal text-muted-foreground">({pct(classifierPct)})</span>
                  </dd>
                </div>
                <div className="flex items-center gap-2">
                  <span aria-hidden className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: LLM_COLOR }} />
                  <Brain className="h-3.5 w-3.5 text-muted-foreground" />
                  <dt className="text-muted-foreground">LLM-escalated</dt>
                  <dd className="font-semibold tabular-nums">
                    {data.llm_count.toLocaleString()} <span className="font-normal text-muted-foreground">({pct(llmPct)})</span>
                  </dd>
                </div>
              </dl>
            </>
          )}
        </Card>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: easeOut, delay: 0.2 }}
      >
        <Card className={cn('p-5', panelSurface)}>
          <h2 className="text-sm font-semibold">Most-flagged hypotheses</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            The hypotheses that came back Contradiction most often, across all documents.
          </p>

          {data.top_hypotheses.length === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">No contradictions flagged yet.</p>
          ) : (
            <TopHypothesesChart items={data.top_hypotheses} />
          )}
        </Card>
      </motion.div>
    </div>
  );
}

function truncate(text: string, max: number) {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function TopHypothesesChart({ items }: { items: Analytics['top_hypotheses'] }) {
  const rowHeight = 40;
  return (
    <div className="mt-2" style={{ height: items.length * rowHeight + 24 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={items}
          layout="vertical"
          margin={{ top: 8, right: 32, bottom: 8, left: 0 }}
          barCategoryGap={8}
        >
          <CartesianGrid horizontal={false} stroke="hsl(var(--border))" />
          <XAxis
            type="number"
            allowDecimals={false}
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
            axisLine={{ stroke: 'hsl(var(--border))' }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="hypothesis"
            width={160}
            tickFormatter={(value: string) => truncate(value, 22)}
            tick={{ fill: 'hsl(var(--foreground))', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: 'hsl(var(--accent))' }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const row = payload[0].payload as Analytics['top_hypotheses'][number];
              return (
                <div className="max-w-[260px] rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-lg">
                  <p className="text-foreground/80">{row.hypothesis}</p>
                  <p className="mt-1 font-semibold text-foreground">
                    {row.contradiction_count} contradiction{row.contradiction_count === 1 ? '' : 's'}
                  </p>
                </div>
              );
            }}
          />
          <Bar dataKey="contradiction_count" fill={BAR_COLOR} radius={[0, 4, 4, 0]} maxBarSize={22}>
            <LabelList
              dataKey="contradiction_count"
              position="right"
              className="fill-muted-foreground"
              style={{ fontSize: 12, fontWeight: 600 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-6" aria-busy>
      <span className="sr-only" role="status">Loading analytics</span>
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
        <div className="skeleton h-3 w-full" />
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
      <p className="text-sm font-medium">Couldn't load analytics</p>
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

function EmptyState() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-border/70 bg-secondary/50">
        <BarChart3 className="h-6 w-6 text-muted-foreground" />
      </div>
      <p className="text-sm font-medium">No analyses yet</p>
      <p className="max-w-xs text-xs text-muted-foreground">
        Run a hypothesis check and this page fills in automatically.
      </p>
      <Button asChild size="sm">
        <Link to="/app">
          <ScanSearch className="h-4 w-4" />
          Analyze a contract
        </Link>
      </Button>
    </div>
  );
}
