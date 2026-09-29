import { useState, type ReactNode } from 'react';
import { motion } from 'framer-motion';
import { Check } from 'lucide-react';
import { UploadPanel } from '../components/UploadPanel';
import { HypothesisPanel } from '../components/HypothesisPanel';
import { ReportPanel } from '../components/ReportPanel';
import { PDFViewer } from '../components/PDFViewer';
import type { ReportResult, ReportCitation } from '../types';
import { AppHeader } from '@/components/AppHeader';
import { WavyBlobs } from '@/components/landing/effects/wavy-blobs';
import { cn } from '@/lib/utils';
import { easeOut } from '@/lib/design';
import { API_BASE } from '@/lib/api';

const STEPS = ['Upload', 'Check', 'Report'] as const;

function StepRail({ current }: { current: number }) {
  return (
    <ol aria-label="Progress" className="hidden items-center gap-1 lg:flex">
      {STEPS.map((step, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <li key={step} className="flex items-center gap-1">
            <span
              aria-current={active ? 'step' : undefined}
              className={cn(
                'relative flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium transition-colors duration-300',
                active ? 'text-foreground' : done ? 'text-foreground/80' : 'text-muted-foreground'
              )}
            >
              {active && (
                <motion.span
                  layoutId="step-rail-active"
                  className="absolute inset-0 rounded-full bg-primary/15 ring-1 ring-primary/40"
                  transition={{ duration: 0.4, ease: easeOut }}
                />
              )}
              <span
                className={cn(
                  'relative flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-bold tabular-nums transition-colors duration-300',
                  done ? 'bg-gradient-brand text-white' : active ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
                )}
              >
                {done ? <Check className="h-2.5 w-2.5" strokeWidth={3} /> : i + 1}
              </span>
              <span className="relative">{step}</span>
            </span>
            {i < STEPS.length - 1 && (
              <span className="relative h-px w-6 overflow-hidden bg-border" aria-hidden>
                <motion.span
                  className="absolute inset-0 origin-left bg-gradient-brand"
                  initial={false}
                  animate={{ scaleX: done ? 1 : 0 }}
                  transition={{ duration: 0.5, ease: easeOut }}
                />
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}

function StepPanel({
  active,
  delay,
  className,
  children,
}: {
  active: boolean;
  delay: number;
  className?: string;
  children: ReactNode;
}) {
  return (
    <motion.div
      layout="position"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: easeOut, delay, layout: { duration: 0.35, ease: easeOut } }}
      className={cn(
        'rounded-2xl transition-shadow duration-500',
        active &&
          'shadow-[0_0_0_1px_hsl(var(--primary)/0.45),0_20px_48px_-24px_hsl(var(--primary)/0.6)]',
        className
      )}
    >
      {children}
    </motion.div>
  );
}

export function AppPage() {
  const [file, setFile] = useState<File | null>(null);
  const [docId, setDocId] = useState<string | null>(null);
  const [activeResult, setActiveResult] = useState<ReportResult | null>(null);
  const [activeCitation, setActiveCitation] = useState<ReportCitation | null>(null);
  const [isChecking, setIsChecking] = useState(false);

  const currentStep = !file ? 0 : isChecking || activeResult ? 2 : 1;

  const handleUploadComplete = (uploadedFile: File, uploadedDocId: string) => {
    setFile(uploadedFile);
    setDocId(uploadedDocId);
    setActiveResult(null);
    setActiveCitation(null);
  };

  const handleCheckHypothesis = async (hypothesis: string) => {
    if (!docId) return;

    setIsChecking(true);
    setActiveCitation(null);

    try {
      const response = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          doc_id: docId,
          hypothesis: hypothesis
        }),
      });

      if (!response.ok) {
        throw new Error('Analysis failed');
      }

      const result = await response.json();
      setActiveResult(result);
    } catch (error) {
      console.error(error);
      alert('Failed to analyze hypothesis.');
    } finally {
      setIsChecking(false);
    }
  };

  const handleCitationClick = (citation: ReportCitation) => {
    setActiveCitation(citation);
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-noise" />
      <WavyBlobs className="-z-10 opacity-60" />

      <AppHeader center={<StepRail current={currentStep} />} />

      {/* Main Content Dashboard */}
      <main className="relative mx-auto flex h-[calc(100vh-64px)] max-w-[1600px] flex-col gap-6 p-6 lg:flex-row">
        {/* Left Column: Interaction & Results */}
        <motion.div
          layoutScroll
          className="-ml-1 -mt-1 flex w-full shrink-0 flex-col gap-6 overflow-y-auto px-1 pt-1 pb-6 lg:w-[408px]"
        >
          <StepPanel active={currentStep === 0} delay={0.05}>
            <UploadPanel onUploadComplete={handleUploadComplete} />
          </StepPanel>

          <StepPanel active={currentStep === 1} delay={0.12}>
            <HypothesisPanel
              onCheck={handleCheckHypothesis}
              disabled={!file}
              isChecking={isChecking}
            />
          </StepPanel>

          <StepPanel active={currentStep === 2} delay={0.19} className="flex min-h-[320px] shrink-0 grow flex-col">
            <ReportPanel
              result={activeResult}
              isChecking={isChecking}
              onCitationClick={handleCitationClick}
            />
          </StepPanel>
        </motion.div>

        {/* Right Column: Document Viewer */}
        <motion.div
          className="min-h-[420px] flex-1"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: easeOut, delay: 0.1 }}
        >
          <PDFViewer file={file} activeCitation={activeCitation} />
        </motion.div>
      </main>
    </div>
  );
}
