import { Fragment, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { FileText, ChevronRight, ChevronDown, Loader2, Zap, Brain, Search, Gauge, CheckCircle2 } from 'lucide-react';
import type { ReportResult, ReportCitation, TriageDetail } from '../types';
import { cn } from '../utils/cn';
import { Card } from './ui/card';
import { easeOut, panelSurface } from '@/lib/design';
import { verdictConfig } from '@/lib/verdict';

interface ReportPanelProps {
  result: ReportResult | null;
  isChecking: boolean;
  onCitationClick: (citation: ReportCitation) => void;
}

function PanelHeader() {
  return (
    <div className="mb-4 flex items-center gap-2">
      <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-xs font-bold text-primary">
        3
      </span>
      <h2 className="text-base font-semibold">Extraction Report</h2>
    </div>
  );
}

function CheckingState() {
  return (
    <Card className={cn('flex flex-1 flex-col p-6', panelSurface)}>
      <PanelHeader />
      <div role="status" aria-live="polite" className="mb-4 flex items-start gap-2.5">
        <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-primary" />
        <div>
          <p className="text-sm font-medium">Reasoning over evidence…</p>
          <p className="text-xs text-muted-foreground">This can take a few seconds.</p>
        </div>
      </div>
      <div aria-hidden className="space-y-5">
        <div className="space-y-3 rounded-2xl border border-border/60 p-4">
          <div className="flex items-center justify-between">
            <div className="skeleton h-3.5 w-28" />
            <div className="skeleton h-4 w-20 rounded-full" />
          </div>
          <div className="skeleton h-1.5 w-full rounded-full" />
          <div className="space-y-2">
            <div className="skeleton h-3 w-full" />
            <div className="skeleton h-3 w-11/12" />
            <div className="skeleton h-3 w-3/5" />
          </div>
        </div>
        <div className="space-y-2">
          <div className="skeleton h-3 w-24" />
          {[0, 1, 2].map((i) => (
            <div key={i} className="space-y-2 rounded-xl border border-border/60 p-3">
              <div className="skeleton h-2.5 w-14" />
              <div className="skeleton h-3 w-full" />
              <div className="skeleton h-3 w-4/5" />
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

function EmptyState() {
  return (
    <Card
      className={cn(
        'flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center text-muted-foreground',
        panelSurface
      )}
    >
      <FileText className="h-9 w-9 opacity-40" />
      <p className="text-sm">Run a hypothesis to see the extraction results here.</p>
    </Card>
  );
}

type TrailStep = { key: string; label: string; icon: typeof Search; state: 'done' | 'taken' | 'skipped' };

function DecisionTrail({ triage }: { triage?: TriageDetail }) {
  const [open, setOpen] = useState(false);
  if (!triage) return null;

  const accepted = triage.decision === 'accept';
  const pct = triage.confidence !== null ? Math.round(triage.confidence * 100) : null;
  const thresholdPct = Math.round(triage.threshold * 100);

  const steps: TrailStep[] = [
    { key: 'retrieve', label: 'Retrieve', icon: Search, state: 'done' },
    { key: 'triage', label: 'Triage', icon: Gauge, state: 'done' },
    {
      key: accepted ? 'accept' : 'escalate',
      label: accepted ? 'Accept' : 'Escalate to LLM',
      icon: accepted ? CheckCircle2 : Brain,
      state: 'taken',
    },
  ];

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex items-center gap-1.5 rounded-md text-xs font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      >
        {open ? 'Hide reasoning' : 'Show reasoning'}
        <ChevronDown className={cn('h-3.5 w-3.5 transition-transform duration-200', open && 'rotate-180')} />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: easeOut }}
            className="overflow-hidden"
          >
            <div className="mt-3 rounded-xl border border-border/60 bg-secondary/20 p-4">
              <div className="flex items-center">
                {steps.map((step, i) => {
                  const isFinal = i === steps.length - 1;
                  const StepIcon = step.icon;
                  return (
                    <Fragment key={step.key}>
                      <div className="flex flex-col items-center gap-1.5">
                        <motion.span
                          initial={{ scale: 0.6, opacity: 0 }}
                          animate={{ scale: 1, opacity: 1 }}
                          transition={{ duration: 0.35, ease: easeOut, delay: i * 0.15 }}
                          className={cn(
                            'flex h-8 w-8 items-center justify-center rounded-full border',
                            isFinal
                              ? accepted
                                ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                                : 'border-primary/40 bg-primary/15 text-primary'
                              : 'border-border bg-background text-muted-foreground'
                          )}
                        >
                          <StepIcon className="h-3.5 w-3.5" />
                        </motion.span>
                        <span
                          className={cn(
                            'whitespace-nowrap text-[10px] font-medium',
                            isFinal ? 'text-foreground' : 'text-muted-foreground'
                          )}
                        >
                          {step.label}
                        </span>
                      </div>
                      {!isFinal && (
                        <span className="relative mx-1 h-px flex-1 -translate-y-2.5 overflow-hidden bg-border" aria-hidden>
                          <motion.span
                            className="absolute inset-0 origin-left bg-primary/50"
                            initial={{ scaleX: 0 }}
                            animate={{ scaleX: 1 }}
                            transition={{ duration: 0.4, ease: easeOut, delay: i * 0.15 + 0.2 }}
                          />
                        </span>
                      )}
                    </Fragment>
                  );
                })}
              </div>

              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.3, delay: 0.5 }}
                className="mt-4 text-xs leading-relaxed text-muted-foreground"
              >
                Triage classified this as <strong className="font-semibold text-foreground">{triage.label ?? 'unknown'}</strong>
                {pct !== null && (
                  <>
                    {' '}at <strong className="font-semibold tabular-nums text-foreground">{pct}%</strong> confidence
                  </>
                )}
                {accepted ? (
                  <> — at or above the {thresholdPct}% threshold, so it was accepted directly, with no LLM call.</>
                ) : (
                  <> — below the {thresholdPct}% threshold, so it was escalated to the LLM for deeper reasoning.</>
                )}
              </motion.p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function ResultState({ result, onCitationClick }: { result: ReportResult; onCitationClick: (c: ReportCitation) => void }) {
  const config = verdictConfig(result.label);
  const Icon = config.icon;
  const confidence = typeof result.confidence === 'number' ? result.confidence : null;
  const confidencePct = confidence === null ? null : Math.round(confidence * 100);

  return (
    <Card className={cn('flex flex-1 flex-col p-6', panelSurface)}>
      <PanelHeader />

      <motion.div
        initial={{ opacity: 0, scale: 0.98, filter: 'blur(8px)' }}
        animate={{ opacity: 1, scale: 1, filter: 'blur(0px)', transitionEnd: { filter: 'none' } }}
        transition={{ duration: 0.6, ease: easeOut }}
        className={cn('relative mb-5 overflow-hidden rounded-2xl border p-4', config.border, config.bg)}
      >
        <motion.span
          aria-hidden
          className="pointer-events-none absolute inset-y-0 left-0 w-1/3 -skew-x-12 bg-gradient-to-r from-transparent via-white/20 to-transparent"
          initial={{ x: '-150%' }}
          animate={{ x: '400%' }}
          transition={{ duration: 1.1, ease: easeOut, delay: 0.25 }}
        />

        <div className="relative flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Icon className={cn('h-4 w-4', config.text)} />
            <span className={cn('text-xs font-bold uppercase tracking-wider', config.text)}>
              {result.label}
            </span>
          </div>
          {result.source && (
            <span
              className={cn(
                'flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium',
                result.source === 'classifier'
                  ? 'border-emerald-500/30 text-emerald-600 dark:text-emerald-400'
                  : 'border-primary/30 text-primary'
              )}
              title={
                result.source === 'classifier'
                  ? 'Resolved directly by the triage classifier — no LLM call needed'
                  : 'Escalated to the LLM for deeper reasoning'
              }
            >
              {result.source === 'classifier' ? (
                <>
                  <Zap className="h-3 w-3" />
                  Classifier
                </>
              ) : (
                <>
                  <Brain className="h-3 w-3" />
                  LLM-verified
                </>
              )}
            </span>
          )}
        </div>

        {confidencePct !== null && (
          <div className="relative mt-3">
            <div className="mb-1.5 flex items-center justify-between text-[11px] font-medium text-muted-foreground">
              <span>Classifier confidence</span>
              <span className="tabular-nums text-foreground">{confidencePct}%</span>
            </div>
            <div
              role="meter"
              aria-label="Classifier confidence"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={confidencePct}
              className="h-1.5 overflow-hidden rounded-full bg-foreground/10"
            >
              <motion.div
                className="h-full origin-left rounded-full bg-gradient-brand"
                initial={{ scaleX: 0 }}
                animate={{ scaleX: confidence ?? 0 }}
                transition={{ duration: 0.9, ease: easeOut, delay: 0.3 }}
              />
            </div>
          </div>
        )}

        <p className="relative mt-3 text-sm leading-relaxed text-foreground/90">{result.reasoning}</p>

        <div className="relative">
          <DecisionTrail triage={result.triage} />
        </div>
      </motion.div>

      <div className="flex-1">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Cited Clauses
        </h3>
        {result.cited_clauses.length === 0 ? (
          <p className="text-sm italic text-muted-foreground">No clauses cited for this result.</p>
        ) : (
          <div className="space-y-2">
            {result.cited_clauses.map((clause, i) => (
              <motion.button
                key={clause.id}
                type="button"
                onClick={() => onCitationClick(clause)}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, ease: easeOut, delay: 0.35 + Math.min(i, 6) * 0.05 }}
                whileTap={{ scale: 0.99 }}
                className="group flex w-full items-start gap-3 rounded-xl border border-border bg-secondary/30 p-3 text-left transition-colors hover:border-primary/40 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                <div className="min-w-0 flex-1">
                  <div className="mb-1 text-xs font-medium tabular-nums text-muted-foreground">
                    Page {clause.page}
                  </div>
                  <p className="line-clamp-3 text-sm text-foreground/90">&ldquo;{clause.text}&rdquo;</p>
                </div>
                <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground opacity-0 transition-all group-hover:translate-x-0.5 group-hover:text-primary group-hover:opacity-100 group-focus-visible:opacity-100" />
              </motion.button>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

export function ReportPanel({ result, isChecking, onCitationClick }: ReportPanelProps) {
  const viewKey = isChecking ? 'checking' : result ? `result:${result.label}:${result.reasoning}` : 'empty';

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={viewKey}
        className="flex flex-1 flex-col"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1, transition: { duration: 0.25 } }}
        exit={{ opacity: 0, transition: { duration: 0.15 } }}
      >
        {isChecking ? (
          <CheckingState />
        ) : result ? (
          <ResultState result={result} onCitationClick={onCitationClick} />
        ) : (
          <EmptyState />
        )}
      </motion.div>
    </AnimatePresence>
  );
}
