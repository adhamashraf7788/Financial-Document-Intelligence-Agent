from fastapi import FastAPI, HTTPException, status
import uvicorn
from shared.schemas import DocumentProcessorResponse
from services.retrieval.chunker import DocumentChunker

app = FastAPI(title="Retrieval Service - Chunking")

chunker = DocumentChunker()

# Testing
@app.post("/test-chunking")
async def test_chunking(parsed_doc: DocumentProcessorResponse):
    """
    Directly tests the chunking strategy by passing a DocumentProcessorResponse body.
    """
    chunks = chunker.process_parsed_document(parsed_doc)
    return {
        "document_id": parsed_doc.document_id,
        "total_chunks_created": len(chunks),
        "chunks": [chunk.dict() for chunk in chunks]
    }


# Launching Test server
if __name__ == '__main__':
    uvicorn.run("services.retrieval.main:app", host="0.0.0.0", port=8000, reload=True)