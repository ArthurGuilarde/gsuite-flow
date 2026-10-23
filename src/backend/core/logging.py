"""Configuração de Logging Estruturado e Contexto de Rastreamento (Request ID).

Suporta formato JSON para ambientes de produção/Docker e formato de console legível
para desenvolvimento local. Injeta automaticamente `request_id` via contextvars em
todos os registros emitidos pelo sistema.
"""

import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

from src.backend.core.config import settings

# Variável de contexto assíncrona para armazenar o Request ID da requisição ativa
_request_id_ctx_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Atributos nativos do LogRecord que devem ser ignorados ao extrair campos extras
_RESERVED_LOG_RECORD_ATTRS: set[str] = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
    "request_id",
}


def get_request_id() -> str | None:
    """Retorna o Request ID associado à requisição atual no contexto assíncrono."""
    return _request_id_ctx_var.get()


def set_request_id(request_id: str | None) -> Token[str | None]:
    """Define o Request ID para o contexto assíncrono atual."""
    return _request_id_ctx_var.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    """Restaura o contexto do Request ID ao estado anterior."""
    _request_id_ctx_var.reset(token)


class RequestIdFilter(logging.Filter):
    """Filtro de log que anexa `request_id` a qualquer LogRecord gerado."""

    def filter(self, record: logging.LogRecord) -> bool:
        req_id = get_request_id()
        record.request_id = req_id if req_id else "-"
        return True


class StructuredJsonFormatter(logging.Formatter):
    """Formatador que serializa registros de log como objetos JSON de linha única."""

    def format(self, record: logging.LogRecord) -> str:
        req_id = getattr(record, "request_id", None) or get_request_id()

        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if req_id and req_id != "-":
            payload["request_id"] = req_id

        # Extrai quaisquer atributos extras passados via extra={...}
        extra_keys = {
            k: v for k, v in record.__dict__.items() if k not in _RESERVED_LOG_RECORD_ATTRS and not k.startswith("_")
        }
        if extra_keys:
            payload.update(extra_keys)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        elif record.exc_text:
            payload["exception"] = record.exc_text

        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


class ConsoleFormatter(logging.Formatter):
    """Formatador legível para terminal de desenvolvimento."""

    DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] [%(request_id)s] %(message)s"
    DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
    ) -> None:
        super().__init__(
            fmt=fmt or self.DEFAULT_FORMAT,
            datefmt=datefmt or self.DEFAULT_DATEFMT,
        )


def setup_logging(
    log_level: str | None = None,
    log_format: str | None = None,
) -> None:
    """Configura os handlers de log para a aplicação e integração com Uvicorn.

    Args:
        log_level: Nível de log (DEBUG, INFO, WARNING, ERROR). Padrão via settings.
        log_format: Formato dos logs ('json' ou 'console'). Padrão via settings.
    """
    level_name = (log_level or settings.LOG_LEVEL).upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt_type = (log_format or settings.LOG_FORMAT).lower()

    # Cria o formatador apropriado
    formatter: logging.Formatter = StructuredJsonFormatter() if fmt_type == "json" else ConsoleFormatter()

    # Cria ou reutiliza o handler padrão de stdout
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.addFilter(RequestIdFilter())
    stream_handler.setFormatter(formatter)

    # Configura o logger raiz
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove handlers antigos para evitar duplicação em reload/reconfiguração
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    root_logger.addHandler(stream_handler)

    # Garante que os loggers internos do projeto herdem o nível e propagação
    for logger_name in ("src", "src.backend"):
        app_logger = logging.getLogger(logger_name)
        app_logger.setLevel(level)
        app_logger.propagate = True
