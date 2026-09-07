from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class Block(BaseModel):
    block_id: str
    content_type: Literal["text", "table"]
    text: Optional[str] = None
    table_data: Optional[List[List[str]]] = None
    bounding_box: List[float]
    section: Optional[str] = None


class Page(BaseModel):
    page_number: int
    blocks: List[Block] = Field(default_factory=list)


class DocumentResponse(BaseModel):
    document_id: str
    pages: List[Page] = Field(default_factory=list)
    status: Literal["success", "failed"]
    
class ProcessRequest(BaseModel):
    document_id: str = Field(min_length=1)
    file_path: str = Field(min_length=1)
    source_split: Literal["train", "validation", "test"]