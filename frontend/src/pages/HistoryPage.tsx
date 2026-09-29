import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import {
  AlertCircle,
  Brain,
  ChevronDown,
  FileText,
  FileX,
  History as HistoryIcon,
  RotateCw,
  ScanSearch,
  Search,
  X,
  Zap,
} from 'lucide-react';
import { AppHeader } from '@/components/AppHeader';
import { ReportPanel } from '@/components/ReportPanel';
import { PDFViewer } from '@/components/PDFViewer';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { WavyBlobs } from '@/components/landing/effects/wavy-blobs';
import { API_BASE } from '@/lib/api';
import { easeOut, panelSurface } from '@/lib/design';
import { LABEL_CONFIG, verdictConfig, type VerdictLabel } from '@/lib/verdict';
import { cn } from '@/lib/utils';
import type { HistoryDocument, HistoryItem, HistoryPage as HistoryPageData, ReportCitation, ReportResult } from '../types';

const PAGE_SIZE = 20;

const RANGES = [
  { value: 'all', label: 'Any time', ms: 0 },
  { value: '24h', label: 'Last 24 hours', ms: 24 * 3600e3 },
  { value: '7d', label: 'Last 7 days', ms: 7 * 24 * 3600e3 },
  { value: '30d', label: 'Last 30 days', ms: 30 * 24 * 3600e3 },
] as const;
type Range = (typeof RANGES)[number]['value'];

const LABELS = Object.keys(LABEL_CONFIG) as VerdictLabel[];

const relativeTime = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });

function timeAgo(iso: string) {
  const seconds = (new Date(iso).getTime() - Date.now()) / 1000;
  const steps: [Intl.RelativeTimeFormatUnit, number][] = [
    ['year', 31536000],
    ['month', 2592000],
    ['week', 604800],
    ['day', 86400],
    ['hour', 3600],
    ['minute', 60],
  ];
  for (const [unit, size] of steps) {
    if (Math.abs(seconds) >= size) return relativeTime.format(Math.round(seconds / size), unit);
  }
  return 'just now';
}

function fullDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

type ListState = { key: string; items: HistoryItem[]; total: number; error: boolean };
type DetailState = { id: number; result: ReportResult | null };

