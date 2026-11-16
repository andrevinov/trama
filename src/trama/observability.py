"""Destino e formato dos logs; os produtores usam somente logging da stdlib.

Contrato: mensagem = nome estável do evento; extra={"data": {...}} = detalhes.
Contexto de correlação fica na aplicação, sem dependência das regras neste módulo.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
import json
import logging
from logging.handlers import RotatingFileHandler
from math import isfinite
from pathlib import Path
import re
import sys
from uuid import uuid4

_context: ContextVar[dict] = ContextVar("trama_log_context", default={})
_IDS = ("session_id", "interaction_id", "operation_id", "ai_call_id")
_SECRET_KEYS = {"authorization", "api_key", "openai_api_key", "access_token", "refresh_token", "password"}
_SECRETS = re.compile(r"\bsk-[A-Za-z0-9_-]+|\bBearer\s+[A-Za-z0-9._~+/-]+=*", re.IGNORECASE)


def new_id() -> str:
    return uuid4().hex


def current_context() -> dict:
    return _context.get().copy()


@contextmanager
def log_context(**identifiers):
    """Escopo restaurável, isolado por tarefa/thread; aceita só identificadores."""
    if set(identifiers) - set(_IDS) or any(value is not None and not isinstance(value, str)
                                          for value in identifiers.values()):
        raise ValueError("Contexto de log inválido.")
    token = _context.set({**_context.get(), **identifiers})
    try:
        yield
    finally:
        _context.reset(token)


def _clean(value):
    if is_dataclass(value) and not isinstance(value, type):
        return _clean(asdict(value))
    if isinstance(value, dict):
        return {str(key): "[REDACTED]" if str(key).lower() in _SECRET_KEYS else _clean(item)
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [_clean(item) for item in sorted(value, key=repr)]
    if isinstance(value, str):
        return _SECRETS.sub("[REDACTED]", value)
    if isinstance(value, Decimal):
        return str(value)  # Mantém a precisão das distâncias.
    if isinstance(value, Path):
        return _clean(str(value))
    if isinstance(value, float) and not isfinite(value):
        return str(value)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return f"<{type(value).__name__}>"  # Nunca serializa clientes/headers/objetos arbitrários.


class ContextFilter(logging.Filter):
    def __init__(self, session_id: str | None = None) -> None:
        super().__init__()
        self.session_id = session_id

    def filter(self, record: logging.LogRecord) -> bool:
        context = {"session_id": self.session_id, **_context.get()}
        for name in _IDS:
            setattr(record, name, context.get(name))
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        error = None
        if record.exc_info and record.exc_info[1] is not None:
            exception = record.exc_info[1]
            causes = []
            visited = {id(exception)}
            cause = exception.__cause__ or (None if exception.__suppress_context__ else exception.__context__)
            while cause is not None and id(cause) not in visited:
                visited.add(id(cause))
                causes.append({"type": type(cause).__name__, "message": str(cause)})
                cause = cause.__cause__ or (None if cause.__suppress_context__ else cause.__context__)
            error = {"type": type(exception).__name__, "message": str(exception),
                     "causes": causes, "traceback": self.formatException(record.exc_info)}
        result = {"schema_version": 1,
                  "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
                  "level": record.levelname, "component": record.name, "event": record.getMessage(),
                  **{name: getattr(record, name, None) for name in _IDS},
                  "data": getattr(record, "data", {}), "error": error}
        return json.dumps(_clean(result), ensure_ascii=False, allow_nan=False)


def configure_logging(*, level: str = "INFO", log_file: Path | str | None = None,
                      stream=None, session_id: str | None = None,
                      max_bytes: int = 5_000_000, backup_count: int = 3) -> str:
    """Configura apenas trama.*, com JSONL no terminal e arquivo rotativo opcional.

    Retorna o id da execução. Reconfigurar substitui só os handlers criados aqui;
    não configura OpenAI, httpx, logger raiz ou qualquer outra biblioteca.
    """
    level = level.upper()
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError("Nível de log inválido.")
    if max_bytes <= 0 or backup_count < 1:
        raise ValueError("Rotação de logs inválida.")
    session_id = session_id or new_id()
    handlers = [logging.StreamHandler(sys.stderr if stream is None else stream)]
    if log_file is not None:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"))
    close_logging()
    logger = logging.getLogger("trama")
    logger.setLevel(level)
    logger.propagate = False
    for handler in handlers:
        handler._trama_owned = True
        handler.setLevel(level)
        handler.addFilter(ContextFilter(session_id))
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    return session_id


def close_logging() -> None:
    logger = logging.getLogger("trama")
    for handler in logger.handlers[:]:
        if getattr(handler, "_trama_owned", False):
            logger.removeHandler(handler)
            handler.close()
