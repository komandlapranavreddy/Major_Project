import { useState, type FormEvent } from 'react';
import { Send, Sparkles } from 'lucide-react';
import { cn } from '../utils/cn';

interface HypothesisPanelProps {
  onCheck: (hypothesis: string) => void;
  disabled: boolean;
}

const PREDEFINED_RULES = [
  "Contains confidentiality clause",
  "Terminable for convenience",
  "Governing law is New York"
];

export function HypothesisPanel({ onCheck, disabled }: HypothesisPanelProps) {
  const [customInput, setCustomInput] = useState('');

  const handleCustomSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (customInput.trim()) {
      onCheck(customInput.trim());
    }
  };

  return (
    <div className={cn("bg-white p-6 rounded-2xl shadow-sm border border-slate-200 transition-opacity duration-300", disabled ? "opacity-50 pointer-events-none" : "opacity-100")}>
      <h2 className="text-lg font-semibold mb-4 text-slate-800 flex items-center gap-2">
        <Sparkles className="h-5 w-5 text-indigo-500" />
        2. Check Hypothesis
      </h2>

      <div className="mb-6">
        <label className="text-sm font-medium text-slate-600 mb-2 block">Standard Rules</label>
        <div className="flex flex-wrap gap-2">
          {PREDEFINED_RULES.map((rule) => (
            <button
              key={rule}
              onClick={() => onCheck(rule)}
              className="px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-lg text-sm font-medium hover:bg-indigo-100 transition-colors border border-indigo-100"
            >
              {rule}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleCustomSubmit}>
        <label className="text-sm font-medium text-slate-600 mb-2 block">Custom Hypothesis</label>
        <div className="flex gap-2">
          <input
            type="text"
            value={customInput}
            onChange={(e) => setCustomInput(e.target.value)}
            placeholder="e.g. Requires 30 days notice for breach..."
            className="flex-1 px-4 py-2 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm"
          />
          <button
            type="submit"
            disabled={!customInput.trim()}
            className="px-4 py-2 bg-slate-900 text-white rounded-xl hover:bg-slate-800 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            <Send className="h-4 w-4" />
            <span className="hidden sm:inline">Check</span>
          </button>
        </div>
      </form>
    </div>
  );
}
