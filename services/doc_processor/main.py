import pymupdf
from pathlib import Path
from paddleocr import PPStructureV3
from models import Block, Page, DocumentResponse, ProcessRequest
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}
  

pipeline = PPStructureV3()

def process_document(file_path, document_id):
    try:
        if not Path(file_path).exists():
            return DocumentResponse(
                document_id=document_id,
                pages=[],
                status="failed"
            )
        document = pymupdf.open(file_path)
        output_dir = Path("tests/pages")
        output_dir.mkdir(parents=True, exist_ok=True)
        pages = []
        for page_number, page in enumerate(document, start=1):
            print(page_number)
            if page_number < 40:
              continue

            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))

            print(pixmap.width, pixmap.height)
            pixmap.save(str(output_dir / f"page_{page_number}.png"))
            result = pipeline.predict(
                str(output_dir / f"page_{page_number}.png")
            )

            result = result[0]

            table_results = result["table_res_list"]
            if table_results:
              print("TABLE FOUND")
              print(table_results[0])

            texts = result["overall_ocr_res"]["rec_texts"]
            boxes = result["overall_ocr_res"]["rec_boxes"]

            blocks = []


            # --------------------------------------------------
            # 1. Find the bounding boxes of detected tables
            # --------------------------------------------------

            table_boxes = []

            for table_index, table in enumerate(table_results, start=1):

                cell_boxes = table["cell_box_list"]

                x0 = float(cell_boxes[:, 0].min())
                y0 = float(cell_boxes[:, 1].min())
                x1 = float(cell_boxes[:, 2].max())
                y1 = float(cell_boxes[:, 3].max())

                table_box = [x0, y0, x1, y1]

                table_boxes.append(table_box)

                print(f"TABLE {table_index} BOX:", table_box)


            # --------------------------------------------------
            # 2. Add normal text
            #    Ignore OCR text that is inside a table
            # --------------------------------------------------

            for index, (text, box) in enumerate(zip(texts, boxes), start=1):

                box = box.tolist()

                bx0, by0, bx1, by1 = box

                inside_table = False

                for table_box in table_boxes:

                    tx0, ty0, tx1, ty1 = table_box

                    # Check whether the OCR box is inside the table
                    center_x = (bx0 + bx1) / 2
                    center_y = (by0 + by1) / 2

                    if (
                        tx0 <= center_x <= tx1
                        and
                        ty0 <= center_y <= ty1
                    ):
                        inside_table = True
                        break

                # Don't add table OCR as normal text
                if inside_table:
                    continue

                block = Block(
                    block_id=f"{document_id}_p{page_number}_b{index:02d}",
                    content_type="text",
                    text=text,
                    bounding_box=box,
                    section=None
                )

                blocks.append(block)


            # --------------------------------------------------
            # 3. Add tables as table blocks
            # --------------------------------------------------

            for table_index, table in enumerate(table_results, start=1):

                cell_boxes = table["cell_box_list"]

                x0 = float(cell_boxes[:, 0].min())
                y0 = float(cell_boxes[:, 1].min())
                x1 = float(cell_boxes[:, 2].max())
                y1 = float(cell_boxes[:, 3].max())

                table_block = Block(
                    block_id=f"{document_id}_p{page_number}_t{table_index:02d}",
                    content_type="table",
                    text=table["pred_html"],
                    table_data=None,
                    bounding_box=[x0, y0, x1, y1],
                    section=None
                )

                blocks.append(table_block)


            page = Page(
                page_number=page_number,
                blocks=blocks
            )

            pages.append(page)

            if page_number >= 40:
                break
            
        document.close()   
        response = DocumentResponse(
          document_id=document_id,
          pages=pages,
          status="success"
        )
        return response
      
    except Exception as e:
        return DocumentResponse(
            document_id=document_id,
            pages=[],
            status="failed"
        )

@app.post("/process", response_model=DocumentResponse)
def process(request: ProcessRequest):
    return process_document(
        request.file_path,
        request.document_id
    )
        

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)