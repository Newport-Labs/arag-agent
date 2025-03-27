from typing import Optional


def client_message(
    user_message: str, openai_client, model: str, system_message: Optional[str] = None, temperature: float = 0.6
) -> str:
    messages = [{"role": "system", "content": system_message}] if system_message else []
    messages.append({"role": "user", "content": user_message})

    response = openai_client.chat.completions.create(model=model, messages=messages, temperature=temperature)

    return response.choices[0].message.content, response.usage.json()


def client_sturctured_message(
    user_message: str,
    openai_client,
    model: str,
    structured_output_schema,
    system_message: Optional[str] = None,
    temperature: float = 0.6,
) -> str:
    messages = [{"role": "system", "content": system_message}] if system_message else []
    messages.append({"role": "user", "content": user_message})

    response = openai_client.beta.chat.completions.parse(
        model=model, messages=messages, response_format=structured_output_schema, temperature=temperature
    )

    return response.choices[0].message.parsed, response.usage.json()