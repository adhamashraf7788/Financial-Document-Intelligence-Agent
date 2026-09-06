from core import *
from sections import *

def process_document(
    file_path,
    document_id
):

    try:
        process_start = time.perf_counter()

        # ----------------------------------------------------
        # CHECK FILE
        # ----------------------------------------------------

        if not Path(file_path).exists():

            return DocumentResponse(
                document_id=document_id,
                pages=[],
                status="failed"
            )

        # ----------------------------------------------------
        # OPEN PDF
        # ----------------------------------------------------

        document = pymupdf.open(
            file_path
        )

        # ----------------------------------------------------
        # OUTPUT DIRECTORY
        # ----------------------------------------------------

        output_dir = Path("tests/pages")

        if save_page_images:
            output_dir.mkdir(
                parents=True,
                exist_ok=True
            )

        pages = []

        # ====================================================
        # PROCESS PAGES
        # ====================================================

        for page_number, page in enumerate(
            document,
            start=1
        ):

            if page_number < first:
                continue

            if page_number > last:
                break

            print(
                f"\nPROCESSING PAGE {page_number}"
            )
            page_start = time.perf_counter()

            # ------------------------------------------------
            # RENDER PAGE
            # ------------------------------------------------

            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(
                    render_scale,
                    render_scale
                )
            )

            image = pixmap_to_array(pixmap)

            if save_page_images:
                image_path = output_dir / f"page_{page_number}.png"
                pixmap.save(str(image_path))

            # =================================================
            # PP-STRUCTUREV3
            # =================================================

            print(
                "Running PP-StructureV3..."
            )

            structure_result = (
                structure_pipeline
                .predict(
                    image
                )[0]
            )

            layout = (
                structure_result[
                    "layout_det_res"
                ]
            )

            parsing_res_list = structure_result.get(
                "parsing_res_list",
                []
            )

            tables = (
                structure_result[
                    "table_res_list"
                ]
            )

            # =================================================
            # REGULAR PADDLEOCR
            # =================================================

            print(
                "Running PaddleOCR..."
            )

            ocr_result = (
                ocr_pipeline
                .predict(
                    image
                )[0]
            )

            texts = ocr_result[
                "rec_texts"
            ]

            boxes = ocr_result[
                "rec_boxes"
            ]

            print(
                "OCR TEXT COUNT:",
                len(texts)
            )

            # =================================================
            # CLEAN TABLES
            # =================================================

            tables, table_boxes = clean_tables(
                tables
            )

            print(
                "TABLES:",
                len(tables)
            )

            # =================================================
            # TEXT REGIONS
            # =================================================

            text_regions = []

            for item in layout["boxes"]:

                if item["label"] != "text":
                    continue

                region = [
                    float(v)
                    for v in item["coordinate"]
                ]

                text_regions.append(
                    region
                )

            text_regions.sort(
                key=lambda b: (
                    b[1],
                    b[0]
                )
            )

            print(
                "TEXT LAYOUT REGIONS:",
                len(text_regions)
            )

            # =================================================
            # SECTIONS
            # =================================================

            sections = detect_sections(
                texts,
                boxes,
                layout,
                table_boxes,
                parsing_res_list
            )

            # =================================================
            # ASSIGN OCR TO TEXT REGIONS
            # =================================================

            region_texts = [
                []
                for _ in text_regions
            ]

            # -------------------------------------------------
            # Optimization:
            #
            # We calculate OCR centers only once.
            # -------------------------------------------------

            ocr_items = []

            for text, box in zip(
                texts,
                boxes
            ):

                if (
                    not text
                    or not text.strip()
                ):
                    continue

                box = np.asarray(
                    box,
                    dtype=float
                ).tolist()

                center = box_center(
                    box
                )

                # Ignore table OCR
                in_table = False

                for table_box in table_boxes:

                    if inside(
                        center,
                        table_box
                    ):

                        in_table = True
                        break

                if in_table:
                    continue

                ocr_items.append(
                    (
                        clean_text(text),
                        box,
                        center
                    )
                )

            # -------------------------------------------------
            # Match OCR lines to layout regions
            # -------------------------------------------------

            for text, box, center in ocr_items:

                for i, region in enumerate(
                    text_regions
                ):

                    if inside(
                        center,
                        region
                    ):

                        region_texts[i].append(
                            (
                                text,
                                box
                            )
                        )

                        break

            # =================================================
            # CREATE BLOCKS
            # =================================================

            blocks = []

            # =================================================
            # TEXT BLOCKS
            # =================================================

            for i, items in enumerate(
                region_texts
            ):

                if not items:
                    continue

                # Sort text lines
                items.sort(
                    key=lambda x: (
                        x[1][1],
                        x[1][0]
                    )
                )

                # Join OCR lines
                text = " ".join(
                    text.strip()
                    for text, _ in items
                    if text.strip()
                )

                if not text:
                    continue

                bounding_box = [
                    float(v)
                    for v in text_regions[i]
                ]

                section = get_section(
                    bounding_box,
                    sections
                )

                blocks.append(
                    Block(
                        block_id=(
                            f"{document_id}_p"
                            f"{page_number}_b"
                            f"{len(blocks)+1:02d}"
                        ),
                        content_type="text",
                        text=text,
                        table_data=None,
                        bounding_box=bounding_box,
                        section=section
                    )
                )

            # =================================================
            # TABLE BLOCKS
            # =================================================

            for i, (
                table,
                table_box
            ) in enumerate(
                zip(
                    tables,
                    table_boxes
                ),
                start=1
            ):

                table_data = (
                    extract_table_data(
                        table,
                        texts,
                        boxes
                    )
                )

                section = get_section(
                    table_box,
                    sections
                )

                blocks.append(
                    Block(
                        block_id=(
                            f"{document_id}_p"
                            f"{page_number}_t"
                            f"{i:02d}"
                        ),
                        content_type="table",
                        text=None,
                        table_data=table_data,
                        bounding_box=table_box,
                        section=section
                    )
                )

            # =================================================
            # SORT BLOCKS
            # =================================================

            blocks.sort(
                key=lambda b: (
                    b.bounding_box[1],
                    b.bounding_box[0]
                )
            )

            # =================================================
            # ADD PAGE
            # =================================================

            pages.append(
                Page(
                    page_number=page_number,
                    blocks=blocks
                )
            )

            print(
                f"PAGE {page_number} TIME: "
                f"{time.perf_counter() - page_start:.2f}s"
            )

        # ====================================================
        # CLOSE PDF
        # ====================================================

        document.close()

        print(
            f"TOTAL PROCESSING TIME: "
            f"{time.perf_counter() - process_start:.2f}s"
        )

        # ====================================================
        # RESPONSE
        # ====================================================

        return DocumentResponse(
            document_id=document_id,
            pages=pages,
            status="success"
        )

    except Exception as e:

        print(
            "ERROR:",
            repr(e)
        )

        raise


