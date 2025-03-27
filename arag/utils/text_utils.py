import concurrent.futures
import re
from collections import defaultdict
from typing import List, Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .vectordb_utils import _get_chunks, get_raw_section


def convert_citations(text):
    # This regex finds patterns like [1, 2, 3] or [1,2,3] (with or without spaces)
    pattern = r"\[(\d+(?:\s*,\s*\d+)+)\]"

    def replacement(match):
        # Extract the numbers from the matched group
        numbers = re.findall(r"\d+", match.group(1))
        # Create individual citations and join them
        return "".join(f"[{num}]" for num in numbers)

    # Replace all occurrences
    result = re.sub(pattern, replacement, text)

    return result


def fix_markdown_tables(markdown_text):
    """
    Fix various formatting issues in Markdown tables using regex.

    This function corrects common problems in Markdown tables:
    - Missing pipe characters (|) at the beginning or end of rows
    - Inconsistent number of columns across rows
    - Missing or malformed separator row (between header and data)
    - Irregular spacing and alignment issues
    - Preserves alignment markers in separator rows (:---:, :---, ---:)

    Args:
        markdown_text (str): Text containing potentially malformed Markdown tables

    Returns:
        str: Text with fixed Markdown tables
    """
    lines = markdown_text.split("\n")
    in_table = False
    current_table = []
    result = []

    # Process the text line by line to identify tables
    for line in lines:
        # Check if the line looks like part of a table (contains pipe character)
        # Skip code blocks (lines starting with ```)
        if "|" in line and not line.strip().startswith("```"):
            if not in_table:
                in_table = True
            current_table.append(line)
        else:
            # If we were in a table but this line isn't part of it
            if in_table:
                # Fix and add the table we've collected
                fixed_table = fix_table(current_table)
                result.extend(fixed_table)
                current_table = []
                in_table = False
            # Add the non-table line
            result.append(line)

    # Handle a table at the end of the text
    if in_table:
        fixed_table = fix_table(current_table)
        result.extend(fixed_table)

    return "\n".join(result)


def fix_table(table_lines):
    """Fix a single Markdown table."""
    # Remove any empty lines and clean up each line
    rows = [row.strip() for row in table_lines if row.strip()]
    if not rows:
        return table_lines

    # Make sure all rows have pipes at start and end
    for i in range(len(rows)):
        if not rows[i].startswith("|"):
            rows[i] = "| " + rows[i]
        if not rows[i].endswith("|"):
            rows[i] = rows[i] + " |"

    # Find the maximum number of columns in any row
    max_cols = 0
    for row in rows:
        cols = row.strip("|").split("|")
        max_cols = max(max_cols, len(cols))

    # Check for a separator row (contains dashes)
    has_separator = False
    separator_idx = -1

    for i, row in enumerate(rows):
        if i > 0 and "-" in row and re.search(r"\|\s*[:]*[-]+[:]*\s*\|", row):
            has_separator = True
            separator_idx = i
            break

    # If no separator row found and we have multiple rows, add one after the first row
    if not has_separator and len(rows) > 1:
        separator = "| " + " | ".join(["---"] * max_cols) + " |"
        rows.insert(1, separator)
        separator_idx = 1

    # Process each row to ensure consistent columns and formatting
    fixed_rows = []

    for i, row in enumerate(rows):
        cols = row.strip("|").split("|")
        cols = [col.strip() for col in cols]

        # Special handling for the separator row
        if i == separator_idx:
            separators = []
            for j in range(max_cols):
                if j < len(cols) and re.match(r"^:?-+:?$", cols[j]):
                    # Preserve alignment markers
                    separators.append(cols[j])
                else:
                    # Default separator
                    separators.append("---")

            fixed_rows.append("| " + " | ".join(separators) + " |")
        else:
            # For data rows, ensure consistent column count
            while len(cols) < max_cols:
                cols.append("")  # Add empty cells if needed
            cols = cols[:max_cols]  # Truncate if too many

            fixed_rows.append("| " + " | ".join(cols) + " |")

    return fixed_rows


