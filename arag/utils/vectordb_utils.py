from typing import Optional

import requests


def _get_chunks(vectordb_endopoint: str, query: str, filename: str, num_chunks: int = 3):

    url = f"{vectordb_endopoint}/query"
    payload = {"query": query, "num_returns": num_chunks, "filename": filename}

    response = requests.get(url, json=payload)

    return response.json()


def _get_metadata(vectordb_endopoint):

    url = f"{vectordb_endopoint}/metadata"

    response = requests.get(url)

    return response.json()


def get_summaries(vectordb_endopoint: str):
    """
    Get summaries from the API.

    Args:
        api_endpoint (str): The URL endpoint for summaries

    Returns:
        dict: The JSON response containing summaries
    """
    url = f"{vectordb_endopoint}/api/summaries"

    response = requests.get(url)

    return response.json()


def get_file_toc(vectordb_endopoint: str, filename: str):
    """
    Get table of contents for a specific file.

    Args:
        api_endpoint (str): The base URL of the API
        filename (str): The name of the file to get TOC for

    Returns:
        dict: The JSON response containing the file's table of contents
    """
    url = f"{vectordb_endopoint}/api/file_toc"

    params = {"filename": filename}

    response = requests.get(url, params=params)

    return response.json()


def get_raw_section(vectordb_endopoint, section, filename):
    """Get raw section content from the vector database.

    Args:
        vectordb_endopoint: URL of the vector database API
        section: Section number/id to retrieve
        filename: PDF filename

    Returns:
        Dictionary containing section data or error message
    """
    url = f"{vectordb_endopoint}/api/section"

    # Use params instead of json for GET requests
    params = {"section": section, "filename": filename}

    response = requests.get(url, params=params)

    # Check if the request was successful
    if response.status_code == 200:
        return response.json()
    else:
        # Handle error case
        try:
            return response.json()  # Try to get error message
        except:
            return {"error": f"Failed to retrieve section {section}. Status code: {response.status_code}"}