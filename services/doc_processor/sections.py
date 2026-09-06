from core import *

# ============================================================
# SECTION DETECTION
# ============================================================

SECTION_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from",
    "in", "into", "is", "of", "on", "or", "the", "to", "with"
}

def is_numbered_section(text):
    return bool(
        re.match(
            r"^\s*(?:item\s+|note\s+)?\d+(?:\.\d+)*[.)-]?(?:\s|$)",
            text,
            flags=re.IGNORECASE
        )
    )


def normalize_section(text):
    text = clean_text(text)


    text = re.sub(
        r"^\s*(?:item\s+|note\s+)?\d+(?:\.\d+)*[.)-]?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\b(?:company|companies)[’']s\b",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(r"\s+([,;:])", r"\1", text)
    text = re.sub(r"([,;:])(?=\S)", r"\1 ", text)
    return text.strip(" ,;:")


def is_section_title_candidate(text):
    text = clean_text(text)
    words = re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)*", text)
    digits = sum(character.isdigit() for character in text)

    if not text or not words or len(text) > 100:
        return False

    if digits > max(2, len(text) * 0.15):
        return False

    if len(words) > 12 or text.endswith((".", ":")):
        return False

    if re.fullmatch(r"[\d\s$%.,()/-]+", text):
        return False

    return sum(character.isalpha() for character in text) >= len(text) * 0.5


def parsing_title_text(parsing_res_list, title_box):
    """Return text from a parsing item that belongs to this title region."""
    if not parsing_res_list:
        return None

    candidates = []

    def visit(value):
        if isinstance(value, dict):
            text = value.get("block_content") or value.get("text")
            box = (
                value.get("block_bbox")
                or value.get("bbox")
                or value.get("coordinate")
                or value.get("box")
            )

            if text and box is not None:
                candidate_box = np.asarray(box, dtype=float).reshape(-1).tolist()

                if len(candidate_box) >= 4:
                    candidate_box = candidate_box[:4]
                    ratio = overlap(candidate_box, title_box) / max(area(candidate_box), 1)

                    if ratio >= 0.5 and is_section_title_candidate(str(text)):
                        candidates.append((ratio, clean_text(text)))

            for child in value.values():
                visit(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child)

    visit(parsing_res_list)
    return max(candidates, default=(0, None))[1]



def detect_sections(
    texts,
    boxes,
    layout,
    table_boxes,
    parsing_res_list=None
):
    sections = []

    for item in layout.get("boxes", []):
        if item.get("label") != "paragraph_title":
            continue

        title_box = [float(value) for value in item["coordinate"]]
        title_text = parsing_title_text(
            parsing_res_list,
            title_box
        )

        if not title_text:
            candidates = []

            for text, box in zip(texts, boxes):
                candidate_text = clean_text(text)
                candidate_box = np.asarray(box, dtype=float).tolist()

                if not is_section_title_candidate(candidate_text):
                    continue

                if any(
                    inside(box_center(candidate_box), table_box)
                    for table_box in table_boxes
                ):
                    continue

                candidate_area = area(candidate_box)
                title_area = area(title_box)
                alignment = overlap(title_box, candidate_box) / max(candidate_area, 1)
                title_coverage = overlap(title_box, candidate_box) / max(title_area, 1)

                if alignment < 0.5 and title_coverage < 0.35:
                    continue

                candidates.append((
                    alignment + title_coverage,
                    candidate_text
                ))

            title_text = max(candidates, default=(0, None))[1]

        if not title_text:
            continue

        numbered = is_numbered_section(title_text)
        title_text = normalize_section(title_text)

        if not title_text or not is_section_title_candidate(title_text):
            continue

        sections.append({
            "text": title_text,
            "box": title_box,
            "numbered": numbered
        })

    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

    unique = []
    seen = set()

    for section in sections:

        key = (
            section["text"].lower(),
            round(
                section["box"][1],
                1
            )
        )

        if key in seen:
            continue

        seen.add(key)

        unique.append(
            section
        )

    # --------------------------------------------------------
    # Prefer numbered headings as main sections
    # --------------------------------------------------------

    main_sections = []

    for section in unique:

        if section["numbered"]:
            main_sections.append(
                section
            )

    # If numbered headings exist, use them.
    # Otherwise fall back to paragraph titles.
    if main_sections:
        unique = main_sections + [
            section
            for section in unique
            if not section["numbered"]
        ]

    # --------------------------------------------------------
    # Sort top → bottom
    # --------------------------------------------------------

    unique.sort(
        key=lambda s: (
            s["box"][1],
            s["box"][0]
        )
    )

    print(
        "SECTIONS DETECTED:",
        len(unique)
    )

    for section in unique:

        print(
            "SECTION:",
            repr(section["text"])
        )

    return unique


# ============================================================
# SECTION ASSIGNMENT
# ============================================================

def get_section(
    block_box,
    sections
):

    if not sections:
        return None

    block_y = block_box[1]

    current_section = None

    # The most recent section heading above
    # the block is inherited.
    for section in sections:

        if section["box"][1] <= block_y:

            current_section = section["text"]

        else:
            break

    return current_section


# ============================================================
# DOCUMENT PROCESSING
# ============================================================

