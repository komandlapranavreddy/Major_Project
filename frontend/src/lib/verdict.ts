import { CheckCircle, XCircle, HelpCircle } from 'lucide-react';
import type { ReportResult } from '../types';

export const LABEL_CONFIG = {
  Entailment: {
    display: 'Entailment',
    text: 'text-emerald-600 dark:text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/20',
    dot: 'bg-emerald-500',
    icon: CheckCircle,
  },
  Contradiction: {
    display: 'Contradiction',
    text: 'text-red-600 dark:text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/20',
    dot: 'bg-red-500',
    icon: XCircle,
  },
  NotMentioned: {
    display: 'Not mentioned',
    text: 'text-muted-foreground',
    bg: 'bg-secondary',
    border: 'border-border',
    dot: 'bg-muted-foreground',
    icon: HelpCircle,
  },
} as const;

export type VerdictLabel = ReportResult['label'];

export function verdictConfig(label: string) {
  return LABEL_CONFIG[label as VerdictLabel] ?? LABEL_CONFIG.NotMentioned;
}
