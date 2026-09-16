
import { FileText, CheckCircle, XCircle, HelpCircle } from 'lucide-react';
import type { ReportResult, ReportCitation } from '../types';

interface ReportPanelProps {
  result: ReportResult | null;
  onCitationClick: (citation: ReportCitation) => void;
}

export function ReportPanel({ result, onCitationClick }: ReportPanelProps) {
  if (!result) {
    return (
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 h-full flex flex-col items-center justify-center text-center opacity-50">
        <FileText className="h-10 w-10 text-slate-300 mb-3" />
        <p className="text-sm text-slate-500">Run a hypothesis to see the extraction results here.</p>
      </div>
    );
  }

  const getLabelConfig = (label: string) => {
    switch (label) {
      case 'Entailment':
        return { color: 'text-green-700', bg: 'bg-green-100', border: 'border-green-200', icon: CheckCircle };
      case 'Contradiction':
        return { color: 'text-red-700', bg: 'bg-red-100', border: 'border-red-200', icon: XCircle };
      default:
        return { color: 'text-slate-700', bg: 'bg-slate-100', border: 'border-slate-200', icon: HelpCircle };
    }
  };

  const config = getLabelConfig(result.label);
  const Icon = config.icon;

  return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 h-full flex flex-col">
      <h2 className="text-lg font-semibold mb-4 text-slate-800 flex items-center gap-2">
        <FileText className="h-5 w-5 text-blue-500" />
        3. Extraction Report
      </h2>

      <div className={`mb-6 p-4 rounded-xl border ${config.border} ${config.bg} flex items-start gap-3`}>
        <Icon className={`h-6 w-6 ${config.color} shrink-0 mt-0.5`} />
        <div>
          <div className={`text-sm font-bold uppercase tracking-wider mb-1 ${config.color}`}>
            {result.label}
          </div>
          <p className="text-sm text-slate-700 leading-relaxed">
            {result.reasoning}
          </p>
        </div>
      </div>

      <div className="flex-1">
        <h3 className="text-sm font-medium text-slate-600 mb-3">Cited Clauses</h3>
        {result.cited_clauses.length === 0 ? (
          <p className="text-sm text-slate-400 italic">No clauses cited for this result.</p>
        ) : (
          <div className="space-y-3 flex-1 overflow-y-auto">
            {result.cited_clauses.map((clause) => (
              <div 
                key={clause.id}
                onClick={() => onCitationClick(clause)}
                className="p-3 rounded-lg border border-slate-200 hover:border-blue-300 hover:bg-blue-50 cursor-pointer transition-colors group"
              >
                <div className="text-xs font-medium text-slate-400 mb-1 flex justify-between">
                  <span>Page {clause.page}</span>
                  <span className="text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity">View in PDF →</span>
                </div>
                <p className="text-sm text-slate-700 line-clamp-3">"{clause.text}"</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
