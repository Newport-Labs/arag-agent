import multiprocessing
import re
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from functools import partial
from typing import Dict, List

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


def split_text(text: str, min_segment_length: int = 10):
    """
    Splits text into meaningful segments while preserving structural elements.

    Args:
        text (str): The input text to split
        min_segment_length (int): Minimum length for a segment to be included

    Returns:
        list: Array of text segments with their original positions
    """
    if not text or not isinstance(text, str):
        return []

    # Normalize line endings and whitespace
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Track protected regions and their types
    protected_regions = []

    # 1. Protect images (markdown and HTML)
    image_patterns = [
        r"!\[[^\]]*\]\([^)]+\)",  # Markdown images
        r"<img[^>]+>",  # HTML images
        r"<div[^>]*>.*?</div>",  # General divs (multi-line)
    ]

    for pattern in image_patterns:
        for match in re.finditer(pattern, text, re.DOTALL | re.IGNORECASE):
            protected_regions.append(
                {"start": match.start(), "end": match.end(), "content": match.group(0), "type": "image"}
            )

    # 2. Protect lists (bullet points, numbered lists)
    list_start_positions = []
    list_end_positions = []
    lines = text.split("\n")
    in_list = False
    list_indent = 0
    current_list_start = 0

    list_patterns = [
        r"^\s*[•\-\*]\s",  # Bullet lists
        r"^\s*\d+[.)]",  # Numbered lists
        r"^\s*[a-z][.)]",  # Alphabetical lists
        r"^\s*[ivxlcdm]+[.)]",  # Roman numeral lists
    ]

    # Find list blocks
    current_position = 0
    for i, line in enumerate(lines):
        is_list_item = any(re.match(pattern, line) for pattern in list_patterns)
        is_indented = line.startswith(" " * 4) or line.startswith("\t")
        is_list_continuation = False

        # Check if this is a continuation of a list item (indented under a bullet)
        if not is_list_item and in_list and is_indented and line.strip():
            is_list_continuation = True

        # Start of a new list
        if is_list_item and not in_list:
            in_list = True
            current_list_start = current_position

        # End of a list
        elif in_list and not is_list_item and not is_list_continuation and line.strip():
            in_list = False
            list_start_positions.append(current_list_start)
            list_end_positions.append(current_position)

        # Empty line terminates a list unless the next line is also a list item
        elif in_list and not line.strip():
            if i + 1 < len(lines):
                next_is_list = any(re.match(pattern, lines[i + 1]) for pattern in list_patterns)
                next_is_continuation = lines[i + 1].startswith(" " * 4) or lines[i + 1].startswith("\t")
                if not next_is_list and not next_is_continuation:
                    in_list = False
                    list_start_positions.append(current_list_start)
                    list_end_positions.append(current_position)

        current_position += len(line) + 1  # +1 for the newline

    # Handle a list at the end of the text
    if in_list:
        list_start_positions.append(current_list_start)
        list_end_positions.append(len(text))

    # Add lists to protected regions
    for start, end in zip(list_start_positions, list_end_positions):
        protected_regions.append({"start": start, "end": end, "content": text[start:end], "type": "list"})

    # 3. Protect code blocks
    code_pattern = r"```[^\n]*\n.*?```"
    for match in re.finditer(code_pattern, text, re.DOTALL):
        protected_regions.append(
            {"start": match.start(), "end": match.end(), "content": match.group(0), "type": "code"}
        )

    # 4. Protect tables
    table_pattern = r"\|[^\n]+\|\n\|[-:| ]+\|\n(\|[^\n]+\|\n)+"
    for match in re.finditer(table_pattern, text, re.DOTALL):
        protected_regions.append(
            {"start": match.start(), "end": match.end(), "content": match.group(0), "type": "table"}
        )

    # 5. Protect headers
    header_pattern = r"^#{1,6}\s+.+$"
    for match in re.finditer(header_pattern, text, re.MULTILINE):
        protected_regions.append(
            {"start": match.start(), "end": match.end(), "content": match.group(0), "type": "header"}
        )

    # Sort protected regions by their start position
    protected_regions.sort(key=lambda x: x["start"])

    # Merge overlapping protected regions
    merged_regions = []
    if protected_regions:
        current_region = protected_regions[0]
        for region in protected_regions[1:]:
            if region["start"] <= current_region["end"]:
                # Regions overlap, merge them
                current_region["end"] = max(current_region["end"], region["end"])
                current_region["content"] = text[current_region["start"] : current_region["end"]]
                current_region["type"] = f"{current_region['type']},{region['type']}"
            else:
                # No overlap, add the current region and move to the next
                merged_regions.append(current_region)
                current_region = region
        merged_regions.append(current_region)

    protected_regions = merged_regions

    # Create a list of non-protected text segments that need splitting
    segments_to_split = []
    last_end = 0

    for region in protected_regions:
        if region["start"] > last_end:
            segments_to_split.append(
                {
                    "start": last_end,
                    "end": region["start"],
                    "content": text[last_end : region["start"]],
                    "type": "regular",
                }
            )
        last_end = region["end"]

    # Add the last segment if needed
    if last_end < len(text):
        segments_to_split.append({"start": last_end, "end": len(text), "content": text[last_end:], "type": "regular"})

    # Process regular segments into sentences
    result_segments = []

    # Add all protected regions directly
    for region in protected_regions:
        result_segments.append(
            {
                "content": region["content"],
                "type": region["type"],
                "start": region["start"],
                "end": region["end"],
                "protected": True,
            }
        )

    # Split regular text into sentences and paragraphs
    for segment in segments_to_split:
        content = segment["content"].strip()
        if not content:
            continue

        # Split paragraphs first
        paragraphs = re.split(r"\n\s*\n", content)

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            # Split by sentence boundaries
            sentence_pattern = r'(?<=[.!?][\'")\s])\s+(?=[A-Z])'
            sentences = re.split(sentence_pattern, paragraph)

            for sentence in sentences:
                sentence = sentence.strip()
                if sentence and len(sentence) >= min_segment_length:
                    # Calculate approximate position in original text
                    sentence_start = text.find(sentence, segment["start"])
                    sentence_end = sentence_start + len(sentence)

                    result_segments.append(
                        {
                            "content": sentence,
                            "type": "sentence",
                            "start": sentence_start,
                            "end": sentence_end,
                            "protected": False,
                        }
                    )

    # Sort all segments by their position in the original text
    result_segments.sort(key=lambda x: x["start"])

    return result_segments


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


