"""
Error code registry for stable error-code contract between backend and frontend.

Each code maps to a stable identifier that the frontend resolves through i18n.
Format: <domain>.<error_type> (e.g., auth.invalid_credentials, leads.not_found)
"""


class ErrorCodes:
    """Stable error code constants."""

    # Generic / Infrastructure
    INTERNAL_SERVER_ERROR = "internal_server_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    VALIDATION_ERROR = "validation.invalid_payload"
    FEATURE_NOT_READY = "feature.not_ready"

    # Authentication & Authorization
    INVALID_CREDENTIALS = "auth.invalid_credentials"
    UNAUTHORIZED = "auth.unauthorized"
    FORBIDDEN = "auth.forbidden"
    TOKEN_EXPIRED = "auth.token_expired"
    INVALID_TOKEN = "auth.invalid_token"

    # Workspace & Users
    WORKSPACE_NOT_FOUND = "workspace.not_found"
    WORKSPACE_CONFLICT = "workspace.conflict"
    USER_NOT_FOUND = "user.not_found"
    USER_ALREADY_EXISTS = "user.already_exists"
    USER_INACTIVE = "user.inactive"

    # Leads
    LEAD_NOT_FOUND = "leads.not_found"
    LEAD_CONFLICT = "leads.conflict"
    INVALID_LEAD_STATUS = "leads.invalid_status"
    BULK_OPERATION_PARTIAL = "leads.bulk_operation_partial"

    # Search Jobs & Requests
    SEARCH_JOB_NOT_FOUND = "search_jobs.not_found"
    SEARCH_JOB_IN_PROGRESS = "search_jobs.in_progress"
    SEARCH_JOB_CONFLICT = "search_jobs.conflict"

    # Providers & External Services
    PROVIDER_UNAVAILABLE = "provider.unavailable"
    PROVIDER_ERROR = "provider.error"
    PROVIDER_QUOTA_EXCEEDED = "provider.quota_exceeded"
    PROVIDER_INVALID_CREDENTIALS = "provider.invalid_credentials"

    # AI Analysis
    AI_ANALYSIS_NOT_FOUND = "ai_analysis.not_found"
    AI_ANALYSIS_GENERATION_FAILED = "ai_analysis.generation_failed"
    AI_ANALYSIS_PROVIDER_UNAVAILABLE = "ai_analysis.provider_unavailable"

    # Assistant / Chat
    ASSISTANT_NOT_FOUND = "assistant.not_found"
    ASSISTANT_CONVERSATION_NOT_FOUND = "assistant.conversation_not_found"
    ASSISTANT_MESSAGE_NOT_FOUND = "assistant.message_not_found"
    ASSISTANT_GENERATION_FAILED = "assistant.generation_failed"

    # Billing
    BILLING_ACCOUNT_NOT_FOUND = "billing.account_not_found"
    BILLING_SUBSCRIPTION_NOT_FOUND = "billing.subscription_not_found"
    BILLING_INVOICE_NOT_FOUND = "billing.invoice_not_found"
    BILLING_PAYMENT_FAILED = "billing.payment_failed"
    BILLING_INSUFFICIENT_CREDITS = "billing.insufficient_credits"

    # Admin / Audit
    ADMIN_AUDIT_LOG_NOT_FOUND = "admin.audit_log_not_found"
    ADMIN_OPERATION_FORBIDDEN = "admin.operation_forbidden"

    # Outreach & Exports
    OUTREACH_NOT_FOUND = "outreach.not_found"
    EXPORT_NOT_FOUND = "export.not_found"
    EXPORT_GENERATION_FAILED = "export.generation_failed"

    # Validation Errors (domain-specific)
    VALIDATION_INVALID_EMAIL = "validation.invalid_email"
    VALIDATION_INVALID_URL = "validation.invalid_url"
    VALIDATION_INVALID_PHONE = "validation.invalid_phone"
    VALIDATION_INVALID_COORDINATES = "validation.invalid_coordinates"
    VALIDATION_MISSING_REQUIRED_FIELD = "validation.missing_required_field"
    VALIDATION_INVALID_ENUM_VALUE = "validation.invalid_enum_value"


def get_error_code(code: str) -> str:
    """
    Normalize and validate error code.
    Returns the code if it's a known constant, otherwise returns a generic code.
    """
    if hasattr(ErrorCodes, code.upper()):
        value: str = getattr(ErrorCodes, code.upper())
        return value
    return ErrorCodes.INTERNAL_SERVER_ERROR
