import os
import re
import urllib.parse
from typing import List, Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .vectordb_utils import _get_chunks, embed_text


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
    # Convert PATH_PLACE_HOLDER to PATH_PLACEHOLDER
    text = text.replace("PATH_PLACE_HOLDER", "PATH_PLACEHOLDER")

    # Convert IMG_PLACE_HOLDER to IMG_PLACEHOLDER
    text = text.replace("IMG_PLACE_HOLDER", "IMG_PLACEHOLDER")

    # Convert /image/s/ to /images/
    text = text.replace("/image/s/", "/images/")

    return text
