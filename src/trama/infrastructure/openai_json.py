"""Transporte JSON compartilhado pelos adaptadores, sem regras de jogo."""

import json
import logging
from time import perf_counter
from openai import (
    APIConnectionError, APIStatusError, AuthenticationError, NotFoundError,
    OpenAI, RateLimitError,
)
from trama.observability import current_context, log_context, new_id
from trama.infrastructure.openai_config import DEFAULT_MODEL, DEFAULT_RESPONSE
from trama.infrastructure.call_budget import CallBudget

logger = logging.getLogger(__name__)

class OpenAIRequestError(ValueError):
    pass


def request_json(client: OpenAI, *, model: str, instructions: str, payload: dict,
                 schema: dict, name: str, max_output_tokens: int = DEFAULT_RESPONSE.max_output_tokens,
                 reasoning_effort: str = DEFAULT_RESPONSE.reasoning_effort,
                 budget: CallBudget | None = None) -> str:
    with log_context(ai_call_id=current_context().get("ai_call_id") or new_id()):
        started = perf_counter()
        logger.info("ai.request_started", extra={"data": {"model": model, "task": name,
                    "max_output_tokens": max_output_tokens, "reasoning_effort": reasoning_effort}})
        parameters = {"model": model, "reasoning": {"effort": reasoning_effort}, "max_output_tokens": max_output_tokens,
                      "instructions": instructions, "input": json.dumps(payload, ensure_ascii=False),
                      "text": {"format": {"type": "json_schema", "name": name,
                                          "strict": True, "schema": schema}}, "store": False}
        logger.debug("ai.request_payload", extra={"data": {"request": parameters}})
        try:
            if budget is not None:
                budget.reserve()
            response = _create_response(client, parameters)
            logger.info("ai.response_received", extra={"data": {
                "model": model, "task": name, "duration_ms": round((perf_counter() - started) * 1000, 3),
                "status": response.status, "response_id": _string(getattr(response, "id", None)),
                "response_model": _string(getattr(response, "model", None)),
                "provider_request_id": _string(getattr(response, "_request_id", None)),
                "usage": _usage(getattr(response, "usage", None))}})
            logger.debug("ai.response_payload", extra={"data": {"output_text": response.output_text}})
            if response.status != "completed":
                raise OpenAIRequestError("A resposta da OpenAI ficou incompleta. Tente um pedido mais curto.")
            if any(getattr(part, "type", None) == "refusal"
                   for item in response.output for part in getattr(item, "content", [])):
                raise OpenAIRequestError("A OpenAI recusou esta solicitação.")
            return response.output_text
        except Exception:
            logger.exception("ai.request_failed", extra={"data": {"model": model, "task": name,
                             "duration_ms": round((perf_counter() - started) * 1000, 3)}})
            raise


def _string(value):
    return value if isinstance(value, str) else None


def _usage(usage) -> dict:
    def count(value):
        return value if type(value) is int and value >= 0 else None

    # Campos do SDK instalado. Ausência de usage não significa custo zero.
    inputs = getattr(usage, "input_tokens_details", None)
    outputs = getattr(usage, "output_tokens_details", None)
    return {"input_tokens": count(getattr(usage, "input_tokens", None)),
            "output_tokens": count(getattr(usage, "output_tokens", None)),
            "total_tokens": count(getattr(usage, "total_tokens", None)),
            "cached_input_tokens": count(getattr(inputs, "cached_tokens", None)),
            "cache_write_tokens": count(getattr(inputs, "cache_write_tokens", None)),
            "reasoning_tokens": count(getattr(outputs, "reasoning_tokens", None))}


def _create_response(client, parameters):
    try:
        return client.responses.create(**parameters)
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