def deduplicate_by_similarity(chunks, embeddings, similarity_threshold=0.85):
    """
    Deduplicate a list of texts based on the cosine similarity of their embeddings.

    Args:
        texts: List of text strings to deduplicate
        similarity_threshold: Threshold above which texts are considered duplicates (0-1)

    Returns:
        List of deduplicated texts
    """
    if not chunks:
        return []

    # Convert to numpy array for easier processing
    embeddings_array = np.array(embeddings)

    # Calculate pairwise cosine similarities
    similarities = cosine_similarity(embeddings_array)

    # Track which texts to keep
    to_keep = [True] * len(chunks)

    # For each text, mark similar texts as duplicates (don't keep)
    for i in range(len(chunks)):
        if to_keep[i]:  # Only check if this text is still considered unique
            for j in range(i + 1, len(chunks)):
                if to_keep[j] and similarities[i, j] >= similarity_threshold:
                    to_keep[j] = False  # Mark as duplicate

    return (
        [text for i, text in enumerate(chunks) if to_keep[i]],
        [embedding for i, embedding in enumerate(embeddings) if to_keep[i]],
    )


def align_text_images(text):
    # Match any image markdown
    image_pattern = r"!\[([^\]]*)\]\(([^)]+)\)"

    def replace_with_centered_image(match):
        alt_text = match.group(1)
        image_path = match.group(2)

        # Add two newlines before the div to separate it from previous text
        return (
            '<div style="text-align: center;">'
            f'<img src="{image_path}" alt="{alt_text}"/>'
            f"<p>{alt_text}</p>"
            "</div>"
        )

    # Replace all image matches with centered images
    result = re.sub(image_pattern, replace_with_centered_image, text)

    return add_spacing_around_divs(result)


def perform_similarity_search(
    vectordb_endopoint: str, queries: List[str], threshold, section: Optional[str] = None, num_chunks: int = 3
) -> List[str]:
    chunks = []
    embeddings = []

    for query in queries:
        chunk = _get_chunks(vectordb_endopoint, query, num_chunks, section=section)

        for c in chunk:
            chunks.append(c["properties"]["text"])
            embeddings.append(c["vector"]["text_vector"])

    # Dedup exact chunks
    chunks, embeddings = deduplicate_by_similarity(chunks=chunks, embeddings=embeddings, similarity_threshold=threshold)

    return (chunks, embeddings)


def extract_section(text: str) -> str:
    # Regex to match the first number in the string
    pattern = r"\d+"

    match = re.search(pattern, text)

    if match:
        return match.group()

    return None


def has_similar_vector(vector, embedding_list, threshold):
    """
    Check if any vector in the embedding_list has a similarity with the given vector
    that exceeds the threshold.

    Args:
        vector (numpy.ndarray): The query vector embedding
        embedding_list (list): List of vector embeddings to compare against
        threshold (float): Similarity threshold (between 0 and 1)

    Returns:
        bool: True if any vector's similarity exceeds threshold, False otherwise
    """
    # Reshape vector to 2D array (required for sklearn's cosine_similarity)
    vector_reshaped = np.array(vector).reshape(1, -1)

    # Convert embedding_list to a 2D numpy array
    embeddings_array = np.array(embedding_list)

    # Calculate cosine similarity between vector and all embeddings at once
    similarities = cosine_similarity(vector_reshaped, embeddings_array)[0]

    # Check if any similarity exceeds the threshold
    return np.any(similarities > threshold)


def remove_hash_lines(text):
    return re.sub(r"\n#+\n", "", text)


def remove_reference_section(input_string):
    # Pattern to match everything between the beginning (after "I have a")
    # and before any number of "#" followed by "References" or "Reference"
    pattern = r"([\s\S]*?)\s*#{1,}\s*References?"

    # Search for the pattern
    match = re.search(pattern, input_string)

    if match:
        return match.group(1).strip()
    else:
        return input_string


def add_spacing_around_divs(text):
    """
    Ensures there are double newlines (\n\n) before and after <div> elements.

    Args:
        text (str): The input text containing div elements

    Returns:
        str: The text with proper spacing around div elements
    """
    # First, normalize any existing div spacing
    # Replace any sequence of newlines before a div with a single newline
    text = re.sub(r"\n+(<div)", r"\n\1", text)

    # Replace any sequence of newlines after a closing div with a single newline
    text = re.sub(r"(</div>)\n+", r"\1\n", text)

    # Now add the double newlines before all div openings
    text = re.sub(r"([^\n])\s*(<div)", r"\1\n\n\2", text)

    # Add double newlines after all div closings
    text = re.sub(r"(</div>)\s*([^\n])", r"\1\n\n\2", text)

    # Handle special case: beginning of text with a div
    text = re.sub(r"^(<div)", r"\1", text)

    # Handle special case: end of text with a div
    text = re.sub(r"(</div>)$", r"\1", text)

    # Handle consecutive divs - ensure double newline between them
    text = re.sub(r"(</div>)\s*(<div)", r"\1\n\n\2", text)

    return text