export function HistoryPage() {
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [label, setLabel] = useState<VerdictLabel | ''>('');
  const [documentId, setDocumentId] = useState('');
  const [range, setRange] = useState<Range>('all');
  const [reload, setReload] = useState(0);

  const [list, setList] = useState<ListState | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [documents, setDocuments] = useState<HistoryDocument[]>([]);

  const [selected, setSelected] = useState<HistoryItem | null>(null);
  const [detail, setDetail] = useState<DetailState | null>(null);
  const [pdfs, setPdfs] = useState<Record<string, File | 'missing'>>({});
  const [activeCitation, setActiveCitation] = useState<ReportCitation | null>(null);
  const detailRef = useRef<HTMLElement>(null);

  const requestKey = JSON.stringify({ debouncedQuery, label, documentId, range, reload });
  const listLoading = list?.key !== requestKey;
  const hasFilters = Boolean(debouncedQuery || label || documentId || range !== 'all');

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => clearTimeout(t);
  }, [query]);

  const buildParams = (offset: number) => {
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
    if (debouncedQuery) params.set('q', debouncedQuery);
    if (label) params.set('label', label);
    if (documentId) params.set('document_id', documentId);
    const ms = RANGES.find((r) => r.value === range)?.ms;
    if (ms) params.set('since', new Date(Date.now() - ms).toISOString());
    return params;
  };

  useEffect(() => {
    const ctrl = new AbortController();
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/history?${buildParams(0)}`, { signal: ctrl.signal });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const page: HistoryPageData = await res.json();
        setList({ key: requestKey, items: page.items, total: page.total, error: false });
      } catch (err) {
        if (ctrl.signal.aborted) return;
        console.error(err);
        setList({ key: requestKey, items: [], total: 0, error: true });
      }
    })();
    return () => ctrl.abort();
    // buildParams reads exactly the values encoded in requestKey.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestKey]);

  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${API_BASE}/history/documents`, { signal: ctrl.signal })
      .then((res) => (res.ok ? res.json() : []))
      .then((docs: HistoryDocument[]) => setDocuments(docs))
      .catch(() => {});
    return () => ctrl.abort();
  }, [reload]);

  useEffect(() => {
    if (!selected) return;
    const ctrl = new AbortController();
    const { id, document_id: docId, filename } = selected;

    fetch(`${API_BASE}/history/${id}`, { signal: ctrl.signal })
      .then((res) => (res.ok ? res.json() : null))
      .then((result: ReportResult | null) => setDetail({ id, result }))
      .catch(() => !ctrl.signal.aborted && setDetail({ id, result: null }));

    if (!(docId in pdfs)) {
      fetch(`${API_BASE}/documents/${docId}/file`, { signal: ctrl.signal })
        .then(async (res) => {
          const value = res.ok ? new File([await res.blob()], filename, { type: 'application/pdf' }) : 'missing';
          setPdfs((prev) => ({ ...prev, [docId]: value }));
        })
        .catch(() => !ctrl.signal.aborted && setPdfs((prev) => ({ ...prev, [docId]: 'missing' })));
    }
    return () => ctrl.abort();
    // pdfs is a cache; re-running when it fills would refetch the report.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  const loadMore = async () => {
    if (!list) return;
    setLoadingMore(true);
    try {
      const res = await fetch(`${API_BASE}/history?${buildParams(list.items.length)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const page: HistoryPageData = await res.json();
      setList((prev) =>
        prev && prev.key === requestKey
          ? { ...prev, items: [...prev.items, ...page.items], total: page.total }
          : prev
      );
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingMore(false);
    }
  };

  const select = (item: HistoryItem) => {
    setSelected(item);
    setActiveCitation(null);
    if (window.matchMedia('(max-width: 1023px)').matches) {
      requestAnimationFrame(() => detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
    }
  };

  const clearFilters = () => {
    setQuery('');
    setDebouncedQuery('');
    setLabel('');
    setDocumentId('');
    setRange('all');
  };

  const detailLoading = selected !== null && detail?.id !== selected.id;
  const pdf = selected ? pdfs[selected.document_id] : undefined;

  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-noise" />
      <WavyBlobs className="-z-10 opacity-60" />

      <AppHeader />

      <main className="relative mx-auto flex max-w-[1600px] flex-col gap-6 p-4 sm:p-6 lg:h-[calc(100vh-64px)] lg:flex-row">
        {/* Left: filters + list */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: easeOut }}
          className="flex w-full shrink-0 flex-col lg:w-[440px]"
        >
          <Card className={cn('flex min-h-0 flex-1 flex-col p-5', panelSurface)}>
            <div className="mb-4 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-primary">
                  <HistoryIcon className="h-3.5 w-3.5" />
                </span>
                <h1 className="text-base font-semibold">Analysis History</h1>
              </div>
              {list && !list.error && (
                <span className="rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium tabular-nums text-muted-foreground">
                  {list.total} {list.total === 1 ? 'result' : 'results'}
                </span>
              )}
            </div>

            {/* Filters */}
            <div className="space-y-3">
              <label className="relative block">
                <span className="sr-only">Search hypotheses and file names</span>
                <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search hypotheses or file names…"
                  className="h-10 w-full rounded-xl border border-input bg-background/60 pl-10 pr-4 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background"
                />
              </label>

              <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by verdict">
                <FilterChip active={label === ''} onClick={() => setLabel('')}>
                  All
                </FilterChip>
                {LABELS.map((l) => (
                  <FilterChip key={l} active={label === l} onClick={() => setLabel(label === l ? '' : l)}>
                    <span className={cn('h-1.5 w-1.5 rounded-full', LABEL_CONFIG[l].dot)} />
                    {LABEL_CONFIG[l].display}
                  </FilterChip>
                ))}
              </div>

              <div className="grid grid-cols-2 gap-2">
                <SelectField
                  label="Document"
                  value={documentId}
                  onChange={setDocumentId}
                  options={[
                    { value: '', label: 'All documents' },
                    ...documents.map((d) => ({ value: d.id, label: `${d.filename} (${d.analysis_count})` })),
                  ]}
                />
                <SelectField
                  label="Date"
                  value={range}
                  onChange={(v) => setRange(v as Range)}
                  options={RANGES.map((r) => ({ value: r.value, label: r.label }))}
                />
              </div>
            </div>

            <div className="my-4 h-px bg-border/70" />

            {/* List */}
            <div className="-mx-1 min-h-[240px] flex-1 overflow-y-auto px-1 pb-1" aria-busy={listLoading}>
              {listLoading ? (
                <ListSkeleton />
              ) : list?.error ? (
                <ListMessage
                  icon={<AlertCircle className="h-6 w-6 text-red-500" />}
                  title="Couldn't load history"
                  body="The backend didn't respond. Make sure it's running, then try again."
                  action={
                    <Button variant="outline" size="sm" onClick={() => setReload((n) => n + 1)}>
                      <RotateCw className="h-4 w-4" />
                      Retry
                    </Button>
                  }
                />
              ) : list && list.items.length === 0 ? (
                hasFilters ? (
                  <ListMessage
                    icon={<Search className="h-6 w-6 text-muted-foreground" />}
                    title="No analyses match these filters"
                    action={
                      <Button variant="outline" size="sm" onClick={clearFilters}>
                        <X className="h-4 w-4" />
                        Clear filters
                      </Button>
                    }
                  />
                ) : (
                  <ListMessage
                    icon={<HistoryIcon className="h-6 w-6 text-muted-foreground" />}
                    title="No analyses yet"
                    body="Every hypothesis you check is saved here automatically."
                    action={
                      <Button asChild size="sm">
                        <Link to="/app">
                          <ScanSearch className="h-4 w-4" />
                          Analyze a contract
                        </Link>
                      </Button>
                    }
                  />
                )
              ) : (
                <ul className="space-y-2">
                  {list?.items.map((item, i) => (
                    <HistoryRow
                      key={item.id}
                      item={item}
                      index={i % PAGE_SIZE}
                      selected={selected?.id === item.id}
                      onSelect={() => select(item)}
                    />
                  ))}
                </ul>
              )}

              {list && !listLoading && list.items.length < list.total && (
                <div className="pt-3 text-center">
                  <Button variant="secondary" size="sm" onClick={loadMore} disabled={loadingMore}>
                    {loadingMore ? 'Loading…' : `Load more (${list.total - list.items.length} left)`}
                  </Button>
                </div>
              )}
            </div>
          </Card>
        </motion.div>

        {/* Right: selected report */}
        <motion.section
          ref={detailRef}
          aria-label="Selected analysis"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: easeOut, delay: 0.1 }}
          className="flex min-h-[420px] min-w-0 flex-1 scroll-mt-20 flex-col gap-6 xl:flex-row"
        >
          {!selected ? (
            <EmptyDetail />
          ) : (
            <>
              <div className="flex w-full shrink-0 flex-col gap-4 xl:w-[400px] xl:overflow-y-auto xl:pb-2">
                <AnimatePresence mode="wait" initial={false}>
                  <motion.div
                    key={selected.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.25, ease: easeOut }}
                  >
                    <Card className={cn('p-5', panelSurface)}>
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                        Hypothesis
                      </p>
                      <p className="mt-1 text-sm font-medium leading-relaxed">{selected.hypothesis}</p>
                      <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                        <span className="flex min-w-0 items-center gap-1.5">
                          <FileText className="h-3.5 w-3.5 shrink-0" />
                          <span className="truncate">{selected.filename}</span>
                        </span>
                        <span aria-hidden>·</span>
                        <time dateTime={selected.created_at}>{fullDate(selected.created_at)}</time>
                      </div>
                    </Card>
                  </motion.div>
                </AnimatePresence>

                <div className="flex min-h-[320px] flex-1 flex-col">
                  {detailLoading ? (
                    <DetailSkeleton />
                  ) : detail?.result ? (
                    <ReportPanel result={detail.result} isChecking={false} onCitationClick={setActiveCitation} />
                  ) : (
                    <Card className={cn('flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center', panelSurface)}>
                      <AlertCircle className="h-6 w-6 text-red-500" />
                      <p className="text-sm font-medium">Couldn't load this report</p>
                      <Button variant="outline" size="sm" onClick={() => setSelected({ ...selected })}>
                        <RotateCw className="h-4 w-4" />
                        Retry
                      </Button>
                    </Card>
                  )}
                </div>
              </div>

              <div className="min-h-[480px] min-w-0 flex-1">
                {pdf === undefined ? (
                  <div className={cn('flex h-full flex-col items-center justify-center rounded-2xl border p-8', panelSurface)}>
                    <div className="skeleton aspect-[8.5/11] w-full max-w-[420px]" />
                    <span className="sr-only" role="status">Loading PDF</span>
                  </div>
                ) : pdf === 'missing' ? (
                  <div
                    className={cn(
                      'flex h-full flex-col items-center justify-center rounded-2xl border p-8 text-center text-muted-foreground',
                      panelSurface
                    )}
                  >
                    <div className="mb-4 flex h-20 w-20 items-center justify-center rounded-3xl border border-border/70 bg-secondary/50">
                      <FileX className="h-9 w-9 opacity-50" />
                    </div>
                    <p className="text-sm font-medium text-foreground/80">Original PDF not available</p>
                    <p className="mt-1 max-w-xs text-xs">
                      The file is no longer on the server, so citations can't be shown in the document.
                    </p>
                  </div>
                ) : (
                  <PDFViewer file={pdf} activeCitation={activeCitation} />
                )}
              </div>
            </>
          )}
        </motion.section>
      </main>
    </div>
  );
}

function FilterChip({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        'flex h-8 items-center gap-1.5 rounded-full border px-3 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-[0.97]',
        active
          ? 'border-primary/50 bg-primary/15 text-foreground'
          : 'border-border bg-secondary/40 text-muted-foreground hover:border-primary/30 hover:text-foreground'
      )}
    >
      {children}
    </button>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="relative block min-w-0">
      <span className="sr-only">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-10 w-full appearance-none truncate rounded-xl border border-input bg-background/60 pl-3 pr-9 text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
    </label>
  );
}

function HistoryRow({
  item,
  index,
  selected,
  onSelect,
}: {
  item: HistoryItem;
  index: number;
  selected: boolean;
  onSelect: () => void;
}) {
  const config = verdictConfig(item.label);
  const Icon = config.icon;

  return (
    <motion.li
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: easeOut, delay: Math.min(index, 8) * 0.04 }}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-current={selected ? 'true' : undefined}
        className={cn(
          'group w-full rounded-xl border p-3 text-left transition-[border-color,background-color,box-shadow,transform] duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-[0.99]',
          selected
            ? 'border-primary/50 bg-primary/[0.08] shadow-[0_10px_28px_-16px_hsl(var(--primary)/0.8)]'
            : 'border-border bg-secondary/30 hover:border-primary/30 hover:bg-primary/[0.04]'
        )}
      >
        <div className="mb-1 flex items-center justify-between gap-3 text-[11px] text-muted-foreground">
          <span className="flex min-w-0 items-center gap-1">
            <FileText className="h-3 w-3 shrink-0" />
            <span className="truncate">{item.filename}</span>
          </span>
          <time dateTime={item.created_at} title={fullDate(item.created_at)} className="shrink-0 tabular-nums">
            {timeAgo(item.created_at)}
          </time>
        </div>
        <p className="line-clamp-2 text-sm font-medium leading-snug">{item.hypothesis}</p>
        <div className="mt-2 flex items-center gap-2">
          <span
            className={cn(
              'flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
              config.text,
              config.bg,
              config.border
            )}
          >
            <Icon className="h-3 w-3" />
            {config.display}
          </span>
          {item.source && (
            <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
              {item.source === 'classifier' ? <Zap className="h-3 w-3" /> : <Brain className="h-3 w-3" />}
              {item.source === 'classifier' ? 'Classifier' : 'LLM'}
              {typeof item.confidence === 'number' && (
                <span className="tabular-nums">· {Math.round(item.confidence * 100)}%</span>
              )}
            </span>
          )}
        </div>
      </button>
    </motion.li>
  );
}

function ListSkeleton() {
  return (
    <div aria-hidden className="space-y-2">
      {[0, 1, 2, 3, 4].map((i) => (
        <div key={i} className="space-y-2 rounded-xl border border-border/60 p-3">
          <div className="flex justify-between">
            <div className="skeleton h-2.5 w-32" />
            <div className="skeleton h-2.5 w-12" />
          </div>
          <div className="skeleton h-3.5 w-4/5" />
          <div className="skeleton h-4 w-24 rounded-full" />
        </div>
      ))}
    </div>
  );
}

function ListMessage({
  icon,
  title,
  body,
  action,
}: {
  icon: ReactNode;
  title: string;
  body?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex h-full min-h-[220px] flex-col items-center justify-center gap-2 px-4 text-center">
      <div className="mb-1 flex h-12 w-12 items-center justify-center rounded-2xl border border-border/70 bg-secondary/50">
        {icon}
      </div>
      <p className="text-sm font-medium">{title}</p>
      {body && <p className="max-w-xs text-xs text-muted-foreground">{body}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

function DetailSkeleton() {
  return (
    <Card className={cn('flex flex-1 flex-col gap-4 p-6', panelSurface)} aria-busy>
      <span className="sr-only" role="status">Loading report</span>
      <div className="skeleton h-4 w-40" />
      <div className="space-y-3 rounded-2xl border border-border/60 p-4">
        <div className="skeleton h-3.5 w-28" />
        <div className="skeleton h-1.5 w-full rounded-full" />
        <div className="skeleton h-3 w-full" />
        <div className="skeleton h-3 w-3/4" />
      </div>
      <div className="skeleton h-16 w-full rounded-xl" />
      <div className="skeleton h-16 w-full rounded-xl" />
    </Card>
  );
}

function EmptyDetail() {
  return (
    <div
      className={cn(
        'flex flex-1 flex-col items-center justify-center rounded-2xl border p-8 text-center text-muted-foreground',
        panelSurface
      )}
    >
      <div className="mb-4 flex h-20 w-20 items-center justify-center rounded-3xl border border-border/70 bg-secondary/50">
        <HistoryIcon className="h-9 w-9 opacity-50" />
      </div>
      <p className="text-sm font-medium text-foreground/80">Select an analysis</p>
      <p className="mt-1 text-xs">Its full report and the original contract open here.</p>
    </div>
  );
}
