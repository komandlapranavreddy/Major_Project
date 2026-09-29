import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { AnimatePresence, motion } from 'framer-motion';
import { FileUp, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { cn } from '../utils/cn';
import { easeOut, panelSurface } from '@/lib/design';
import { API_BASE } from '@/lib/api';
import { Card } from './ui/card';
import { Button } from './ui/button';

interface UploadPanelProps {
  onUploadComplete: (file: File, docId: string) => void;
}

type Status = 'idle' | 'uploading' | 'complete' | 'error';

export function UploadPanel({ onUploadComplete }: UploadPanelProps) {
  const [status, setStatus] = useState<Status>('idle');
  const [file, setFile] = useState<File | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;
    const uploadedFile = acceptedFiles[0];
    setFile(uploadedFile);
    setStatus('uploading');
    setErrorMessage(null);

    try {
      const formData = new FormData();
      formData.append('file', uploadedFile);

      const response = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Upload failed');
      }

      const data = await response.json();

      setStatus('complete');
      onUploadComplete(uploadedFile, data.doc_id);
    } catch (error) {
      console.error(error);
      setStatus('error');
      setErrorMessage(error instanceof Error ? error.message : 'Failed to upload document.');
    }
  }, [onUploadComplete]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    disabled: status === 'uploading',
  });

  const view = status === 'uploading' ? 'idle' : status;

  return (
    <Card className={cn('p-6', panelSurface)}>
      <div className="mb-4 flex items-center gap-2">
        <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-xs font-bold text-primary">
          1
        </span>
        <h2 className="text-base font-semibold">Upload Contract</h2>
      </div>

      <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={view}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0, transition: { duration: 0.3, ease: easeOut } }}
        exit={{ opacity: 0, y: -6, transition: { duration: 0.15 } }}
      >
      {(status === 'idle' || status === 'uploading') && (
        <div
          {...getRootProps()}
          className={cn(
            'rounded-2xl border-2 border-dashed p-8 text-center transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
            status === 'uploading'
              ? 'cursor-wait border-primary/40 bg-primary/5'
              : isDragActive
                ? 'cursor-pointer scale-[1.01] border-primary bg-primary/5 shadow-[0_12px_32px_-16px_hsl(var(--primary)/0.6)]'
                : 'cursor-pointer border-border hover:-translate-y-0.5 hover:border-primary/40 hover:bg-accent/40 hover:shadow-[0_12px_28px_-18px_hsl(var(--primary)/0.5)] active:translate-y-0'
          )}
        >
          <input {...getInputProps()} />

          {status === 'uploading' ? (
            <>
              <Loader2 className="mx-auto mb-3 h-9 w-9 animate-spin text-primary" />
              <p className="text-sm font-medium">Uploading {file?.name}…</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Extracting text and layout data
              </p>
              <div className="mx-auto mt-4 h-1.5 w-full max-w-[220px] overflow-hidden rounded-full bg-muted">
                <div className="h-full w-1/3 animate-indeterminate rounded-full bg-gradient-brand" />
              </div>
            </>
          ) : (
            <>
              <div
                className={cn(
                  'mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl transition-colors',
                  isDragActive ? 'bg-primary/15' : 'bg-secondary'
                )}
              >
                <FileUp className={cn('h-6 w-6', isDragActive ? 'text-primary' : 'text-muted-foreground')} />
              </div>
              <p className="text-sm font-medium">Drag & drop a PDF here, or click to select</p>
              <p className="mt-1 text-xs text-muted-foreground">Supports standard PDF contracts</p>
            </>
          )}
        </div>
      )}

      {status === 'complete' && (
        <div className="flex items-center gap-3 rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.06] p-4">
          <motion.span
            initial={{ scale: 0.5, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.4, ease: easeOut, delay: 0.1 }}
            className="shrink-0"
          >
            <CheckCircle2 className="h-6 w-6 text-emerald-500" />
          </motion.span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-emerald-600 dark:text-emerald-400">
              {file?.name}
            </p>
            <p className="text-xs text-muted-foreground">Processed and ready for analysis</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="shrink-0"
            onClick={() => {
              setStatus('idle');
              setFile(null);
            }}
          >
            Replace
          </Button>
        </div>
      )}

      {status === 'error' && (
        <div className="flex items-start gap-3 rounded-2xl border border-red-500/20 bg-red-500/[0.06] p-4">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-500" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-red-500">Upload failed</p>
            <p className="mt-0.5 text-xs text-muted-foreground">{errorMessage}</p>
          </div>
          <Button variant="outline" size="sm" className="shrink-0" onClick={() => setStatus('idle')}>
            Try again
          </Button>
        </div>
      )}
      </motion.div>
      </AnimatePresence>
    </Card>
  );
}
