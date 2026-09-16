import { useState, useEffect, useMemo } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut, File } from 'lucide-react';
import type { ReportCitation } from '../types';
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

  if (!file) {
    return (
      <div className="bg-slate-50 border border-slate-200 rounded-2xl h-full flex flex-col items-center justify-center text-slate-400">
        <File className="h-16 w-16 mb-4 opacity-50" />
        <p>No document loaded</p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-slate-200 rounded-2xl h-full flex flex-col overflow-hidden shadow-sm">
      {/* Toolbar */}
      <div className="h-14 border-b border-slate-200 flex items-center justify-between px-4 bg-slate-50 shrink-0">
        <div className="flex items-center gap-2">
          <button 
            onClick={() => setPageNumber(p => Math.max(1, p - 1))}
            disabled={pageNumber <= 1}
            className="p-1.5 rounded hover:bg-slate-200 disabled:opacity-50"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
          <span className="text-sm font-medium text-slate-700 w-24 text-center">
            Page {pageNumber} of {numPages || '--'}
          </span>
          <button 
            onClick={() => setPageNumber(p => Math.min(numPages || p, p + 1))}
            disabled={pageNumber >= (numPages || 1)}
            className="p-1.5 rounded hover:bg-slate-200 disabled:opacity-50"
          >
            <ChevronRight className="h-5 w-5" />
          </button>
        </div>
        
        <div className="flex items-center gap-2">
          <button 
            onClick={() => setScale(s => Math.max(0.5, s - 0.2))}
            className="p-1.5 rounded hover:bg-slate-200"
          >
            <ZoomOut className="h-5 w-5" />
          </button>
          <span className="text-sm font-medium text-slate-700 w-12 text-center">
            {Math.round(scale * 100)}%
          </span>
          <button 
            onClick={() => setScale(s => Math.min(3, s + 0.2))}
            className="p-1.5 rounded hover:bg-slate-200"
          >
            <ZoomIn className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* Viewer Area */}
      <div className="flex-1 overflow-auto bg-slate-100 p-4 flex justify-center relative">
        <Document
          file={fileUrl}
          onLoadSuccess={onDocumentLoadSuccess}
          loading={
            <div className="flex items-center justify-center h-full">
              <span className="text-slate-500">Loading PDF...</span>
            </div>
          }
          className="relative"
        >
          <Page 
            pageNumber={pageNumber} 
            scale={scale} 
            renderTextLayer={true}
            renderAnnotationLayer={true}
          />
          
          {/* Highlight Overlay Simulation */}
          {activeCitation && activeCitation.page === pageNumber && activeCitation.bbox && (
            <div 
              className="absolute bg-yellow-300/40 border-2 border-yellow-400 rounded cursor-pointer z-10 pointer-events-none transition-all duration-300"
              style={{
                // In a real app, you'd map PDF coordinate space to pixels based on scale
                // These are just mock styles for demonstration
                top: `${activeCitation.bbox[1] * scale}px`,
                left: `${activeCitation.bbox[0] * scale}px`,
                width: `${(activeCitation.bbox[2] - activeCitation.bbox[0]) * scale}px`,
                height: `${(activeCitation.bbox[3] - activeCitation.bbox[1]) * scale}px`,
              }}
            />
          )}
        </Document>
      </div>
    </div>
  );
}
