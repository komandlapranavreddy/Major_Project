import fitz  # PyMuPDF
import re

def process_pdf(file_path: str):
    """
    Parses a PDF file and yields text chunks with metadata.
    """
    doc = fitz.open(file_path)
    chunks = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # Get text blocks (x0, y0, x1, y1, text, block_no, block_type)
        blocks = page.get_text("blocks")
        
        for b in blocks:
            text = b[4].strip()
            
            # Simple chunking: ignore very short blocks (e.g. page numbers)
            if len(text) < 20:
                continue
                
            # Clean up newlines within a block
            text = re.sub(r'\s+', ' ', text)
            
            chunk = {
                "text": text,
                "page": page_num + 1,
                # bbox is stored as [x0, y0, x1, y1]
                "bbox": [b[0], b[1], b[2], b[3]]
            }
            chunks.append(chunk)
            
    return chunks
