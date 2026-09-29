import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { motion } from 'framer-motion';
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut, FileX } from 'lucide-react';
import type { ReportCitation } from '../types';
import { Button } from './ui/button';
import { cn } from '../utils/cn';
import { easeOut, panelSurface } from '@/lib/design';
import 'react-pdf/dist/Page/TextLayer.css';
import 'react-pdf/dist/Page/AnnotationLayer.css';

// Set worker path to local or CDN
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PDFViewerProps {
  file: File | null;
  activeCitation: ReportCitation | null;
}

export function PDFViewer({ file, activeCitation }: PDFViewerProps) {
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(1.0);
  const viewerRef = useRef<HTMLDivElement>(null);
  const [availableWidth, setAvailableWidth] = useState<number | null>(null);
  const [pageWidth, setPageWidth] = useState<number | null>(null);

  // Fit the page to the column, and position highlights with the same scale the page renders at.
  const fitScale = availableWidth && pageWidth ? Math.min(1, availableWidth / pageWidth) : 1;
  const renderScale = scale * fitScale;

  useEffect(() => {
    const el = viewerRef.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => setAvailableWidth(entry.contentRect.width));
    observer.observe(el);
    return () => observer.disconnect();
  }, [file]);

  const scrollToHighlight = useCallback((el: HTMLDivElement | null) => {
    el?.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
  }, []);

  // If a citation is clicked, jump to that page
  useEffect(() => {
    if (activeCitation && activeCitation.page) {
      setPageNumber(activeCitation.page);
    }
  }, [activeCitation]);

  const fileUrl = useMemo(() => (file ? URL.createObjectURL(file) : ''), [file]);

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
    setPageNumber(1);
  }

  const pageSkeleton = (
    <div
      aria-hidden
      className="flex aspect-[8.5/11] max-w-full flex-col gap-3 rounded-sm bg-card p-10 shadow-md"
      style={{ width: `${612 * renderScale}px` }}
    >
      <div className="skeleton mb-4 h-4 w-2/5" />
      {Array.from({ length: 9 }, (_, i) => (
        <div key={i} className={cn('skeleton h-2.5', i % 4 === 3 ? 'mb-3 w-3/5' : 'w-full')} />
      ))}
    </div>
  );

  if (!file) {
    return (
      <div
        className={cn(
          'flex h-full flex-col items-center justify-center rounded-2xl border text-muted-foreground',
          panelSurface
        )}
      >
        <div className="mb-4 flex h-20 w-20 items-center justify-center rounded-3xl border border-border/70 bg-secondary/50">
          <FileX className="h-9 w-9 opacity-50" />
        </div>
        <p className="text-sm font-medium text-foreground/80">No document loaded</p>
        <p className="mt-1 text-xs">Upload a contract to preview it here.</p>
      </div>
    );
  }

  return (
    <div className={cn('flex h-full flex-col overflow-hidden rounded-2xl border', panelSurface)}>
      {/* Toolbar */}
      <div className="glass flex h-14 shrink-0 items-center justify-between border-b border-border/60 px-4">
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setPageNumber((p) => Math.max(1, p - 1))}
            disabled={pageNumber <= 1}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="w-24 text-center text-sm font-medium tabular-nums text-muted-foreground">
            Page {pageNumber} of {numPages || '--'}
          </span>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setPageNumber((p) => Math.min(numPages || p, p + 1))}
            disabled={pageNumber >= (numPages || 1)}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" onClick={() => setScale((s) => Math.max(0.5, s - 0.2))}>
            <ZoomOut className="h-4 w-4" />
          </Button>
          <span className="w-12 text-center text-sm font-medium tabular-nums text-muted-foreground">
            {Math.round(scale * 100)}%
          </span>
          <Button variant="ghost" size="icon" onClick={() => setScale((s) => Math.min(3, s + 0.2))}>
            <ZoomIn className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Viewer Area */}
      <div ref={viewerRef} className="relative flex-1 overflow-auto bg-muted/40 p-4">
        <Document
          file={fileUrl}
          onLoadSuccess={onDocumentLoadSuccess}
          loading={
            <div role="status" aria-label="Loading PDF">
              {pageSkeleton}
            </div>
          }
          className="relative mx-auto w-fit"
        >
          <motion.div
            key={pageNumber}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.25, ease: easeOut }}
          >
            <Page
              pageNumber={pageNumber}
              scale={renderScale}
              onLoadSuccess={(page) => setPageWidth(page.originalWidth)}
              renderTextLayer={true}
              renderAnnotationLayer={true}
              loading={pageSkeleton}
            />
          </motion.div>

          {/* Highlight Overlay Simulation */}
          {activeCitation && activeCitation.page === pageNumber && activeCitation.bbox && (
            <motion.div
              key={activeCitation.id}
              ref={scrollToHighlight}
              initial={{ opacity: 0, scale: 1.06 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4, ease: easeOut }}
              className="pointer-events-none absolute z-10 rounded border-2 border-amber-400 bg-amber-300/30 shadow-[0_0_0_4px_rgba(251,191,36,0.18),0_0_18px_rgba(217,119,6,0.55)]"
              // bbox is in PDF points with a top-left origin (PyMuPDF), same space as originalWidth.
              style={{
                top: `${activeCitation.bbox[1] * renderScale}px`,
                left: `${activeCitation.bbox[0] * renderScale}px`,
                width: `${(activeCitation.bbox[2] - activeCitation.bbox[0]) * renderScale}px`,
                height: `${(activeCitation.bbox[3] - activeCitation.bbox[1]) * renderScale}px`,
              }}
            />
          )}
        </Document>
      </div>
    </div>
  );
}
