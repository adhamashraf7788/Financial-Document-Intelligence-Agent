from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class Block(BaseModel):
    block_id: str
    content_type: str  # "text" or "table"
    text: Optional[str] = None
    table_data: Optional[List[List[Any]]] = None
    bounding_box: Optional[List[float]] = None
    section: Optional[str] = "General"

class Page(BaseModel):
    page_number: int
    blocks: List[Block]

class DocumentProcessorResponse(BaseModel):
    document_id: str
    pages: List[Page]
    status: str

class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    page: int
    section: str
    content_type: str  # "text" or "table"
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)