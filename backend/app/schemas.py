from pydantic import BaseModel, Field
from typing import List, Optional

class UploadResponse(BaseModel):
    doc_id: str
    message: str

class AnalyzeRequest(BaseModel):
    doc_id: str
    hypothesis: str

class ReportCitation(BaseModel):
    id: str
    text: str
    page: int
    bbox: Optional[List[float]] = None

class ReportResult(BaseModel):
    label: str = Field(..., description="Must be Entailment, Contradiction, or NotMentioned")
    reasoning: str
    cited_clauses: List[ReportCitation]