def get_embedding_for_page(page, get_embeddings_func):
    """Get embedding for a single page - for parallel processing"""
    content = page["content"]
    # Handle empty content
    if not content or not isinstance(content, str) or len(content.strip()) < 10:
        return np.zeros((768,))  # Use default dimension

    try:
        return get_embeddings_func(text=content)
    except Exception as e:
        print(f"Error getting embeddings: {e}")
        # Use zero vector as fallback
        return np.zeros((768,))


def process_segment_for_citation(
    segment_data, chunks_vectors, page_boundaries, threshold, get_embeddings_func, min_length=30
):
    """Process a single segment for citation matching - for parallel processing"""
    segment, segment_idx = segment_data

    # Types of content that shouldn't be cited
    no_citation_types = {"image", "header", "code", "table"}

    # Check if this is a protected segment type that shouldn't get citations
    segment_type = segment.get("type", "")

    # Images and headers never get citations
    if any(t in segment_type.split(",") for t in no_citation_types) or segment.get("protected", False):
        return (segment_idx, -1)

    # Lists are usually cited, but we need to check content
    if "list" in segment_type:
        # Check if this list has sections that shouldn't be cited (like "Remedy:")
        content = segment["content"]
        if "Remedy:" in content or "remedy:" in content or len(content) < min_length:
            return (segment_idx, -1)

    # Check if content is too short for citation
    content = segment["content"]
    if len(content) < min_length:
        return (segment_idx, -1)

    # Skip citation for obvious references
    if "refer to section" in content.lower() or "see section" in content.lower():
        return (segment_idx, -1)

    try:
        segment_vector = np.array(get_embeddings_func(text=content))[None, ...]
        scores = cosine_similarity(segment_vector, chunks_vectors)
        max_score = np.max(scores)

        if max_score > threshold:
            return (segment_idx, np.argmax(scores).item())
        else:
            # Add segments that don't meet threshold without citation
            return (segment_idx, -1)
    except Exception as e:
        print(f"Error processing segment: {e}")
        # Keep the segment without citation if there's an error
        return (segment_idx, -1)


