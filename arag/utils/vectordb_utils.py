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