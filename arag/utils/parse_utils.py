import concurrent.futures
import re
from collections import defaultdict


def extract_page_numbers(text):
    # Define the regex pattern to find page numbers
    pattern = r"[Pp]age\s+(\d+)"

    # Find all matches in the text
    matches = re.findall(pattern, text)

    # Return the list of page numbers
    return matches


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

    # Step 1: Group content by reference
    references = defaultdict(str)

    def group_by_reference(item):
        content, ref = item
        references[ref[0]] += content + "\n\n"

    # Process in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        list(executor.map(group_by_reference, results))

    # Strip content
    for ref in references:
        references[ref] = references[ref].strip()

    # Step 2: Find matching pages for each reference
    ref_pages = {}

    def find_matching_pages(ref_content_pair):
        reference, content = ref_content_pair

        # Search chunks in parallel
        def check_chunk(chunk):
            response = fact_checker.perform_action(query=content, context=chunk)
            if response == "yes":
                page = extract_page_numbers(chunk)
                return page
            return None

        with concurrent.futures.ThreadPoolExecutor() as chunk_executor:
            # Process chunks until we find a match
            for page in chunk_executor.map(check_chunk, knowledge):
                if page is not None:
                    return reference, [int(p) for p in page]

        return reference, None

    # Process all references in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for reference, pages in executor.map(find_matching_pages, references.items()):
            if pages is not None:
                ref_pages[reference] = pages

    # Step 3: Order dictionary and format answer
    ref_pages = order_dict_by_keys(ref_pages)

    # Create a list of all replacements to make
    replacements = []

    for idx, (reference, page) in enumerate(ref_pages.items()):
        if len(page) == 1:
            if reference == idx + 1:
                old_ref = f"[{reference}]"
                new_ref = f"[{reference}](PATH_PLACEHOLDER#page={page[0]})"
            else:
                old_ref = f"[{idx + 1}]"
                new_ref = f"[{idx + 1}](PATH_PLACEHOLDER#page={page[0]})"
        elif len(page) > 1:
            min_page = min(page)
            max_page = max(page)
            if reference == idx + 1:
                old_ref = f"[{reference}]"
                new_ref = f"[{reference}](PATH_PLACEHOLDER#page={min_page}-{max_page})"
            else:
                old_ref = f"[{idx + 1}]"
                new_ref = f"[{idx + 1}](PATH_PLACEHOLDER#page={min_page}-{max_page})"

        replacements.append((old_ref, new_ref))

    for old_ref, new_ref in replacements:
        # Only replace if the exact pattern [X] is found (not already replaced)
        pattern = re.escape(old_ref)
        answer = re.sub(pattern + r"(?!\()", new_ref, answer)

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

            reference_present, image = image_extractor.perform_action(query=image_text, context=chunk)
            if reference_present:
                # Clean the image path
                clean_image = image.replace("(", "").replace(")", "").replace("images/", "IMG_PLACEHOLDER/")
                return clean_image
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