def add_citations_parallel(
    answer_segments: List[Dict],
    page_boundaries: List[Dict],
    threshold: float = 0.5,
    get_embeddings_func=None,
    min_length: int = 30,
):
    """
    Add citations to answer segments based on similarity to reference content.
    This version uses parallel processing for improved performance.

    Args:
        answer_segments (List[Dict]): List of text segments with metadata
        page_boundaries (List[Dict]): List of page boundaries with content and page numbers
        threshold (float): Similarity threshold for citation (default: 0.5)
        get_embeddings_func: Function to get embeddings from text
        min_length (int): Minimum text length for citation consideration

    Returns:
        str: Text with citations added
    """
    if not get_embeddings_func:
        raise ValueError("A function to get embeddings must be provided")

    # Skip processing if no page boundaries or segments
    if not page_boundaries or not answer_segments:
        return "\n\n".join([s["content"] for s in answer_segments])

    # Determine number of workers (CPUs)
    num_workers = max(1, multiprocessing.cpu_count() - 1)  # Leave one CPU free

    # Process page boundaries to get embeddings in parallel
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        # Create a partial function with the embedding function
        get_embedding_partial = partial(get_embedding_for_page, get_embeddings_func=get_embeddings_func)

        # Process pages in parallel
        embeddings = list(executor.map(get_embedding_partial, page_boundaries))

        # Assign embeddings back to pages
        for i, page in enumerate(page_boundaries):
            page["vector"] = embeddings[i]

    # Stack vectors for efficient similarity computation
    try:
        chunks_vectors = np.stack([page["vector"] for page in page_boundaries], axis=0)
    except ValueError:
        print("Warning: Could not stack vectors, dimensions may not match")
        return "\n\n".join([s["content"] for s in answer_segments])

    # Prepare segments for parallel processing
    segment_data = [(segment, i) for i, segment in enumerate(answer_segments)]

    # Process segments in parallel
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        # Create a partial function with fixed arguments
        process_segment_partial = partial(
            process_segment_for_citation,
            chunks_vectors=chunks_vectors,
            page_boundaries=page_boundaries,
            threshold=threshold,
            get_embeddings_func=get_embeddings_func,
            min_length=min_length,
        )

        # Process segments in parallel and get results
        citation_results = list(executor.map(process_segment_partial, segment_data))

    # Convert results back to the format expected by post-processing
    selected_idxs = []
    for idx, citation_idx in citation_results:
        selected_idxs.append((answer_segments[idx], citation_idx))

    # Post-process selected_idxs to group header-list citations
    processed_idxs = []
    i = 0
    while i < len(selected_idxs):
        segment, idx = selected_idxs[i]
        segment_type = segment.get("type", "")

        # Check if this is a header with a citation
        if "header" in segment_type and idx != -1:
            # Add header with its citation
            header_citation = idx
            processed_idxs.append((segment, header_citation))
            i += 1

            # Look ahead for consecutive list items with the same citation
            while i < len(selected_idxs) and "list" in selected_idxs[i][0].get("type", ""):
                list_segment, list_idx = selected_idxs[i]

                # If list item has the same citation as header, remove its citation
                if list_idx == header_citation:
                    processed_idxs.append((list_segment, -1))  # Remove citation
                else:
                    # Different citation, keep it
                    processed_idxs.append((list_segment, list_idx))

                i += 1
        else:
            # Process consecutive segments with the same citation
            current_citation = idx
            if current_citation != -1:
                # Check for consecutive segments with same citation (not headers or lists)
                group_segment_types = set()
                group_segments = []
                group_segments.append((segment, current_citation))
                j = i + 1

                # Group up to 3 consecutive segments with same citation
                while (
                    j < len(selected_idxs)
                    and selected_idxs[j][1] == current_citation
                    and len(group_segments) < 3
                    and "header" not in selected_idxs[j][0].get("type", "")
                    and "list" not in selected_idxs[j][0].get("type", "")
                ):
                    next_segment, _ = selected_idxs[j]
                    group_segment_types.add(next_segment.get("type", ""))
                    group_segments.append((next_segment, -1))  # Remove duplicate citation
                    j += 1

                # If we found a group, add it
                if len(group_segments) > 1:
                    processed_idxs.extend(group_segments)
                    i = j
                else:
                    # No group found, add as is
                    processed_idxs.append((segment, idx))
                    i += 1
            else:
                # No citation, add as is
                processed_idxs.append((segment, idx))
                i += 1

    # Map to page numbers using processed_idxs
    updated_sections = []
    for s, idx in processed_idxs:
        if idx == -1:
            updated_sections.append((s, None))
        else:
            updated_sections.append((s, page_boundaries[idx]["page_number"]))

    # Get unique page numbers for citation indices
    unique_indexes = []
    for s, page in updated_sections:
        if page is not None:
            unique_indexes.append(page)

    unique_indexes = sorted(set(unique_indexes))

    # Create a mapping from page numbers to citation indices - FIX: Start from 1 instead of 0
    citation_map = {page: idx + 1 for idx, page in enumerate(unique_indexes)}

    # Build the final text with citations
    # Reconstruct the original text structure, preserving relative positions

    # First, add citations to the segments
    segments_with_citations = []

    for segment, page in updated_sections:
        content = segment["content"]

        # Skip citation for protected segments
        if page is None:
            segments_with_citations.append((segment, content))
        else:
            # Add citation
            citation_index = citation_map[page]
            cited_content = f"{content} [{citation_index}]({page})"
            segments_with_citations.append((segment, cited_content))

    # Sort segments by their original position
    segments_with_citations.sort(key=lambda x: x[0]["start"])

    # Build final text by adding appropriate spacing
    final_segments = []
    previous_type = None

    for i, (segment, content) in enumerate(segments_with_citations):
        segment_type = segment.get("type", "")

        # Determine how to join this segment
        if "image" in segment_type or "table" in segment_type:
            # Images and tables get extra spacing
            final_segments.append("")
            final_segments.append(content)
            final_segments.append("")
        elif "header" in segment_type:
            # Headers get extra spacing
            if previous_type and previous_type != "header":
                final_segments.append("")
            final_segments.append(content)
        elif "list" in segment_type:
            # Lists get preserved as is
            final_segments.append(content)
        elif i > 0 and "header" in segments_with_citations[i - 1][0].get("type", ""):
            # Text after headers doesn't need extra spacing
            final_segments.append(content)
        elif previous_type and previous_type == "sentence" and segment_type == "sentence":
            # Add double line break between paragraphs
            final_segments.append("")
            final_segments.append(content)
        else:
            # Regular text
            final_segments.append(content)

        previous_type = segment_type

    # Join with double line breaks - FIX: Use double newlines for paragraph separation
    # First, convert empty strings to explicit paragraph markers
    marked_segments = []
    for segment in final_segments:
        if not segment:
            marked_segments.append("__PARAGRAPH_BREAK__")
        else:
            marked_segments.append(segment)

    # Now join segments with appropriate breaks
    parts = []
    for segment in marked_segments:
        if segment == "__PARAGRAPH_BREAK__":
            # Don't add the marker to the output text
            continue
        parts.append(segment)

    # Join all parts with double newlines to ensure paragraph separation
    full_text = "\n\n".join(parts)

    # Clean up multiple blank lines
    full_text = re.sub(r"\n{3,}", "\n\n", full_text)

    return full_text.strip()


