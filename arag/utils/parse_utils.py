import concurrent.futures
import re
from collections import defaultdict


def extract_page_numbers(text):
    # Pattern for standard "Page X" format
    single_pattern = r"[Pp]age\s+(\d+)"

    # Pattern for comma or space-separated page numbers (e.g., "Page 22, 23, 24" or "Pages 22-24")
    multi_pattern = r"[Pp]ages?\s+(\d+)(?:[\s,]+(\d+))*"
    range_pattern = r"[Pp]ages?\s+(\d+)[- ](\d+)"

    # Find all standard matches
    single_matches = re.findall(single_pattern, text)

    # Find potential multi-page references
    multi_matches = re.findall(multi_pattern, text)

    # Find range references
    range_matches = re.findall(range_pattern, text)

    # Process the results
    page_numbers = single_matches.copy()

    # Add multi-page references (this will catch sequences like "Page 22, 23, 24")
    for match in multi_matches:
        for page in match:
            if page and page not in page_numbers:
                page_numbers.append(page)

    # Process page ranges (like "Pages 22-24")
    for start, end in range_matches:
        start_num = int(start)
        end_num = int(end)
        for page_num in range(start_num, end_num + 1):
            page_str = str(page_num)
            if page_str not in page_numbers:
                page_numbers.append(page_str)

    # Additional pattern for lists in brackets like "[Manual Name, Page 22, 23, 24]"
    bracket_pattern = r"\[[^\]]*[Pp]age\s+(\d+)(?:[,\s]+(\d+))*\]"
    bracket_matches = re.findall(bracket_pattern, text)

    # Process bracket matches
    for match in bracket_matches:
        for page in match:
            if page and page not in page_numbers:
                page_numbers.append(page)

    # Final cleanup - remove any empty strings and ensure unique values
    page_numbers = [page for page in page_numbers if page]

    return list(set(page_numbers))


def extract_references_with_context(text):
    # Split the text into sentences and potential sentence fragments
    # This avoids the need for variable-width lookbehinds
    splits = re.split(r"(?<=\.)\s+|(?<=\n)", text)

    results = []

    for split in splits:
        # Find all references in this segment
        references = re.findall(r"\[(\d+)\]", split)

        if references:
            # If there are references, add this segment to results
            results.append((split.strip(), references))

    return results


def order_dict_by_keys(input_dict) -> dict:
    """
    Orders a dictionary by its keys

    Args:
        input_dict (dict): Dictionary to be ordered

    Returns:
        dict: A new dictionary ordered by keys
    """
    return {k: input_dict[k] for k in sorted(input_dict.keys())}


