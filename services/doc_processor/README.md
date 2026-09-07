# LEDGER – Document Processing Service

This directory contains the **Document Processing service** for the LEDGER Financial Document Intelligence Agent.

The service is responsible for taking a financial-report PDF, processing its pages with PDF rendering, OCR, document layout analysis, table extraction, and section detection, and returning structured document data for the Retrieval service.

## Folder Structure

```text
doc_processor/
├── main.py
├── document_processor.py
├── core.py
├── sections.py
├── models.py
├── requirements.txt
├── Dockerfile
└── tests/
    ├── test.pdf
    └── financial_report.pdf
```

---

## File Descriptions

### `main.py`

This is the **FastAPI entry point** for the Document Processing service.

It is responsible for:

- Creating the FastAPI application.
- Loading the OCR/layout models when the application starts.
- Reading environment variables such as:
  - `FIRST_PAGE`
  - `LAST_PAGE`
  - `RENDER_SCALE`
  - `SAVE_PAGE_IMAGES`
  - `DEBUG_GEOMETRY`
- Providing the health-check endpoint:
  - `GET /health`
- Providing the document-processing endpoint:
  - `POST /process`
- Starting the Uvicorn server on port `8000`.

The main processing endpoint receives a `ProcessRequest` and calls `process_document()`.

---

### `document_processor.py`

This file contains the **main document-processing pipeline**.

The processing flow is:

```text
PDF file
   ↓
PyMuPDF
   ↓
Render page as image
   ↓
PP-StructureV3
   ↓
Layout + table detection
   ↓
PaddleOCR
   ↓
OCR text + bounding boxes
   ↓
Table cleaning/reconstruction
   ↓
Section detection
   ↓
Text block creation
   ↓
Table block creation
   ↓
Page objects
   ↓
DocumentResponse
```

Main responsibility:

- Validate that the PDF exists.
- Open the PDF with PyMuPDF.
- Process the selected page range.
- Render each page.
- Run PP-StructureV3.
- Run regular PaddleOCR.
- Separate normal page text from table text.
- Detect sections.
- Create text and table blocks.
- Attach page numbers, bounding boxes, and sections.
- Sort blocks in document order.
- Return the final `DocumentResponse`.

This file is the main coordinator of the other modules.

---

### `core.py`

This file contains the **core table-processing, OCR-cleaning, geometry, and financial-data reconstruction logic**.

It includes functionality for:

#### Geometry

- Calculating bounding-box centers.
- Checking whether points are inside regions.
- Calculating bounding-box area.
- Calculating overlap between boxes.
- Converting PyMuPDF page images into NumPy arrays.

#### Text cleaning

- Normalizing whitespace.
- Cleaning OCR artifacts.
- Removing unnecessary `text:` prefixes.
- Cleaning currency, percentages, punctuation, and common OCR mistakes.

#### Financial table processing

- Detecting financial values.
- Splitting multiple financial values that were returned inside one OCR cell.
- Grouping physical cells into logical rows.
- Matching OCR output to physical table cells.
- Inferring logical numeric columns from their x-coordinates.
- Repairing misplaced values.
- Repairing merged label/value cells.
- Reconstructing wrapped table labels.
- Merging continuation rows.
- Normalizing the final number of columns.
- Normalizing currency values.

#### Table management

- Calculating overall table bounding boxes.
- Removing duplicate table detections.
- Sorting tables from top to bottom.
- Extracting final structured table data.

This file is where most of the custom logic used to make financial tables reliable is implemented.

---

### `sections.py`

This file contains the **section-detection and section-assignment logic**.

It is responsible for identifying headings such as:

```text
NOTE 13 – INCOME TAX
Income Statement
Selected Financial Data
Overview
```

Main functionality includes:

- Detecting numbered sections.
- Normalizing section titles.
- Filtering out text that is unlikely to be a section heading.
- Reading title text from PP-StructureV3 parsing results.
- Matching OCR text to detected title regions when necessary.
- Removing duplicate section detections.
- Preferring numbered headings when available.
- Sorting sections by their position on the page.
- Assigning the most recent section above a text/table block.

