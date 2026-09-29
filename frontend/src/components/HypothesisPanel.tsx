import { useState, type FormEvent } from 'react';
import { motion } from 'framer-motion';
import { Send, Sparkles, Loader2, ListChecks, PenLine } from 'lucide-react';
import { cn } from '../utils/cn';
import { easeOut, panelSurface } from '@/lib/design';
import { ShineBorder } from '@/components/landing/effects/shine-border';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from './ui/tabs';

interface HypothesisPanelProps {
  onCheck: (hypothesis: string) => void;
  /** True once a document has been uploaded and hypotheses can be checked. */
  disabled: boolean;
  /** True while a check request is in flight. */
  isChecking: boolean;
}

const PREDEFINED_RULES = [
  'Contains confidentiality clause',
  'Terminable for convenience',
  'Governing law is New York',
];

export function HypothesisPanel({ onCheck, disabled, isChecking }: HypothesisPanelProps) {
  const [customInput, setCustomInput] = useState('');
  const [pendingHypothesis, setPendingHypothesis] = useState<string | null>(null);

  const locked = disabled || isChecking;

  const handleRuleClick = (rule: string) => {
    setPendingHypothesis(rule);
    onCheck(rule);
  };

  const handleCustomSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = customInput.trim();
    if (trimmed) {
      setPendingHypothesis(trimmed);
      onCheck(trimmed);
    }
  };

  return (
    <Card className={cn('p-6 transition-opacity duration-300', panelSurface, disabled && !isChecking && 'opacity-60')}>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-xs font-bold text-primary">
            2
          </span>
          <h2 className="text-base font-semibold">Check Hypothesis</h2>
        </div>
        {isChecking && (
          <span className="flex items-center gap-1.5 text-xs font-medium text-primary">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Analyzing…
          </span>
        )}
      </div>

      {disabled && !isChecking && (
        <p className="mb-4 text-xs text-muted-foreground">Upload a contract above to get started.</p>
      )}

      <Tabs defaultValue="standard">
        <TabsList className="w-full">
          <TabsTrigger value="standard" className="flex-1 gap-1.5">
            <ListChecks className="h-3.5 w-3.5" />
            Standard Rules
          </TabsTrigger>
          <TabsTrigger value="custom" className="flex-1 gap-1.5">
            <PenLine className="h-3.5 w-3.5" />
            Custom
          </TabsTrigger>
        </TabsList>

        <TabsContent value="standard" className="space-y-2">
          {PREDEFINED_RULES.map((rule) => {
            const isPending = isChecking && pendingHypothesis === rule;
            const isLastChecked = !isChecking && pendingHypothesis === rule;
            return (
              <motion.button
                key={rule}
                type="button"
                onClick={() => handleRuleClick(rule)}
                disabled={locked}
                whileHover={locked ? undefined : { x: 2 }}
                whileTap={locked ? undefined : { scale: 0.98 }}
                transition={{ duration: 0.15, ease: easeOut }}
                className={cn(
                  'relative flex w-full items-center gap-3 rounded-xl border border-border bg-secondary/40 px-4 py-3 text-left text-sm font-medium transition-[border-color,background-color,box-shadow,opacity] duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed',
                  !locked && 'hover:border-primary/40 hover:bg-primary/5',
                  locked && !isPending && 'opacity-60',
                  isPending && 'border-transparent bg-primary/[0.08] shadow-[0_8px_24px_-12px_hsl(var(--primary)/0.7)]',
                  isLastChecked && 'border-primary/50 bg-primary/[0.06]'
                )}
              >
                {isPending && <ShineBorder className="animate-border-spin opacity-100" />}
                {isPending ? (
                  <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
                ) : (
                  <Sparkles
                    className={cn(
                      'h-4 w-4 shrink-0 transition-colors',
                      isLastChecked ? 'text-primary' : 'text-muted-foreground'
                    )}
                  />
                )}
                {rule}
              </motion.button>
            );
          })}
        </TabsContent>

        <TabsContent value="custom">
          <form onSubmit={handleCustomSubmit} className="flex gap-2">
            <input
              type="text"
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value)}
              disabled={locked}
              placeholder="e.g. Requires 30 days notice for breach..."
              className="flex-1 rounded-xl border border-input bg-background px-4 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background disabled:opacity-60"
            />
            <Button type="submit" disabled={locked || !customInput.trim()}>
              {isChecking && pendingHypothesis === customInput.trim() ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
              <span className="hidden sm:inline">Check</span>
            </Button>
          </form>
        </TabsContent>
      </Tabs>
    </Card>
  );
}
