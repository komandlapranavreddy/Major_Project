import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { FileUp, Loader2, CheckCircle2 } from 'lucide-react';
import { cn } from '../utils/cn';

interface UploadPanelProps {
  onUploadComplete: (file: File, docId: string) => void;
}

export function UploadPanel({ onUploadComplete }: UploadPanelProps) {
  const [status, setStatus] = useState<'idle' | 'uploading' | 'extracting' | 'complete'>('idle');
  const [file, setFile] = useState<File | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;
    const uploadedFile = acceptedFiles[0];
    setFile(uploadedFile);
    setStatus('uploading');

    try {
      const formData = new FormData();
      formData.append('file', uploadedFile);

      const response = await fetch('http://localhost:8000/upload', {
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
      setStatus('idle');
      alert('Failed to upload document');
    }
  }, [onUploadComplete]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
  });

  return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
      <h2 className="text-lg font-semibold mb-4 text-slate-800">1. Upload Contract</h2>
      
      {status === 'idle' && (
        <div
          {...getRootProps()}
          className={cn(
            "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors",
            isDragActive ? "border-blue-500 bg-blue-50" : "border-slate-300 hover:border-slate-400 hover:bg-slate-50"
          )}
        >
          <input {...getInputProps()} />
          <FileUp className="mx-auto h-10 w-10 text-slate-400 mb-3" />
          <p className="text-sm font-medium text-slate-700">Drag & drop a PDF here, or click to select</p>
          <p className="text-xs text-slate-500 mt-1">Supports standard PDF contracts</p>
        </div>
      )}

      {status === 'uploading' && (
        <div className="flex flex-col items-center justify-center py-8">
          <Loader2 className="h-8 w-8 text-blue-500 animate-spin mb-3" />
          <p className="text-sm font-medium text-slate-700">Uploading {file?.name}...</p>
        </div>
      )}

      {status === 'extracting' && (
        <div className="flex flex-col items-center justify-center py-8">
          <Loader2 className="h-8 w-8 text-purple-500 animate-spin mb-3" />
          <p className="text-sm font-medium text-slate-700">Extracting text & layout data...</p>
        </div>
      )}

      {status === 'complete' && (
        <div className="flex flex-col items-center justify-center py-8 bg-green-50 rounded-xl border border-green-100">
          <CheckCircle2 className="h-8 w-8 text-green-500 mb-3" />
          <p className="text-sm font-medium text-green-800">Processed {file?.name}</p>
        </div>
      )}
    </div>
  );
}
