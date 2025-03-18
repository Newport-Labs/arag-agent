from typing import Optional

import requests


def _get_chunks(vectordb_endopoint: str, query: str, num_chunks: int = 3, section: Optional[str] = None):

    url = vectordb_endopoint

    if section:
        payload = {"query": query, "num_returns": num_chunks, "section": str(section)}
    else:
        payload = {"query": query, "num_returns": num_chunks}

    response = requests.get(url, json=payload)

    return response.json()


def embed_text(vectordb_endopoint: str, text: str):

    url = vectordb_endopoint
    headers = {"Content-Type": "application/json"}
    data = {"text": text}

    response = requests.post(url, json=data, headers=headers)

    return response.json()
