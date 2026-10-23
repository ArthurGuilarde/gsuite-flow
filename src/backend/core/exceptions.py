"""Exceções de domínio da aplicação.

Services lançam estas exceções (sem conhecer HTTP). Um handler global em `main.py`
as converte em respostas JSON com o status HTTP correspondente.
"""


class DomainError(Exception):
    """Erro de domínio base. Subclasses definem o status HTTP semântico."""

    status_code: int = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationError(DomainError):
    status_code = 400


class AuthenticationError(DomainError):
    status_code = 401


class PermissionDeniedError(DomainError):
    status_code = 403


class NotFoundError(DomainError):
    status_code = 404


class ConflictError(DomainError):
    status_code = 409
