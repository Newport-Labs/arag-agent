import os
import re
import urllib.parse
from typing import List, Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .vectordb_utils import _get_chunks, embed_text


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
    lines = markdown_text.split('\n')
    in_table = False
    current_table = []
    result = []
    
    # Process the text line by line to identify tables
    for line in lines:
        # Check if the line looks like part of a table (contains pipe character)
        # Skip code blocks (lines starting with ```)
        if '|' in line and not line.strip().startswith('```'):
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
    
    return '\n'.join(result)


def convert_references(text):
    # Define the regex pattern to match references like [Manual Name, Page 165, Section 5.7]
    pattern = r'\[(.*?), Page (\d+)(?:, Section [\d\.]+)?\]'
    
    # Find all matches in the text
    matches = re.findall(pattern, text)
    
    # Create a dictionary to store unique references and their replacement numbers
    unique_refs = {}
    ref_counter = 1
    
    # First pass: identify unique references and assign numbers
    for match in matches:
        manual_name = match[0]
        page_number = match[1]
        full_match = f"[{manual_name}, Page {page_number}"
        if ", Section" in text[text.find(full_match):text.find(full_match) + 50]:
            # Find the section part if it exists
            section_part = re.search(r'(, Section [\d\.]+)', text[text.find(full_match):text.find(full_match) + 50])
            if section_part:
                full_match += section_part.group(1)
        full_match += "]"
        
        if full_match not in unique_refs:
            unique_refs[full_match] = {
                'number': ref_counter,
                'page': page_number
            }
            ref_counter += 1
    
    # Second pass: replace references in the text
    result_text = text
    for ref, ref_data in unique_refs.items():
        replacement = f"[{ref_data['number']}](PATH_PLACEHOLDER#page={ref_data['page']})"
        result_text = result_text.replace(ref, replacement)
    
    return result_text


def fix_table(table_lines):
    """Fix a single Markdown table."""
    # Remove any empty lines and clean up each line
    rows = [row.strip() for row in table_lines if row.strip()]
    if not rows:
        return table_lines
    
    # Make sure all rows have pipes at start and end
    for i in range(len(rows)):
        if not rows[i].startswith('|'):
            rows[i] = '| ' + rows[i]
        if not rows[i].endswith('|'):
            rows[i] = rows[i] + ' |'
    
    # Find the maximum number of columns in any row
    max_cols = 0
    for row in rows:
        cols = row.strip('|').split('|')
        max_cols = max(max_cols, len(cols))
    
    # Check for a separator row (contains dashes)
    has_separator = False
    separator_idx = -1
    
    for i, row in enumerate(rows):
        if i > 0 and '-' in row and re.search(r'\|\s*[:]*[-]+[:]*\s*\|', row):
            has_separator = True
            separator_idx = i
            break
    
    # If no separator row found and we have multiple rows, add one after the first row
    if not has_separator and len(rows) > 1:
        separator = '| ' + ' | '.join(['---'] * max_cols) + ' |'
        rows.insert(1, separator)
        separator_idx = 1
    
    # Process each row to ensure consistent columns and formatting
    fixed_rows = []
    
    for i, row in enumerate(rows):
        cols = row.strip('|').split('|')
        cols = [col.strip() for col in cols]
        
        # Special handling for the separator row
        if i == separator_idx:
            separators = []
            for j in range(max_cols):
                if j < len(cols) and re.match(r'^:?-+:?$', cols[j]):
                    # Preserve alignment markers
                    separators.append(cols[j])
                else:
                    # Default separator
                    separators.append('---')

            fixed_rows.append('| ' + ' | '.join(separators) + ' |')
        else:
            # For data rows, ensure consistent column count
            while len(cols) < max_cols:
                cols.append('')  # Add empty cells if needed
            cols = cols[:max_cols]  # Truncate if too many

            fixed_rows.append('| ' + ' | '.join(cols) + ' |')

    return fixed_rows


def deduplicate_by_similarity(chunks, similarity_threshold=0.85, embeddings=None, paths=None):
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

    if embeddings is None:
        # Get embeddings for each text
        embeddings = []

        for chunk in chunks:
            embedding = embed_text(chunk)["vector"]
            embeddings.append(embedding)

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
        [path for i, path in enumerate(paths) if to_keep[i]],
        [embedding for i, embedding in enumerate(embeddings) if to_keep[i]],
    )


def align_text_images(text):
    # Regular expression to match all images with IMG_PLACEHOLDER
    image_pattern = r"!\[([^\]]*)\]\((IMG_PLACEHOLDER[^)]+)\)"

    def replace_with_centered_image(match):
        image_path = match.group(2)
        # Just center the image without adding descriptions
        return f'<div style="text-align: center;">' f'<img src="{image_path}" alt=""/>' f"</div>"

    # Replace all image matches with centered images
    result = re.sub(image_pattern, replace_with_centered_image, text)

    return result


def perform_similarity_search(
    vectordb_endopoint: str, queries: List[str], threshold, section: Optional[str] = None, num_chunks: int = 3
) -> List[str]:
    chunks = []
    paths = []
    embeddings = []

    for query in queries:
        chunk = _get_chunks(vectordb_endopoint, query, num_chunks, section=section)

        for c in chunk:
            pdf_path = (
                "Manual name: "
                + c["properties"]["pdf_file"]
                + "\n"
                + "PDF path: "
                + os.path.join("./data", urllib.parse.quote(c["properties"]["pdf_file"]) + ".pdf")
                + "\n\n"
            )
            chunks.append(c["properties"]["text"])
            paths.append(pdf_path)
            embeddings.append(c["vector"]["text_vector"])

    # Dedup exact chunks
    chunks, paths, embeddings = deduplicate_by_similarity(
        chunks=chunks, paths=paths, embeddings=embeddings, similarity_threshold=threshold
    )

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


def fix_path_formatting(text):
    # Replace incorrect closing brackets with parentheses for path references
    pattern1 = r"(\[\d+\]\(PATH_PLACEHOLDER#page=\d+)\]"
    text = re.sub(pattern1, r"\1)", text)
    text = text.replace("<br>", "")

    # Convert PATH_PLACE_HOLDER to PATH_PLACEHOLDER
    text = text.replace("PATH_PLACE_HOLDER", "PATH_PLACEHOLDER")

    # Convert IMG_PLACE_HOLDER to IMG_PLACEHOLDER
    text = text.replace("IMG_PLACE_HOLDER", "IMG_PLACEHOLDER")

    # Convert /image/s/ to /images/
    text = text.replace("/image/s/", "/images/")

    return text
