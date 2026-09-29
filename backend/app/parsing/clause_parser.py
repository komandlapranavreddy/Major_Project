"""
parsing/clause_parser.py
────────────────────────
Splits a contract's flat text into clause-level units using
paragraph/section/numbering boundaries only — never on arbitrary
character limits.

Public API (matches architecture123.md):
  detect_section_heading(line: str) -> str | None
  segment_clauses(pages: list[PageBlock]) -> list[Clause]

Data classes:
  PageBlock(text, page_num, bbox)
  Clause(id, text, page_num, section_heading)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

try:
    # This file previously had zero `backend.app.*` dependencies and was a
    # standalone leaf module. Falling back to a plain logger (rather than
    # letting this import fail) preserves that if it's ever imported from a
    # context without the repo root on sys.path.
    from backend.app.logging_config import get_logger, log_exception, log_step
except ImportError:
    import logging as _logging

    def get_logger(name):
        return _logging.getLogger(name)

    def log_step(logger, step, **context):
        logger.info("STEP %s | %s", step, context)

    def log_exception(logger, msg, **context):
        logger.error("FAILED %s | %s", msg, context, exc_info=True)

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PageBlock:
    """Output of pdf_extractor.extract_pages(); one block per PDF page."""
    text: str
    page_num: int
    bbox: Optional[tuple] = None


@dataclass
class Clause:
    """A single retrievable clause unit."""
    id: str                          # e.g. "doc42_clause_007"
    text: str
    page_num: int
    section_heading: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Heading detection patterns
# ─────────────────────────────────────────────────────────────────────────────

# Numbered sections: "1.", "2.1", "2.3.4", "10." — optionally followed by text
_RE_NUMBERED = re.compile(
    r"^\s*(\d{1,3}(?:\.\d{1,3})*\.?)\s*(.*)$"
)

# ALL-CAPS headings: at least 3 capital letters (allows spaces/hyphens)
# Must be the whole line after stripping.
_RE_ALLCAPS = re.compile(
    r"^[A-Z][A-Z\s\-&,/]{2,}[A-Z]$"
)

# Recital openers
_RE_RECITAL = re.compile(
    r"^(WHEREAS|NOW,?\s+THEREFORE|IN\s+WITNESS\s+WHEREOF|RECITALS?|WITNESSETH)",
    re.IGNORECASE,
)

# Paragraph break: one or more blank lines
_RE_PARA_BREAK = re.compile(r"\n{2,}")

# A line that starts a new numbered section (used as split boundary)
_RE_SECTION_START = re.compile(
    r"(?m)^(\d{1,3}(?:\.\d{1,3})*\.?\s+|\s*(?:WHEREAS|NOW,?\s+THEREFORE|IN\s+WITNESS|RECITALS?)\b)"
)

# Minimum / maximum thresholds (used for flagging only — not for splitting)
MIN_CLAUSE_CHARS = 20
MAX_CLAUSE_CHARS = 2000


def detect_section_heading(line: str) -> Optional[str]:
    """
    Return the detected heading label if `line` looks like a section header,
    else return None.

    Priority:
      1. Recital opener (WHEREAS, NOW THEREFORE, ...)
      2. Numbered section (1., 2.1, 2.3.4)
      3. ALL-CAPS heading (RECITALS, CONFIDENTIALITY, ...)
    """
    stripped = line.strip()
    if not stripped:
        return None

    if _RE_RECITAL.match(stripped):
        return stripped.split()[0].upper()

    m = _RE_NUMBERED.match(stripped)
    if m:
        # Only accept as a heading if the number occupies a standalone-ish role
        # (i.e., the rest of the line is either empty or continuation text)
        return m.group(1)

    if _RE_ALLCAPS.match(stripped):
        return stripped

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Core segmentation
# ─────────────────────────────────────────────────────────────────────────────

def _split_into_raw_chunks(text: str) -> list[str]:
    """
    Split the full contract text into raw chunks using:
      1. Paragraph breaks (two or more newlines).
      2. Within each paragraph, if a line starts a new numbered section
         AND is not mid-sentence, split there too.

    Returns a list of non-empty stripped chunks.
    """
    # Step 1: split on blank lines
    paragraphs = _RE_PARA_BREAK.split(text)

    chunks: list[str] = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Step 2: Within a paragraph, look for embedded section headers.
        # A new numbered section on its own line inside a paragraph means
        # the paragraph is actually two clauses glued together.
        lines = para.split("\n")
        current_lines: list[str] = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Detect if this line is a section header AND we already have
            # content above it in the current chunk (i.e., this is a boundary).
            if current_lines and stripped and _is_section_start_line(stripped):
                # Flush what we have, start fresh
                joined = "\n".join(current_lines).strip()
                if joined:
                    chunks.append(joined)
                current_lines = [line]
            else:
                current_lines.append(line)

        tail = "\n".join(current_lines).strip()
        if tail:
            chunks.append(tail)

    return chunks


def _is_section_start_line(line: str) -> bool:
    """
    Return True if `line` looks like it starts a new numbered section or a
    major structural header (WHEREAS, RECITALS, etc.).
    We're stricter here than detect_section_heading to avoid false splits.
    """
    stripped = line.strip()
    # Numbered: must start with digit(s) and a dot
    if re.match(r"^\d{1,3}\.\s", stripped):
        return True
    # Recital / structural keywords at line start
    if _RE_RECITAL.match(stripped):
        return True
    return False


def _merge_short_fragments(chunks: list[str]) -> list[str]:
    """
    Merge chunks shorter than MIN_CLAUSE_CHARS into their neighbor.
    Short fragments are almost always orphaned section-number labels
    (e.g., "3." alone on a line), standalone punctuation, or signature fields.
    Merge forward (into the next chunk) first; if at the end, merge backward.
    """
    result: list[str] = []
    i = 0
    while i < len(chunks):
        chunk = chunks[i]
        if len(chunk) < MIN_CLAUSE_CHARS and i + 1 < len(chunks):
            # Prepend to the next chunk
            chunks[i + 1] = chunk + "\n" + chunks[i + 1]
            i += 1
            continue
        if len(chunk) < MIN_CLAUSE_CHARS and result:
            # Append to the previous chunk
            result[-1] = result[-1] + "\n" + chunk
            i += 1
            continue
        result.append(chunk)
        i += 1
    return result


def segment_clauses(pages: list[PageBlock]) -> list[Clause]:
    """
    Split a list of PageBlocks into clause-level Clause units.

    Splitting is done on structural boundaries only:
      - Paragraph breaks (blank lines)
      - Lines that start a new numbered section (1., 2.1, ...)
      - Lines that open a recital block (WHEREAS, NOW THEREFORE, ...)

    Short orphan fragments (<20 chars) are merged into their neighbor.
    No splitting occurs at arbitrary character limits.

    Args:
        pages: List of PageBlock objects (from pdf_extractor or synthetic).

    Returns:
        Ordered list of Clause objects.
    """
    if not pages:
        logger.warning("segment_clauses() called with 0 pages - returning [].")
        return []

    total_chars = sum(len(p.text) for p in pages)
    log_step(logger, "parse.start", n_pages=len(pages), total_chars=total_chars)

    # Build doc_id prefix from first page (used for clause IDs).
    # If page_num is meaningful we include it; here we concatenate all pages.
    all_text_parts: list[tuple[str, int]] = []
    for page in pages:
        all_text_parts.append((page.text, page.page_num))

    full_text = "\n\n".join(t for t, _ in all_text_parts)

    # Track which page a character offset falls on (simple approach:
    # assign each chunk to the page whose text contains most of it).
    page_starts: list[tuple[int, int]] = []  # (char_offset, page_num)
    offset = 0
    for text, pnum in all_text_parts:
        page_starts.append((offset, pnum))
        offset += len(text) + 2  # +2 for the \n\n separator

    def _page_for_offset(char_offset: int) -> int:
        pnum = 0
        for start, p in page_starts:
            if char_offset >= start:
                pnum = p
        return pnum

    try:
        raw_chunks = _split_into_raw_chunks(full_text)
        merged_chunks = _merge_short_fragments(raw_chunks)
    except Exception:
        log_exception(logger, "clause segmentation crashed", n_pages=len(pages),
                      total_chars=total_chars)
        raise

    clauses: list[Clause] = []
    char_cursor = 0

    for idx, chunk_text in enumerate(merged_chunks):
        # Approximate character position of this chunk in the full text
        pos = full_text.find(chunk_text[:40], char_cursor)
        if pos == -1:
            pos = char_cursor
        char_cursor = pos + len(chunk_text)

        # Detect the section heading for this clause
        first_line = chunk_text.split("\n")[0]
        heading = detect_section_heading(first_line) or ""

        clause = Clause(
            id=f"clause_{idx:04d}",
            text=chunk_text,
            page_num=_page_for_offset(pos),
            section_heading=heading,
        )
        clauses.append(clause)

    if not clauses:
        # Real failure mode: a scanned PDF with no text layer produces empty
        # pages, which silently yields zero clauses downstream (empty index,
        # "NotMentioned" for every hypothesis) with no error anywhere — this
        # is the one place that can be diagnosed and logged.
        logger.warning(
            "segment_clauses() produced 0 clauses from %d page(s), %d total "
            "chars - likely a scanned/image-only PDF with no extractable "
            "text layer.", len(pages), total_chars,
        )
    else:
        log_step(logger, "parse.done", n_clauses=len(clauses),
                 raw_chunks=len(raw_chunks), merged_chunks=len(merged_chunks))

    return clauses