The detected section is stored in the `section` field of each output block.

---

### `models.py`

This file defines the **Pydantic data models used as the API contract** between the Document Processing service and the rest of the system.

The main models are:

#### `Block`

Represents one piece of extracted content.

```text
block_id
content_type
text
table_data
bounding_box
section
```

`content_type` can be:

```text
text
table
```

#### `Page`

Represents one processed PDF page.

```text
page_number
blocks
```

#### `DocumentResponse`

Represents the complete result of processing a document.

```text
document_id
pages
status
```

`status` can be:

```text
success
failed
```

#### `ProcessRequest`

Represents the request sent to the service.

```text
document_id
file_path
source_split
```

This file keeps the output format consistent between services.

---

### `requirements.txt`

Contains the Python dependencies required to run the service.

The important packages are:

- `fastapi` – REST API framework.
- `uvicorn` – ASGI server.
- `pymupdf` – PDF loading and page rendering.
- `numpy` – numerical and bounding-box processing.
- `paddlepaddle` – PaddlePaddle runtime.
- `paddleocr` – OCR and PP-StructureV3.

The PaddlePaddle/PaddleOCR versions should remain pinned to the versions that were tested successfully with this project.

---

### `Dockerfile`

This file defines how the Document Processing service is packaged into a Docker container.

It is responsible for:

- Selecting the Python base image.
- Installing required system libraries.
- Installing Python dependencies.
- Copying the service source code into the image.
- Exposing port `8000`.
- Starting FastAPI with Uvicorn.

The container allows the service to run consistently across different machines and environments.

---

### `tests/`

This directory contains PDFs used while developing and testing the document processor.

The test files include financial reports and other sample PDFs used to evaluate:

- OCR quality.
- Table extraction.
- Financial-value alignment.
- Section detection.
- Multi-column tables.
- Wrapped table labels.
- Different financial-report layouts.

PDF files are used only for testing and are not required to be committed to the repository if they are excluded by `.gitignore`.

---

## API

### Health Check

```http
GET /health
```

Response:

```json
{
  "status": "ok"
}
```

### Process Document

```http
POST /process
Content-Type: application/json
```

Example request:

```json
{
  "document_id": "doc_017",
  "file_path": "/data/raw_pdfs/doc_017.pdf",
  "source_split": "train"
}
```

The service returns a structured `DocumentResponse`.

Example:

```json
{
  "document_id": "doc_017",
  "pages": [
    {
      "page_number": 1,
      "blocks": [
        {
          "block_id": "doc_017_p1_b01",
          "content_type": "text",
          "text": "Total operating income for fiscal year 2020 was...",
          "bounding_box": [100, 200, 500, 240],
          "section": "Income Statement"
        },
        {
          "block_id": "doc_017_p1_t01",
          "content_type": "table",
          "table_data": [
            ["Item", "2019", "2020"],
            ["Revenue", "1,200", "1,450"]
          ],
          "bounding_box": [100, 250, 700, 500],
          "section": "Income Statement"
        }
      ]
    }
  ],
  "status": "success"
}
```

---

## Environment Variables

The service supports the following configuration values:

| Variable | Default | Purpose |
|---|---:|---|
| `FIRST_PAGE` | `1` | First PDF page to process |
| `LAST_PAGE` | `1000` | Last PDF page to process |
| `RENDER_SCALE` | `2.0` | PyMuPDF rendering scale |
| `SAVE_PAGE_IMAGES` | `0` | Save rendered page images when set to `1` |
| `DEBUG_GEOMETRY` | `0` | Print table/OCR geometry diagnostics when set to `1` |

---

## Responsibilities and Scope

The Document Processing service ends after producing structured document content.

It **does not perform**:

- Chunking
- Vector database storage
- Retrieval
- Reranking
- Question answering
- LLM reasoning
- Answer validation

Those responsibilities belong to the other LEDGER services.

The output of this service is the structured input used by the Retrieval service.
