import re
from typing import List

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .vectordb_utils import get_embeddings


def parse_chunks_with_position(extracted_knowledge: str):
    """
    Parse chunks from text with page markers like {123}-----
    This version preserves the position information of each segment
    relative to page markers for more precise citation
    """
    # First, prepare a structure that keeps track of page boundaries
    page_pattern = r"\{(\d+)\}-+"
    page_matches = list(re.finditer(page_pattern, extracted_knowledge))

    if not page_matches:
        return []

    page_boundaries = []
    for i, match in enumerate(page_matches):
        # Convert to int, add 1, then back to string to adjust for 0-based indexing
        page_number = str(int(match.group(1)) + 1)
        start_pos = match.end()

        # End position is the start of next page marker or end of text
        end_pos = len(extracted_knowledge)
        if i < len(page_matches) - 1:
            end_pos = page_matches[i + 1].start()

        page_boundaries.append(
            {
                "page_number": page_number,
                "start_pos": start_pos,
                "end_pos": end_pos,
                "content": extracted_knowledge[start_pos:end_pos].strip(),
            }
        )

    return page_boundaries


def split_text(text: str):
    """
    Splits text into segments based on:
    - Complete sentences (ending with ., !, ?)
    - Preserves bullet lists and enumerations as complete segments

    Args:
        text (str): The input text to split.

    Returns:
        list: An array of text segments.
    """
    if not text or not isinstance(text, str):
        return []

    # Normalize line endings
    text = text.replace("\r\n", "\n")

    # Split into paragraphs (defined by blank lines)
    paragraphs = re.split(r"\n\s*\n", text)
    result_segments = []

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        # Check if this paragraph contains ANY list markers
        lines = paragraph.split("\n")

        # Improved regex pattern to match all types of bullet points and enumerations
        # This checks for bullets (•, -, *) and various numbering formats (1., a), ii., etc.)
        list_marker_pattern = r"^\s*([•\-\*]|\d+[.)]|[a-z][.)]|[ivxlcdm]+[.)])"

        # Count lines with list markers
        has_list_markers = any(re.match(list_marker_pattern, line.strip(), re.IGNORECASE) for line in lines)

        if has_list_markers:
            # This paragraph contains list items, keep it as one segment
            result_segments.append(paragraph)
        else:
            # For regular paragraphs, split by sentence boundaries
            # Look for period, exclamation point, or question mark followed by space and capital letter
            sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", paragraph)
            for sentence in sentences:
                if sentence.strip():
                    result_segments.append(sentence.strip())

    return result_segments


def add_citations(answer_segments: List[str], page_boundaries: dict, threshold: float):
    for page in page_boundaries:
        content = page["content"]
        vector = get_embeddings(text=content)
        page["vector"] = vector

    chunks_vectors = np.stack([page["vector"] for page in page_boundaries], axis=0)
    selected_idxs = []

    for segment in answer_segments:
        segment_vector = np.array(get_embeddings(segment))[None, ...]
        scores = cosine_similarity(segment_vector, chunks_vectors)
        max_score = np.max(scores)

        if max_score > threshold:
            selected_idxs.append((segment, np.argmax(scores).item()))

    updated_sections = []

    for s in selected_idxs:
        updated_sections.append((s[0], page_boundaries[s[1]]["page_number"]))

    unique_indexes = []

    for s in updated_sections[1:]:
        if not s[0].endswith(":") and not s[0].startswith("#") and not "![]" in s[0] and not s[0].endswith("**"):
            unique_indexes.append(s[1])

    unique_indexes = np.unique(unique_indexes)
    full_text = ""

    for idx, section in enumerate(updated_sections):
        if (
            idx == 0
            or section[0].endswith(":")
            or section[0].startswith("#")
            or "![]" in section[0]
            or section[0].endswith("**")
            or "<div" in section[0]
        ):
            full_text += section[0] + "\n\n"

            continue

        citation = section[1]
        citation_index = np.argwhere(unique_indexes == citation).item()
        s = section[0] + f" [{citation_index}]({citation})"

        full_text += s + "\n\n"

    return full_text.strip()


def process_citations(answer, text_chunks, threshold=0.5):
    """Main function to process citations"""
    # Parse chunks with position info
    page_boundaries = parse_chunks_with_position(text_chunks)

    # Extract segments with position info
    answer_segments = split_text(text=answer)

    # Find matches
    return add_citations(answer_segments=answer_segments, page_boundaries=page_boundaries, threshold=threshold)