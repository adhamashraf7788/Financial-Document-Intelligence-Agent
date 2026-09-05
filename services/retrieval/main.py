from typing import List
from fastapi import FastAPI, HTTPException, status
import uvicorn
import uuid
from shared.schemas import Block, Page, DocumentProcessorResponse, Chunk




app = FastAPI(title="Retrieval Service - Chunking")


# ----------------------------------------------------------------- Chunking Logic ----------------------------------------------------------------- 
class DocumentChunker:
    def __init__(self, target_chunk_size: int = 40, chunk_overlap: int = 10):
        self.target_chunk_size = target_chunk_size
        self.chunk_overlap = chunk_overlap

    def _chunk_table(self, block: Block, doc_id: str, page_num: int) -> List[Chunk]:
        chunks = []

        # if the block has a table it will store it 
        table = block.table_data or []
        # if table var has no table return chunks
        if not table:
            return chunks

        # extracting data from the table and restructuring it as Markdown table string
        header = table[0]
        headers_str = " | ".join([str(h) for h in header])
        divider = " | ".join(["---"] * len(header))
        rows_md = [" | ".join([str(cell) for cell in row]) for row in table[1:]]
        full_table_md = f"Section: {block.section}\n| {headers_str} |\n| {divider} |\n"

        # Keep short tables -> single chunks;
        # larger ones -> splitted with preserved headers
        if len(rows_md) <= 15:
            full_table_md += "\n".join([f"| {r} |" for r in rows_md])
            chunks.append(
                Chunk(
                    chunk_id=f"{doc_id}_p{page_num}_tbl_{uuid.uuid4().hex[:6]}",
                    document_id=doc_id,
                    page=page_num,
                    section=block.section or "General",
                    content_type="table",
                    text=full_table_md,
                    metadata={"is_complete_table": True, "num_rows": len(rows_md)}
                )
            )
        else:
            batch_size = 10
            for i in range(0, len(rows_md), batch_size):
                sub_rows = rows_md[i : i + batch_size]
                chunk_text = (
                    f"Section: {block.section} (Table rows {i+1} to {i+len(sub_rows)})\n"
                    f"| {headers_str} |\n| {divider} |\n"
                    + "\n".join([f"| {r} |" for r in sub_rows])
                )
                chunks.append(
                    Chunk(
                        chunk_id=f"{doc_id}_p{page_num}_tbl_{i}_{uuid.uuid4().hex[:6]}",
                        document_id=doc_id,
                        page=page_num,
                        section=block.section or "General",
                        content_type="table",
                        text=chunk_text,
                        metadata={"is_complete_table": False, "row_start": i, "row_end": i + len(sub_rows)}
                    )
                )
        return chunks




    def _chunk_text_section(self, section_text: str, doc_id: str, page_num: int, section_name: str) -> List[Chunk]:
        chunks = []
        # splits the piece of text 
        words = section_text.split()
        # if words var has no text return chunks
        if not words:
            return chunks

        # Parent Chunk
        parent_id = f"{doc_id}_p{page_num}_parent_{uuid.uuid4().hex[:6]}" # creates id for the parent
        parent_chunk = Chunk(
            chunk_id=parent_id,
            document_id=doc_id,
            page=page_num,
            section=section_name,
            content_type="text",
            text=f"Section: {section_name}\n{section_text}",
            metadata={"is_parent": True}
        )
        chunks.append(parent_chunk)

        # Child Chunks
        start = 0
        while start < len(words):
            # determining the index of the last word of the chunk
            end = start + self.target_chunk_size
            # storing the chunk words in a list
            child_words = words[start:end]
            # creating the child chunk text
            child_text = " ".join(child_words)

            # creating chunk
            chunks.append(
                Chunk(
                    chunk_id=f"{doc_id}_p{page_num}_child_{uuid.uuid4().hex[:6]}",
                    document_id=doc_id,
                    page=page_num,
                    section=section_name,
                    content_type="text",
                    text=f"Section: {section_name}\n{child_text}",
                    metadata={"is_parent": False, "parent_id": parent_id}
                )
            )

            # End of the section_text
            if end >= len(words):
                break

            # updating the start index with respect to the overlap
            start += (self.target_chunk_size - self.chunk_overlap)

        return chunks




    def process_parsed_document(self, doc_data: DocumentProcessorResponse) -> List[Chunk]:
        all_chunks = []

        for page in doc_data.pages:
            current_section = None
            accumulated_text = []

            for block in page.blocks:
                # Table Blocks
                if block.content_type == "table":
                    # Handeling the overlapping text
                    if accumulated_text:
                        text_content = " ".join(accumulated_text)
                        all_chunks.extend(
                            self._chunk_text_section(text_content, doc_data.document_id, page.page_number, current_section or "General")
                        )
                        accumulated_text = []

                    # Handeling the Table
                    all_chunks.extend(self._chunk_table(block, doc_data.document_id, page.page_number))

                # Text Blocks
                elif block.content_type == "text":
                    # Handeling the transion from one section to another
                    if block.section != current_section and accumulated_text:
                        text_content = " ".join(accumulated_text)
                        all_chunks.extend(
                            self._chunk_text_section(text_content, doc_data.document_id, page.page_number, current_section or "General")
                        )
                        accumulated_text = []

                    current_section = block.section
                    if block.text:
                        accumulated_text.append(block.text)

            # Handeling the overlapping text
            if accumulated_text:
                text_content = " ".join(accumulated_text)
                all_chunks.extend(
                    self._chunk_text_section(text_content, doc_data.document_id, page.page_number, current_section or "General")
                )

        return all_chunks
# --------------------------------------------------------------------------------------------------------------------------------------------

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