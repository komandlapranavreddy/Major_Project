export interface ReportCitation {
  id: string;
  text: string;
  page: number;
  bbox?: number[];
}

export interface ReportResult {
  label: 'Entailment' | 'Contradiction' | 'NotMentioned';
  reasoning: string;
  cited_clauses: ReportCitation[];
}
