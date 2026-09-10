import pymupdf
import numpy as np
import re
import os
import time
from pathlib import Path
from fastapi import FastAPI
from paddleocr import PPStructureV3, PaddleOCR

from models import Block, Page, DocumentResponse, ProcessRequest


app = FastAPI()


# ============================================================
# MODELS
# ============================================================

# Loaded ONCE when the FastAPI process starts.
# Do NOT put these inside process_document().
structure_pipeline = PPStructureV3()
ocr_pipeline = PaddleOCR(lang="en")


# ============================================================
# PAGE RANGE
# ============================================================

first = int(os.getenv("FIRST_PAGE", "1"))
last = int(os.getenv("LAST_PAGE", "1000"))
render_scale = float(os.getenv("RENDER_SCALE", "2.0"))
save_page_images = os.getenv("SAVE_PAGE_IMAGES", "0") == "1"

# TEMPORARY DIAGNOSTIC FLAG — prints cell/OCR geometry.
DEBUG_GEOMETRY = os.getenv("DEBUG_GEOMETRY", "0") == "1"


# ============================================================
# API
# ============================================================

@app.get("/health")
def health():
    return {"status": "ok"}


# ============================================================
# BOX HELPERS
# ============================================================

def box_center(box):
    x0, y0, x1, y1 = box
    return (
        (x0 + x1) / 2,
        (y0 + y1) / 2
    )


def inside(point, box):
    x, y = point

    return (
        box[0] <= x <= box[2]
        and box[1] <= y <= box[3]
    )


def area(box):
    return (
        max(0, box[2] - box[0])
        * max(0, box[3] - box[1])
    )


def overlap(a, b):
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])

    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])

    if x1 <= x0 or y1 <= y0:
        return 0

    return (
        (x1 - x0)
        * (y1 - y0)
    )


def pixmap_to_array(pixmap):
    channels = pixmap.n
    image = np.frombuffer(
        pixmap.samples,
        dtype=np.uint8
    ).reshape(
        pixmap.height,
        pixmap.width,
        channels
    )

    return image[:, :, :3].copy()


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text):
    if text is None:
        return ""

    text = str(text).strip()
    return " ".join(text.split())