def process_content_references(answer, knowledge, fact_checker) -> str:
    results = extract_references_with_context(answer)

    # Get all unique references in the answer
    all_refs = set([ref[0] for _, ref in results])

    # Step 1: Group content by reference
    references = defaultdict(list)

    def group_by_reference(item):
        content, ref = item
        references[ref[0]].append(content)

    # Process in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        list(executor.map(group_by_reference, results))

    updated_references = {}

    for ref, content in references.items():
        updated_references[ref] = "\n\n".join(content[1:3])

    references = updated_references

    # Strip content
    for ref in references:
        references[ref] = references[ref].strip()

    # Step 2: Find matching pages for each reference
    ref_pages = {}
    used_pages = set()  # Track which pages have already been used

    # Make a copy of knowledge to be able to remove chunks as they're processed
    remaining_chunks = knowledge.copy()

    # First check for existing references in the answer
    existing_ref_pattern = r"\[(\d+)\]\(PATH_PLACEHOLDER#page=(\d+(?:-\d+)?)\)"
    existing_refs = re.findall(existing_ref_pattern, answer)

    # Add existing references to ref_pages and mark pages as used
    for ref_num, page_range in existing_refs:
        ref_num = int(ref_num)
        if "-" in page_range:
            start, end = map(int, page_range.split("-"))
            pages = list(range(start, end + 1))
        else:
            pages = [int(page_range)]

        ref_pages[ref_num] = pages
        for page in pages:
            used_pages.add(page)

    # Process references that don't have pages yet
    refs_to_process = sorted([(int(ref), content) for ref, content in references.items() if int(ref) not in ref_pages])

    # Process each reference sequentially
    for reference, content in refs_to_process:
        matching_pages = []
        chunks_to_remove = []

        # First, check all remaining chunks to find matches
        for chunk_idx, chunk in enumerate(remaining_chunks):
            response = fact_checker.perform_action(query=content, context=chunk)
            if response == "yes":
                pages = extract_page_numbers(chunk)
                pages = [int(p) for p in pages if p]

                # Filter out pages already used
                available_pages = [p for p in pages if p not in used_pages]

                if available_pages:
                    # Add available pages to our matches
                    matching_pages.extend(available_pages)
                    # Mark these pages as used
                    for page in available_pages:
                        used_pages.add(page)
                    # Mark this chunk for removal
                    chunks_to_remove.append(chunk_idx)
                    # Once we find a match with available pages, we can stop
                    break

        # Remove the used chunks (starting from the end to avoid index shifting)
        for idx in sorted(chunks_to_remove, reverse=True):
            remaining_chunks.pop(idx)

        # Store the matching pages for this reference
        if matching_pages:
            ref_pages[reference] = matching_pages

    # Step 3: Order dictionary and format answer
    ref_pages = {k: ref_pages[k] for k in sorted(ref_pages.keys())}

    # Create a list of all replacements to make
    replacements = []

    for idx, (reference, pages) in enumerate(ref_pages.items()):
        if pages and len(pages) == 1:
            if reference == idx + 1:
                old_ref = f"[{reference}]"
                new_ref = f"[{reference}](PATH_PLACEHOLDER#page={pages[0]})"
            else:
                old_ref = f"[{idx + 1}]"
                new_ref = f"[{idx + 1}](PATH_PLACEHOLDER#page={pages[0]})"

            replacements.append((old_ref, new_ref))

        elif pages and len(pages) > 1:
            min_page = min(pages)
            max_page = max(pages)

            if reference == idx + 1:
                old_ref = f"[{reference}]"
                new_ref = f"[{reference}](PATH_PLACEHOLDER#page={min_page}-{max_page})"
            else:
                old_ref = f"[{idx + 1}]"
                new_ref = f"[{idx + 1}](PATH_PLACEHOLDER#page={min_page}-{max_page})"

            replacements.append((old_ref, new_ref))

    # Apply all replacements
    for old_ref, new_ref in replacements:
        # Only replace if the exact pattern [X] is found (not already replaced)
        pattern = re.escape(old_ref)
        answer = re.sub(pattern + r"(?!\()", new_ref, answer)

    # Check if all references in the original answer were replaced
    for ref in all_refs:
        ref_pattern = f"\\[{ref}\\](?!\\()"
        if re.search(ref_pattern, answer):
            print(f"Warning: Reference [{ref}] was not replaced in the answer.")

    return answer


def extract_image_references(text) -> str:
    """
    Extracts Markdown image references from text.

    Args:
        text (str): The text to extract image references from

    Returns:
        list: A list of extracted image references
    """
    # Match pattern: ![Image Description]
    # The regex pattern matches:
    # - Literal exclamation mark and opening square bracket
    # - Any characters inside the square brackets (non-greedy)
    # - Closing square bracket
    pattern = r"!\[([^\]]+)\]"

    # Find all matches in the text
    matches = re.findall(pattern, text)

    # Reconstruct the full image reference format
    image_references = [f"![{match}]" for match in matches]

    return image_references


def process_images_parallel(answer, knowledge, image_extractor) -> str:
    img_list = extract_image_references(answer)
    output_image = {}

    def process_image(image_text):
        # For each image, search through knowledge chunks in parallel
        def check_chunk(chunk):
            if "![" not in chunk:
                return None

            reference_present, page, type, type_number = image_extractor.perform_action(query=image_text, context=chunk)
            if reference_present:
                image = f"IMG_PLACEHOLDER/_page_{page}_{type}_{type_number}.jpeg"
                return image
            return None

        # Process knowledge chunks in parallel for each image
        with concurrent.futures.ThreadPoolExecutor() as chunk_executor:
            for result in chunk_executor.map(check_chunk, knowledge):
                if result is not None:
                    return image_text, result
        return image_text, None

    # Process all images in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for image_text, image_path in executor.map(process_image, img_list):
            if image_path is not None:
                output_image[image_text] = image_path

    # Create a list of replacements to make
    replacements = []
    for key, img_path in output_image.items():
        replacements.append((key, f"{key}({img_path})"))

    # Apply replacements using regex to avoid duplicates
    for key, replacement in replacements:
        # Only replace if the exact key is found (not already replaced)
        pattern = re.escape(key) + r"(?!\()"
        answer = re.sub(pattern, replacement, answer)

    return answer