def extract_section_numbers(text: str) -> List[str]:
    """
    Extract section numbers from text in various formats and layouts:
    - "Section X.Y" references
    - "X.Y:" with colon
    - "X. Title" at line start
    - "X.Y.Z. Title.." with varying punctuation
    - Nested indented sections with various formats

    Args:
        text (str): Input text containing section references

    Returns:
        List[str]: Sorted list of unique section numbers
    """
    # First, clean up the text to normalize some patterns
    # Replace multiple dots with a single one
    cleaned_text = re.sub(r"\.{2,}", ".", text)

    # Core section number pattern: digits separated by periods
    section_num_pattern = r"\d+(?:\.\d+)*"

    # Combined pattern for different formats
    patterns = [
        # Format: "Section X.Y"
        rf"Section\s+({section_num_pattern})",
        # Format: "X.Y:" (with colon)
        rf"(?:^|\n)\s*({section_num_pattern})\s*:",
        # Format: Indented sections (may start with spaces)
        rf'(?:^|\n)\s+({section_num_pattern})\s*[:."]',
        # Format: "X.Y. Title" or "X.Y Title" at line start
        rf"(?:^|\n)\s*({section_num_pattern})(?:\.|\s+)",
    ]

    # Combine all patterns with OR
    combined_pattern = "|".join(patterns)

    # Use a set to collect unique matches
    section_set = set()

    # Find all matches
    for match in re.finditer(combined_pattern, cleaned_text):
        # Process each capturing group
        for group_idx in range(1, len(patterns) + 1):
            if group_idx <= len(match.groups()) and match.group(group_idx):
                # Clean up the section number (remove trailing dots and spaces)
                section_num = match.group(group_idx).rstrip(". ")
                section_set.add(section_num)
                break

    # Sort the section numbers numerically by each component
    def section_sort_key(section):
        return [int(n) for n in section.split(".")]

    sorted_sections = sorted(section_set, key=section_sort_key)

    return sorted_sections


def transform_span_tags(text):
    """
    Transforms span tags with id="page-X-Y" format to <page_X> format.

    Args:
        text (str): The input text containing span tags

    Returns:
        str: Text with transformed span tags
    """
    # This regex pattern matches <span id="page-NUMBER-NUMBER"></span> and captures the first number
    pattern = r'<span id="page-(\d+)-\d+"></span>'

    # Replace with <page_NUMBER>
    transformed_text = re.sub(pattern, r"<page_\1> ", text)

    return transformed_text


def retrieve_sections(
    filename: str, vectordb_endpoint, sections: Optional[List[str]] = None, text: Optional[str] = None
) -> List[str]:
    """
    Retrieve sections from a vector database in parallel.

    Args:
        filename: The name of the file to retrieve sections from
        vectordb_endpoint: The endpoint for the vector database
        sections: List of section identifiers to retrieve
        text: Text to extract section numbers from if sections is None

    Returns:
        List of contents from the retrieved sections
    """
    if sections is None and text is None:
        raise AssertionError("You should provide the text of the sections.")

    if sections is None:
        sections = extract_section_numbers(text)

    sections = [sections] if isinstance(sections, str) else sections

    # Define a worker function to process each section
    def process_section(section):
        try:
            content = get_raw_section(section=section, filename=filename, vectordb_endopoint=vectordb_endpoint)
            return [i["properties"]["text"] for i in content]
        except:
            return []

    # Use ThreadPoolExecutor to parallelize the section retrieval
    contents = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Submit all tasks and get future objects
        future_to_section = {executor.submit(process_section, section): section for section in sections}

        # Process results as they complete
        for future in concurrent.futures.as_completed(future_to_section):
            section_content = future.result()
            contents.extend(section_content)

    return list(set(contents))


