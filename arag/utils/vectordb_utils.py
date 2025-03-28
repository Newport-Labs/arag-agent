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


def get_embeddings(text, model="nomic-embed-text", api_url="http://localhost:11434"):
    """
    Get embeddings for the provided text using Ollama API.

    Args:
        text (str): The text to generate embeddings for
        model (str): The model to use for embeddings, default is "nomic-embed-text"
        api_url (str): The base URL for Ollama API, default is "http://localhost:11434"

    Returns:
        list: The embedding vector if successful
        None: If the request failed
    """
    endpoint = f"{api_url}/api/embeddings"

    payload = {"model": model, "prompt": text}

    try:
        response = requests.post(endpoint, json=payload)
        response.raise_for_status()  # Raise an exception for HTTP errors

        result = response.json()

        # The Ollama API returns embeddings in the 'embedding' field
        if "embedding" in result:
            return result["embedding"]
        else:
            print(f"Unexpected response format: {result}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        return None