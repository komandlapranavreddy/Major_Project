import { useState } from 'react';
import { UploadPanel } from './components/UploadPanel';
import { HypothesisPanel } from './components/HypothesisPanel';
import { ReportPanel } from './components/ReportPanel';
import { PDFViewer } from './components/PDFViewer';
import type { ReportResult, ReportCitation } from './types';
import { Scale } from 'lucide-react';

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [docId, setDocId] = useState<string | null>(null);
  const [activeResult, setActiveResult] = useState<ReportResult | null>(null);
  const [activeCitation, setActiveCitation] = useState<ReportCitation | null>(null);
  const [isChecking, setIsChecking] = useState(false);

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
      const response = await fetch('http://localhost:8000/analyze', {
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
    <div className="min-h-screen bg-slate-100 flex flex-col font-sans text-slate-900">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="bg-blue-600 p-2 rounded-lg">
            <Scale className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900 leading-tight">EdgeLegal</h1>
            <p className="text-xs text-slate-500 font-medium tracking-wide uppercase">Document Intelligence Pipeline</p>
          </div>
        </div>
      </header>

      {/* Main Content Dashboard */}
      <main className="flex-1 p-6 flex flex-col lg:flex-row gap-6 h-[calc(100vh-76px)] overflow-hidden">
        
        {/* Left Column: Interaction & Results */}
        <div className="w-full lg:w-1/3 flex flex-col gap-6 overflow-y-auto pr-2 pb-6">
          <UploadPanel onUploadComplete={handleUploadComplete} />
          
          <HypothesisPanel 
            onCheck={handleCheckHypothesis} 
            disabled={!file || isChecking} 
          />
          
          <div className="flex-1 min-h-[300px]">
            {isChecking ? (
              <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 h-full flex flex-col items-center justify-center">
                <div className="animate-pulse flex flex-col items-center">
                  <div className="h-10 w-10 bg-slate-200 rounded-full mb-4"></div>
                  <div className="h-4 w-32 bg-slate-200 rounded mb-2"></div>
                  <div className="h-3 w-48 bg-slate-200 rounded"></div>
                </div>
              </div>
            ) : (
              <ReportPanel 
                result={activeResult} 
                onCitationClick={handleCitationClick} 
              />
            )}
          </div>
        </div>

        {/* Right Column: Document Viewer */}
        <div className="w-full lg:w-2/3 h-full">
          <PDFViewer file={file} activeCitation={activeCitation} />
        </div>

      </main>
    </div>
  );
}

export default App;
