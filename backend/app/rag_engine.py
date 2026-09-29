import chromadb
from chromadb.utils import embedding_functions
import json
import os
from app.llm.groq_client import groq_client

# Initialize ChromaDB in a local directory
CHROMA_DB_DIR = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_DIR)

# Use sentence-transformers embedding function
sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

# Get or create collection
collection = chroma_client.get_or_create_collection(
    name="legal_documents",
    embedding_function=sentence_transformer_ef
)

def store_document_chunks(doc_id: str, chunks: list):
    """
    Embeds and stores document chunks in ChromaDB.
    """
    ids = []
    documents = []
    metadatas = []
    
    for i, chunk in enumerate(chunks):
        chunk_id = f"{doc_id}_chunk_{i}"
        ids.append(chunk_id)
        documents.append(chunk["text"])
        metadatas.append({
            "doc_id": doc_id,
            "page": chunk["page"],
            # Store bbox as a string to bypass ChromaDB metadata type restrictions
            "bbox": json.dumps(chunk["bbox"])
        })
        
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )

def analyze_hypothesis(doc_id: str, hypothesis: str, top_k: int = 5):
    """
    Retrieves context for a hypothesis and runs Groq (or Ollama fallback) inference to get structured results.
    """
    # 1. Retrieve relevant chunks
    results = collection.query(
        query_texts=[hypothesis],
        n_results=top_k,
        where={"doc_id": doc_id}
    )
    
    # 2. Build context string
    context_chunks = []
    citations = []
    
    if results['documents'] and len(results['documents'][0]) > 0:
        docs = results['documents'][0]
        metas = results['metadatas'][0]
        ids = results['ids'][0]
        
        for i in range(len(docs)):
            text = docs[i]
            meta = metas[i]
            chunk_id = ids[i]
            
            context_chunks.append(f"--- Chunk ID: {chunk_id} ---\n{text}")
            
            citations.append({
                "id": chunk_id,
                "text": text,
                "page": meta["page"],
                "bbox": json.loads(meta["bbox"]) if "bbox" in meta else None
            })
            
    context_str = "\n\n".join(context_chunks)
    
    # 3. Call LLM (Groq with rotating keys, or fallback to Ollama)
    system_prompt = """
    You are an expert legal AI assistant. Your task is to evaluate a legal hypothesis against the provided contract context.
    
    You MUST output ONLY a valid JSON object with the following structure, and nothing else:
    {
      "label": "Entailment" | "Contradiction" | "NotMentioned",
      "reasoning": "A concise explanation of why this label was chosen based on the context.",
      "cited_chunk_ids": ["list", "of", "chunk", "ids", "used", "as", "evidence"]
    }
    
    Rules for labels:
    - Entailment: The context clearly supports the hypothesis.
    - Contradiction: The context clearly contradicts the hypothesis.
    - NotMentioned: The context does not contain enough information to support or contradict the hypothesis.
    """
    
    user_prompt = f"Context from Contract:\n{context_str}\n\nHypothesis: {hypothesis}"
    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt}
    ]
    
    try:
        if groq_client.has_keys:
            # High-speed Groq inference with key rotation
            response_text = groq_client.chat(
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.0
            )
        else:
            # Fallback to local Ollama
            import ollama
            response = ollama.chat(model='llama3.1:8b', messages=messages, format='json')
            response_text = response['message']['content']
            
        parsed_result = json.loads(response_text)
        
        # 4. Map chunk IDs back to full citation objects
        used_ids = parsed_result.get("cited_chunk_ids", [])
        final_citations = [c for c in citations if c["id"] in used_ids]
        
        # Fallback: if model returns empty cited_chunk_ids but finds entailment/contradiction, include top 1
        if not final_citations and parsed_result.get("label") != "NotMentioned" and citations:
            final_citations = [citations[0]]
            
        return {
            "label": parsed_result.get("label", "NotMentioned"),
            "reasoning": parsed_result.get("reasoning", "No valid reasoning provided."),
            "cited_clauses": final_citations
        }
        
    except Exception as e:
        print(f"Error during LLM inference: {e}")
        return {
            "label": "NotMentioned",
            "reasoning": f"Error during analysis: {str(e)}",
            "cited_clauses": []
        }

