"""Transporte JSON compartilhado pelos adaptadores, sem regras de jogo."""

import json
from openai import (
    APIConnectionError, APIStatusError, AuthenticationError, NotFoundError,
    OpenAI, RateLimitError,
)

DEFAULT_MODEL = "gpt-5.6-luna"


class OpenAIRequestError(ValueError):
    pass


def request_json(client: OpenAI, *, model: str, instructions: str, payload: dict,
                 schema: dict, name: str, max_output_tokens: int = 1000) -> str:
    try:
        response = client.responses.create(
            model=model, reasoning={"effort": "low"}, max_output_tokens=max_output_tokens,
            instructions=instructions, input=json.dumps(payload, ensure_ascii=False),
            text={"format": {"type": "json_schema", "name": name,
                             "strict": True, "schema": schema}},
            store=False,
        )
    except AuthenticationError as error:
        raise OpenAIRequestError("Chave da OpenAI inválida. Confira OPENAI_API_KEY.") from error
    except RateLimitError as error:
        raise OpenAIRequestError("A OpenAI informou limite de uso ou créditos. Tente mais tarde.") from error
    except APIConnectionError as error:
        raise OpenAIRequestError("Não foi possível conectar à OpenAI no prazo. Tente novamente.") from error
    except NotFoundError as error:
        raise OpenAIRequestError("Modelo indisponível. Confira TRAMA_OPENAI_MODEL e o acesso da conta.") from error
    except APIStatusError as error:
        raise OpenAIRequestError(f"A OpenAI recusou a chamada (HTTP {error.status_code}).") from error
    if response.status != "completed":
        raise OpenAIRequestError("A resposta da OpenAI ficou incompleta. Tente um pedido mais curto.")
    if any(
        getattr(part, "type", None) == "refusal"
        for item in response.output
        for part in getattr(item, "content", [])
    ):
        raise OpenAIRequestError("A OpenAI recusou esta solicitação.")
    return response.output_text