def process_citations(answer, text_chunks, threshold=0.5, get_embeddings_func=None):
    """Main function to process citations with parallel processing"""
    if not get_embeddings_func:
        raise ValueError("A function to get embeddings must be provided")

    # Parse chunks with position info
    page_boundaries = parse_chunks_with_position(text_chunks)

    # Extract segments with metadata
    answer_segments = split_text(text=answer)

    # Find matches and add citations using parallel processing
    return add_citations_parallel(
        answer_segments=answer_segments,
        page_boundaries=page_boundaries,
        threshold=threshold,
        get_embeddings_func=get_embeddings_func,
    )


def chunk_list(lst, chunk_size):
    """Helper function to divide a list into chunks of specified size"""
    for i in range(0, len(lst), chunk_size):
        yield lst[i : i + chunk_size]


def batch_process_embeddings(texts, get_embeddings_func, batch_size=16):
    """Process embeddings in batches for better efficiency"""
    batches = list(chunk_list(texts, batch_size))

    all_embeddings = []
    for batch in batches:
        try:
            batch_embeddings = get_embeddings_func(texts=batch)  # Assuming the function supports batch processing
            all_embeddings.extend(batch_embeddings)
        except TypeError:
            # If batch processing is not supported, fall back to individual processing
            for text in batch:
                embedding = get_embeddings_func(text=text)
                all_embeddings.append(embedding)

    return all_embeddings