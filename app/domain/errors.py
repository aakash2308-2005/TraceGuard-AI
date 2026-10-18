"""Domain error types mapped to HTTP responses in the API layer."""


class DomainError(Exception):
    """Base class for domain errors."""

    code = "domain_error"
    http_status = 400

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(DomainError):
    code = "not_found"
    http_status = 404


class AuthenticationError(DomainError):
    code = "authentication_error"
    http_status = 401


class AuthorizationError(DomainError):
    code = "authorization_error"
    http_status = 403


class ValidationError(DomainError):
    code = "validation_error"
    http_status = 422


class ConflictError(DomainError):
    code = "conflict"
    http_status = 409


class EvidenceIntegrityError(DomainError):
    code = "evidence_integrity_error"
    http_status = 422


class ExternalServiceError(DomainError):
    code = "external_service_error"
    http_status = 502