def clean_table_cell(value):
    if value is None:
        return "N/A"

    text = clean_text(value)

    while text.lower().startswith("text:"):
        text = text[5:].strip()

    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\$\s+(?=[(\d])", "$", text)
    text = re.sub(r"\s+\$", "$", text)
    text = re.sub(r"\s+([%])", r"\1", text)
    text = re.sub(r"\s+([,;:.])", r"\1", text)

    if re.fullmatch(r"(?:tax\s*)?(?:\.\s*){2,}", text, re.IGNORECASE):
        return "N/A"

    return text or "N/A"


def clean_cell_text(text):
    if text is None:
        return ""

    return clean_table_cell(text) if str(text).strip() else ""


def is_numeric_cell(text):
    return bool(
        re.fullmatch(
            r"\$?\(?\d[\d,]*(?:\.\d+)?\)?(?:[-–]\s*\w+)?",
            text.replace(" ", "")
        )
    )


def is_date_header(text):
    return bool(
        re.fullmatch(
            r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?",
            text,
            flags=re.IGNORECASE
        )
    )


def normalize_currency(text):
    text = clean_table_cell(text)

    if "$" not in text:
        return text

    value = text.replace("$", "").strip()

    if not value or not is_numeric_cell(value):
        return text

    return f"${value}"


def clean_table_row(row):
    return [
        clean_table_cell(
            normalize_currency(value)
        )
        for value in row
    ]


# ============================================================
# TABLE HELPERS
# ============================================================

def get_table_box(table):

    boxes = np.asarray(
        table["cell_box_list"],
        dtype=float
    )

    return [
        float(boxes[:, 0].min()),
        float(boxes[:, 1].min()),
        float(boxes[:, 2].max()),
        float(boxes[:, 3].max())
    ]


FINANCIAL_VALUE_PATTERN = re.compile(
    r"\$?\(?\d[\d,]*(?:\.\d+)?\)?%?(?:\s+(?:million|billion|thousand))?",
    flags=re.IGNORECASE
)


NO_DIGIT_CURRENCY_PATTERN = re.compile(r"^\$+$")


def split_cell_values(text):
    matches = [
        match.group(0).strip()
        for match in FINANCIAL_VALUE_PATTERN.finditer(text)
    ]

    if len(matches) < 2:
        return []

    remainder = FINANCIAL_VALUE_PATTERN.sub("", text)
    if remainder.strip(" $(),.%"):
        return []

    return matches


def cell_rows(cells):
    rows = []

    for cell in sorted(cells, key=lambda item: (item["y"], item["x"])):
        row = next(
            (
                candidate
                for candidate in rows
                if abs(cell["y"] - candidate["y"]) <= max(
                    min(cell["height"], candidate["height"]) * 0.5,
                    5
                )
            ),
            None
        )

        if row is None:
            rows.append({
                "y": cell["y"],
                "height": cell["height"],
                "cells": [cell]
            })
        else:
            row["cells"].append(cell)
            row["y"] = np.mean([
                item["y"]
                for item in row["cells"]
            ])

    for row in rows:
        row["cells"].sort(key=lambda item: item["x"])

    return sorted(rows, key=lambda row: row["y"])


def split_row_cells(row, ocr_box, value_count):
    """Find the physical cells that can receive a split OCR value list."""
    row_cells = row["cells"]
    overlapping = [
        cell
        for cell in row_cells
        if overlap(ocr_box, cell["box"]) > 0
    ]

    if len(overlapping) == value_count:
        return sorted(overlapping, key=lambda cell: cell["x"])

    cells_to_right = [
        cell
        for cell in row_cells
        if cell["x"] >= ocr_box[0]
    ]

    if len(cells_to_right) == value_count:
        return sorted(cells_to_right, key=lambda cell: cell["x"])

    if len(row_cells) == value_count:
        return sorted(row_cells, key=lambda cell: cell["x"])

    if len(row_cells) > value_count:
        return sorted(row_cells, key=lambda cell: cell["x"])[-value_count:]

    return []


def row_has_data(values):
    for value in values[1:]:
        if value is None:
            continue

        value = str(value).strip()
        if value and value.upper() != "N/A" and value != "—" and value != "–" and value != "-":
            return True

    return False


def row_label(values):
    if not values:
        return ""

    value = values[0]
    if value is None:
        return ""

    value = str(value).strip()
    return "" if value.upper() == "N/A" else value


def looks_like_heading(label):
    """Generic structural test for a table heading row."""
    if not label:
        return False

    label = label.strip()
    if label.endswith(":"):
        return True

    words = re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*", label)
    if not words:
        return False

    # A mostly textual, relatively short row with no obvious sentence-ending
    # punctuation is more likely to be a subsection/header than a wrapped data
    # label. This is only a guard against over-merging.
    return (
        len(words) <= 8
        and not any(char.isdigit() for char in label)
        and len(label) <= 70
        and label == label.title()
    )


def label_is_continuation(previous_label, next_label):
    """Generic test for a wrapped/continued table label."""
    if not previous_label or not next_label:
        return False

    previous = previous_label.strip()
    following = next_label.strip()

    # Do not merge a fragment that already contains a sentence boundary.
    # This prevents cases such as "... net" + "of tax. Net income" from
    # swallowing the start of a new logical row.
    if re.search(r"[.!?]\s+[A-Z]", following):
        return False

    # A colon followed by additional words usually indicates that the row
    # contains its own category/label structure (for example "Federal: Current")
    # rather than being a pure continuation of the previous label.
    if ":" in following and not following.endswith(":"):
        return False

    if looks_like_heading(previous) or looks_like_heading(following):
        # A heading can still be continued when the next line is only a short
        # textual fragment (for example a word split across table rows).
        if not (len(following.split()) <= 2 and len(following) <= 30):
            return False

    if previous.endswith((",", "-", "/")):
        return True

    if following[0].islower():
        return True

    # Very short next-line fragments are a strong generic signal of a wrapped
    # label. This catches labels split across physical table rows without
    # depending on company-specific vocabulary.
    following_words = following.split()
    if len(following_words) <= 2 and len(following) <= 30:
        return True

    continuation_words = {
        "and", "or", "of", "to", "from", "for", "with", "by", "in",
        "on", "at", "as", "than", "that", "which", "into", "over",
        "under", "per", "net", "less", "more"
    }
    return previous.split()[-1].lower().strip("(),.;:") in continuation_words


def repair_label_value_artifacts(values):
    """Repair only obvious generic label/footnote attachment artifacts."""
    if not values:
        return values

    values = list(values)

    # OCR sometimes leaves a currency symbol attached to the label boundary.
    # Move it to the first numeric value rather than changing the table layout.
    label = clean_cell_text(values[0])
    if label.endswith("$"):
        stripped_label = label[:-1].rstrip()
        first_value_index = next(
            (i for i, cell in enumerate(values[1:], start=1)
             if cell not in (None, "", "N/A") and is_numeric_cell(clean_cell_text(cell))),
            None
        )
        if first_value_index is not None:
            first_value = clean_cell_text(values[first_value_index])
            if not first_value.startswith("$"):
                values[first_value_index] = f"${first_value}"
            values[0] = stripped_label or "N/A"

    # Leading parenthesized footnote markers can be OCR'd into a numeric cell
    # together with its actual value, e.g. "(2)$(187,020)".
    for i in range(1, len(values)):
        cell = clean_cell_text(values[i])
        if not cell or cell == "N/A":
            continue
        cleaned = re.sub(r"^\(\d+\)\s*", "", cell)
        if cleaned != cell and (is_numeric_cell(cleaned) or "$" in cleaned):
            values[i] = cleaned

    return values


def repair_misaligned_rows(rows):
    """Repair row/label placement using generic row structure, not PDF text rules."""
    index = 0

    while index < len(rows):
        current = rows[index]
        values = current["values"]
        current_label = row_label(values)
        current_data = row_has_data(values)

        # Data row with missing label + next row containing only a label.
        if (
            current_data
            and not current_label
            and index + 1 < len(rows)
        ):
            following = rows[index + 1]
            following_label = row_label(following["values"])
            following_data = row_has_data(following["values"])

            if (
                following_label
                and not following_data
                and not looks_like_heading(following_label)
            ):
                current["values"][0] = following_label
                following["values"][0] = "N/A"

        # Label-only row followed by a data row with a continuation label.
        if index + 1 < len(rows):
            following = rows[index + 1]
            following_label = row_label(following["values"])
            following_data = row_has_data(following["values"])

            if (
                current_label
                and not current_data
                and following_label
                and following_data
                and label_is_continuation(current_label, following_label)
            ):
                width = max(len(current["values"]), len(following["values"]))
                f_values = following["values"] + ["N/A"] * (width - len(following["values"]))
                f_values[0] = f"{current_label} {following_label}".strip()
                following["values"] = f_values
                current["values"][0] = "N/A"

        # Two data rows with wrapped labels and complementary numeric content.
        if index + 1 < len(rows):
            following = rows[index + 1]
            following_label = row_label(following["values"])
            following_data = row_has_data(following["values"])

            if (
                current_label
                and current_data
                and following_label
                and following_data
                and label_is_continuation(current_label, following_label)
            ):
                width = max(len(current["values"]), len(following["values"]))
                c_values = current["values"] + ["N/A"] * (width - len(current["values"]))
                f_values = following["values"] + ["N/A"] * (width - len(following["values"]))

                overlap_data = any(
                    row_has_data(["", c_values[i]]) and
                    row_has_data(["", f_values[i]])
                    for i in range(1, width)
                )

                if not overlap_data:
                    f_values[0] = f"{current_label} {following_label}".strip()
                    for i in range(1, width):
                        if c_values[i] not in ("", "N/A") and f_values[i] in ("", "N/A"):
                            f_values[i] = c_values[i]
                    following["values"] = f_values
                    current["values"] = ["N/A"] + ["N/A"] * (width - 1)

        index += 1

    return rows


def split_compound_row_labels(rows):
    """Split a single OCR label when it contains two logical row labels.

    This is a conservative, document-independent repair. It only acts when
    the label contains sentence-ending punctuation followed by a new
    capitalized phrase, which is a common OCR failure when two table rows are
    recognized as one text box. Numeric values remain attached to the latter
    logical row.
    """
    if not rows:
        return rows

    repaired = []

    boundary_pattern = re.compile(
        r"^(?P<prefix>.+?[.!?])\s+(?P<suffix>[A-Z][A-Za-z0-9][^.!?]{0,80})$"
    )

    for row in rows:
        values = list(row.get("values", []))
        if not values:
            continue

        label = row_label(values)
        if not label:
            repaired.append(row)
            continue

        match = boundary_pattern.match(label)
        if not match:
            repaired.append(row)
            continue

        prefix = match.group("prefix").strip()
        suffix = match.group("suffix").strip()

        # Avoid treating ordinary abbreviations/decimal-like text as row
        # boundaries. A genuine second label should contain at least one
        # alphabetic word and should not simply repeat the prefix.
        if (
            not re.search(r"[A-Za-z]", suffix)
            or suffix.lower() == prefix.lower()
            or len(suffix.split()) > 8
        ):
            repaired.append(row)
            continue

        current = dict(row)
        current_values = list(values)
        current_values[0] = suffix
        current["values"] = current_values

        # If the prefix looks like a continuation of the previous label,
        # attach it to that previous row while preserving the current row's
        # numeric values. This handles patterns such as:
        #   "Discontinued operations, net" + "of tax. Net income"
        # -> "Discontinued operations, net of tax." + "Net income"
        if repaired:
            previous = repaired[-1]
            previous_values = list(previous.get("values", []))
            previous_label = row_label(previous_values)

            if (
                previous_label
                and row_has_data(previous_values)
                and not row_has_data([prefix] + ["N/A"] * (len(previous_values) - 1))
            ):
                combined = f"{previous_label} {prefix}".strip()
                previous_values[0] = combined
                previous["values"] = previous_values

        repaired.append(current)

    return repaired


def merge_continuation_rows(rows):
    """Conservative wrapper retained for compatibility with the pipeline."""
    rows = repair_misaligned_rows(rows)

    merged = []
    for row in rows:
        values = row.get("values", [])
        if not values:
            continue
        merged.append(row)
    return merged


def infer_logical_column_centers(table_box, texts, boxes):
    """
    Infer logical numeric-column X centers from OCR geometry without changing
    PP-StructureV3's physical cell boxes.

    Financial tables commonly contain a label column followed by several
    numeric/year columns. OCR may detect '$' separately from a number, so the
    physical table grid can contain more cells than the logical table has
    columns. The logical column centers are therefore inferred from the OCR
    X positions of numeric/year content.
    """
    candidates = []
    year_positions = []

    def add_position(x):
        if table_box[0] <= x <= table_box[2]:
            candidates.append(float(x))

    for text, box in zip(texts, boxes):
        cleaned = clean_text(text)
        if not cleaned:
            continue

        ocr_box = np.asarray(box, dtype=float).tolist()
        center = box_center(ocr_box)

        if not overlap(ocr_box, table_box) and not inside(center, table_box):
            continue

        # Extract year positions from OCR text. If several years occur in one
        # OCR box, estimate their individual X positions from character index.
        year_matches = list(re.finditer(r"\b(?:19|20)\d{2}\b", cleaned))
        if year_matches:
            text_width = max(ocr_box[2] - ocr_box[0], 1)
            text_len = max(len(cleaned), 1)
            for match in year_matches:
                fraction = (match.start() + match.end()) / 2 / text_len
                year_x = ocr_box[0] + text_width * fraction
                year_positions.append(year_x)
                add_position(year_x)
            continue

        split_values = split_cell_values(cleaned)
        if len(split_values) > 1:
            width = max(ocr_box[2] - ocr_box[0], 1)
            step = width / len(split_values)
            for index in range(len(split_values)):
                add_position(ocr_box[0] + step * (index + 0.5))
            continue

        if cleaned == "$" or is_numeric_cell(cleaned) or re.search(r"\d", cleaned):
            add_position(center[0])

    if not candidates:
        return []

    # Distinct year positions are the strongest signal for financial tables.
    # Otherwise infer column count from the stable clusters in numeric OCR.
    sorted_years = sorted(year_positions)
    unique_years = []
    for x in sorted_years:
        if not unique_years or abs(x - unique_years[-1]) > 20:
            unique_years.append(x)

    if len(unique_years) >= 2:
        expected_numeric_columns = len(unique_years)
    else:
        expected_numeric_columns = min(6, max(1, len(candidates) // 3))

    expected_numeric_columns = min(expected_numeric_columns, 8)

    candidates = sorted(candidates)

    if expected_numeric_columns == 1:
        return [float(np.mean(candidates))]

    # Split sorted X positions into clusters by the largest gaps. This avoids
    # changing the physical cells and naturally groups '$' with nearby values.
    if len(candidates) <= expected_numeric_columns:
        return [float(x) for x in candidates]

    gaps = [
        (candidates[i + 1] - candidates[i], i)
        for i in range(len(candidates) - 1)
    ]
    cut_count = min(expected_numeric_columns - 1, len(gaps))
    cut_indices = sorted(
        index
        for _, index in sorted(gaps, reverse=True)[:cut_count]
    )

    groups = []
    start = 0
    for cut in cut_indices:
        groups.append(candidates[start:cut + 1])
        start = cut + 1
    groups.append(candidates[start:])

    centers = [float(np.mean(group)) for group in groups if group]

    # Year positions are better anchors than inferred cluster means when they
    # are available and agree with the number of numeric columns.
    if len(unique_years) == len(centers):
        centers = [
            float((a + b) / 2)
            for a, b in zip(centers, unique_years)
        ]
        # The averaging above is intentionally conservative; if the year OCR
        # falls inside a combined header box, keep its measured position
        # because it is directly tied to the page geometry.
        centers = [float(x) for x in unique_years]

    return centers


def logical_column_for_x(x, numeric_centers):
    """Return the logical numeric column nearest to X."""
    if not numeric_centers:
        return None
    return min(
        range(len(numeric_centers)),
        key=lambda index: abs(x - numeric_centers[index])
    )


def split_label_and_value(text):
    """Split OCR text when one recognition spans a label and a financial value."""
    text = clean_text(text)
    if not text:
        return None

    matches = list(FINANCIAL_VALUE_PATTERN.finditer(text))
    if not matches:
        return None

    # Only treat the first match as a value split when meaningful text exists
    # before it. The remaining text stays with the same OCR item and is later
    # placed in the value column only when it is itself numeric/financial.
    first = matches[0]
    prefix = text[:first.start()].strip(" .,:;-)")
    value = first.group(0).strip()

    if not prefix or not is_numeric_cell(value):
        return None

    suffix = text[first.end():].strip()
    return prefix, value, suffix


def assign_to_logical_row(logical_rows, geometry_rows, center_y):
    if not logical_rows or not geometry_rows:
        return None

    nearest_index = min(
        range(len(geometry_rows)),
        key=lambda i: abs(center_y - geometry_rows[i]["y"])
    )

    row = geometry_rows[nearest_index]
    distance = abs(center_y - row["y"])

    if distance > max(row["height"] * 0.75, 5):
        return None

    return logical_rows[nearest_index]


def merge_adjacent_financial_fragments(values):
    """
    Merge financial text fragments that belong to the same logical cell.

    This is deliberately geometry-independent and conservative. It only
    merges adjacent value-column entries when the left fragment is a bare
    currency symbol or the right fragment is clearly a numeric value.
    """
    if not values:
        return values

    merged = []
    index = 0

    while index < len(values):
        current = clean_cell_text(values[index])

        if (
            current == "$"
            and index + 1 < len(values)
        ):
            following = clean_cell_text(values[index + 1])

            if (
                following
                and following != "N/A"
                and is_numeric_cell(following)
                and not following.startswith("$")
            ):
                merged.append(f"${following}")
                index += 2
                continue

        merged.append(current)
        index += 1

    return merged


def final_financial_cleanup(value, col_index, row_context=None):
    """Final conservative cleanup for generic financial text artifacts."""
    if not value or value == "N/A":
        return value

    text = str(value).strip()

    # Remove accidental duplicate currency symbols.
    while "$$" in text:
        text = text.replace("$$", "$")

    # A standalone currency symbol in a value column does not represent
    # a numeric value by itself. Keep the label column untouched.
    if col_index > 0 and NO_DIGIT_CURRENCY_PATTERN.fullmatch(text):
        return "N/A"

    return text


def normalize_column_count(rows):
    """Ensure all rows in the table have the same number of columns."""
    if not rows:
        return rows

    max_cols = max(len(row) for row in rows)
    normalized = []

    for row in rows:
        row = list(row)
        if len(row) < max_cols:
            row.extend(["N/A"] * (max_cols - len(row)))
        elif len(row) > max_cols:
            row = row[:max_cols]
        normalized.append(row)

    return normalized


def extract_table_data(table, texts, boxes):
    cell_boxes = np.asarray(
        table["cell_box_list"],
        dtype=float
    )

    cells = [
        {
            "box": [float(value) for value in cell_box],
            "text": [],
            "x": (cell_box[0] + cell_box[2]) / 2,
            "y": (cell_box[1] + cell_box[3]) / 2,
            "height": cell_box[3] - cell_box[1]
        }
        for cell_box in cell_boxes
    ]

    if not cells:
        return []

    table_box = get_table_box(table)
    geometry_rows = cell_rows(cells)

    numeric_centers = infer_logical_column_centers(
        table_box,
        texts,
        boxes
    )

    if not numeric_centers:
        return []

    if DEBUG_GEOMETRY:
        print("\n===== TABLE DEBUG =====")
        print(f"TABLE BOX: {table_box}")
        print(f"PHYSICAL CELL_COUNT: {len(cells)}")
        print(
            "LOGICAL NUMERIC COLUMN CENTERS:",
            [round(x, 2) for x in numeric_centers]
        )
        for index, row in enumerate(geometry_rows):
            print(
                f"ROW[{index}] y={row['y']:.2f} h={row['height']:.2f} "
                f"cells={[round(c['x'], 2) for c in row['cells']]}"
            )

    logical_rows = [
        {
            "y": row["y"],
            "height": row["height"],
            "values": [""] * (len(numeric_centers) + 1),
            "items": []
        }
        for row in geometry_rows
    ]

    for text, ocr_box in zip(texts, boxes):
        text = clean_text(text)
        if not text:
            continue

        ocr_box = np.asarray(ocr_box, dtype=float).tolist()
        center = box_center(ocr_box)

        if not overlap(ocr_box, table_box) and not inside(center, table_box):
            continue

        logical_row = assign_to_logical_row(
            logical_rows,
            geometry_rows,
            center[1]
        )
        if logical_row is None:
            continue

        # Multi-value OCR: assign each numeric token by its estimated X position.
        split_values = split_cell_values(text)
        if len(split_values) > 1:
            width = max(ocr_box[2] - ocr_box[0], 1)
            for index, value in enumerate(split_values):
                value_x = ocr_box[0] + width * (index + 0.5) / len(split_values)
                column = logical_column_for_x(value_x, numeric_centers)
                if column is None:
                    continue
                target = column + 1
                if target < len(logical_row["values"]):
                    existing = logical_row["values"][target]
                    logical_row["values"][target] = (
                        f"{existing} {value}".strip()
                        if existing else value
                    )
            continue

        # Generic label/value split for OCR that spans the logical column boundary.
        split_label = split_label_and_value(text)
        if split_label is not None:
            prefix, value, suffix = split_label
            value_match = re.search(re.escape(value), text)
            value_center_x = center[0]
            if value_match:
                start_fraction = value_match.start() / max(len(text), 1)
                end_fraction = value_match.end() / max(len(text), 1)
                value_center_x = ocr_box[0] + (
                    ocr_box[2] - ocr_box[0]
                ) * ((start_fraction + end_fraction) / 2)

            column = logical_column_for_x(value_center_x, numeric_centers)
            if column is not None:
                target = column + 1
                if target < len(logical_row["values"]):
                    existing = logical_row["values"][target]
                    logical_row["values"][target] = (
                        f"{existing} {value}".strip()
                        if existing else value
                    )

            if prefix:
                existing_label = logical_row["values"][0]
                logical_row["values"][0] = (
                    f"{existing_label} {prefix}".strip()
                    if existing_label else prefix
                )

            # Preserve non-financial suffix text as label content rather than
            # discarding OCR information.
            if suffix and not is_numeric_cell(suffix):
                existing_label = logical_row["values"][0]
                logical_row["values"][0] = (
                    f"{existing_label} {suffix}".strip()
                    if existing_label else suffix
                )
            continue

        is_numericish = (
            text == "$"
            or is_numeric_cell(text)
            or bool(re.search(r"\b(?:19|20)\d{2}\b", text))
            or bool(re.search(r"\d", text))
            or text in {"—", "–", "-"}
        )

        if not is_numericish:
            existing_label = logical_row["values"][0]
            logical_row["values"][0] = (
                f"{existing_label} {text}".strip()
                if existing_label else text
            )
            continue

        column = logical_column_for_x(center[0], numeric_centers)
        if column is None:
            continue

        target = column + 1
        if target >= len(logical_row["values"]):
            continue

        existing = logical_row["values"][target]
        logical_row["values"][target] = (
            f"{existing} {text}".strip()
            if existing else text
        )

        if DEBUG_GEOMETRY:
            print(
                f"OCR {text!r} center_x={center[0]:.2f} "
                f"-> logical_column={target} "
                f"anchor={numeric_centers[column]:.2f}"
            )

    # Remove empty geometric rows before structural reconstruction.
    candidate_rows = []
    for logical_row in logical_rows:
        values = merge_adjacent_financial_fragments(logical_row["values"])
        values = repair_label_value_artifacts(values)
        cleaned = clean_table_row(values)
        final = [
            final_financial_cleanup(cell, index, cleaned)
            for index, cell in enumerate(cleaned)
        ]

        if any(
            cell not in (None, "", "N/A")
            for cell in final
        ):
            candidate_rows.append({"values": final})

    candidate_rows = split_compound_row_labels(candidate_rows)
    candidate_rows = repair_misaligned_rows(candidate_rows)
    candidate_rows = merge_continuation_rows(candidate_rows)

    result = []
    for row in candidate_rows:
        values = row["values"]
        if any(cell not in (None, "", "N/A") for cell in values):
            result.append(values)

    return normalize_column_count(result)


# ============================================================
# TABLE CLEANING
# ============================================================

def clean_tables(tables):

    if not tables:
        return [], []

    table_boxes = [
        get_table_box(table)
        for table in tables
    ]

    keep = []

    for i, current in enumerate(
        table_boxes
    ):

        current_area = area(
            current
        )

        if current_area == 0:
            continue

        duplicate = False

        for j, other in enumerate(
            table_boxes
        ):

            if i == j:
                continue

            other_area = area(
                other
            )

            if other_area == 0:
                continue

            smaller = min(
                current_area,
                other_area
            )

            ratio = (
                overlap(
                    current,
                    other
                )
                / smaller
            )

            # If two table detections overlap
            # almost completely, keep the larger one.
            if (
                ratio > 0.90
                and current_area > other_area
            ):

                duplicate = True
                break

        if not duplicate:
            keep.append(i)

    tables = [
        tables[i]
        for i in keep
    ]

    table_boxes = [
        table_boxes[i]
        for i in keep
    ]

    # Sort top → bottom
    sorted_data = sorted(
        zip(
            tables,
            table_boxes
        ),
        key=lambda x: (
            x[1][1],
            x[1][0]
        )
    )

    tables = [
        x[0]
        for x in sorted_data
    ]

    table_boxes = [
        x[1]
        for x in sorted_data
    ]

    return tables, table_boxes


