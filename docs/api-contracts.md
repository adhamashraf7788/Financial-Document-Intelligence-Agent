## Document Processing Service

### Endpoint

`POST /process`

The Document Processing service receives the path of a financial-report PDF and returns structured pages containing text and table blocks.

### Request

```json
{
  "document_id": "doc_017",
  "file_path": "/data/raw_pdfs/doc_017.pdf",
  "source_split": "train"
}
```

#### Request fields

| Field          | Type   | Required | Description                                                        |
| -------------- | ------ | -------- | ------------------------------------------------------------------ |
| `document_id`  | string | Yes      | Unique identifier of the document                                  |
| `file_path`    | string | Yes      | Path to the PDF file accessible by the Document Processing service |
| `source_split` | string | Yes      | Dataset split. Allowed values: `train`, `validation`, `test`       |

### Response

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
          "table_data": null,
          "bounding_box": [100, 200, 500, 240],
          "section": "Income Statement"
        },
        {
          "block_id": "doc_017_p1_t01",
          "content_type": "table",
          "text": null,
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

### Response fields

#### `DocumentResponse`

| Field         | Type   | Description                              |
| ------------- | ------ | ---------------------------------------- |
| `document_id` | string | ID of the processed document             |
| `pages`       | array  | List of processed PDF pages              |
| `status`      | string | Processing result: `success` or `failed` |

#### `Page`

| Field         | Type    | Description                                |
| ------------- | ------- | ------------------------------------------ |
| `page_number` | integer | PDF page number                            |
| `blocks`      | array   | Text and table blocks detected on the page |

#### `Block`

| Field          | Type        | Description                                         |
| -------------- | ----------- | --------------------------------------------------- |
| `block_id`     | string      | Unique identifier for the block                     |
| `content_type` | string      | Either `text` or `table`                            |
| `text`         | string/null | Extracted text for a text block                     |
| `table_data`   | array/null  | Extracted table data for a table block              |
| `bounding_box` | array       | `[x0, y0, x1, y1]` coordinates of the block         |
| `section`      | string/null | Detected document section associated with the block |

### Failed Response

When the PDF cannot be found or processing fails, the service returns a response with:

```json
{
  "document_id": "doc_017",
  "pages": [],
  "status": "failed"
}
```

### Processing Flow

```text
POST /process
      ↓
Validate PDF path
      ↓
Open PDF with PyMuPDF
      ↓
Render page
      ↓
PP-StructureV3
      ↓
PaddleOCR
      ↓
Table reconstruction / cleaning
      ↓
Section detection
      ↓
Create text/table blocks
      ↓
DocumentResponse
```

The service creates text blocks from OCR matched to layout regions and table blocks from the cleaned table results, attaching the corresponding bounding box and section.