def tokenize_and_chunk(tokenizer, text, max_tokens=512, overlap_tokens=256):
    """
    Tokenizes the text and splits it into overlapping chunks if it exceeds the max_tokens limit.

    :param text: The input text to tokenize and chunk.
    :param max_tokens: The maximum number of tokens allowed per chunk.
    :param overlap_tokens: The number of overlapping tokens between chunks.
    :param tokenizer_name: The name of the tokenizer to use (e.g., "bert-base-uncased").
    :return: A list of tokenized chunks.
    """

    # Tokenize the text
    tokens = tokenizer.encode(text)

    # Check if the text is already within the limit
    if len(tokens) <= max_tokens:
        return [text]

    # Split the text into overlapping chunks
    chunks = []
    start = 0

    while start < len(tokens):
        end = start + max_tokens
        chunk = tokens[start:end]
        chunks.append(tokenizer.decode(chunk))
        start += max_tokens - overlap_tokens  # Move the window forward, overlapping by `overlap_tokens`

    return chunks


def format_references(text):
    """
    A robust function that:
    1. Identifies all references in the format [number](page_number)
    2. Ensures each page consistently uses a single reference number
    3. Reorganizes reference numbers to be sequential (no gaps)
    4. Replaces each page_number with doc1.pdf#page-{page_number}

    If the function encounters any errors, it will fall back to simply
    replacing the page numbers with doc1.pdf#page-{page_number}.

    Args:
        text (str): The input text containing references

    Returns:
        str: Text with standardized, sequential references and replaced page links
    """
    try:
        # Regular expression to find references in the format [number](page_number)
        regex = r"\[(\d+)\]\((\d+)\)"

        # Step 1: Find all unique reference numbers
        all_refs = set()
        for match in re.finditer(regex, text):
            all_refs.add(int(match.group(1)))

        # Step 2: Map pages to all their reference numbers and count occurrences
        page_to_refs = defaultdict(list)
        for match in re.finditer(regex, text):
            ref_num = int(match.group(1))
            page_num = match.group(2)
            page_to_refs[page_num].append(ref_num)

        # Step 3: Determine the canonical reference number for each page
        # Use the most frequent reference, or the lowest if tied
        canonical_refs = {}
        for page_num, ref_nums in page_to_refs.items():
            # Count the frequency of each reference number
            ref_counts = {}
            for ref in ref_nums:
                ref_counts[ref] = ref_counts.get(ref, 0) + 1

            # Find the most frequent references
            max_count = max(ref_counts.values())
            most_common_refs = [ref for ref, count in ref_counts.items() if count == max_count]

            # Use the lowest number if there's a tie
            canonical_refs[page_num] = min(most_common_refs)

        # Step 4: Create a mapping of reference numbers to their new sequential numbers
        unique_canonical_refs = sorted(set(canonical_refs.values()))
        ref_to_new_ref = {old_ref: i + 1 for i, old_ref in enumerate(unique_canonical_refs)}

        # Step 5: Create a mapping of all original references to their new format
        replacements = {}
        for match in re.finditer(regex, text):
            original = match.group(0)
            ref_num = int(match.group(1))
            page_num = match.group(2)

            # Get the canonical reference number for this page
            canonical_ref = canonical_refs[page_num]

            # Get the new sequential reference number
            new_ref = ref_to_new_ref[canonical_ref]

            # Create the replacement with the new sequential reference
            replacement = f"[{new_ref}](doc1.pdf#page-{page_num})"
            replacements[original] = replacement

        # Step 6: Apply all replacements (from longest match to shortest to avoid partial matches)
        result = text
        for original, replacement in sorted(replacements.items(), key=lambda x: -len(x[0])):
            result = result.replace(original, replacement)

        # Generate a report of standardizations and sequencing made
        ref_changes = defaultdict(set)
        for page_num, ref_nums in page_to_refs.items():
            canonical_ref = canonical_refs[page_num]
            new_ref = ref_to_new_ref[canonical_ref]
            for ref in set(ref_nums):
                if ref != new_ref:
                    ref_changes[ref].add(new_ref)

        report_lines = []
        for old_ref, new_refs in sorted(ref_changes.items()):
            if len(new_refs) == 1:
                new_ref = list(new_refs)[0]
                report_lines.append(f"Reference [{old_ref}] changed to [{new_ref}]")

        return result, "\n".join(report_lines)

    except Exception as e:
        # Fallback: just replace page numbers with doc1.pdf#page-{page_number}
        fallback_result = re.sub(r"\[(\d+)\]\((\d+)\)", lambda m: f"[{m.group(1)}](doc1.pdf#page-{m.group(2)})", text)
        return fallback_result, f"Error during reference standardization: {str(e)}. Applied simple page replacement."
