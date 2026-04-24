from app.core.errors import ForbiddenError


class PlanLimitExceededError(ForbiddenError):
    code = "plan_limit_exceeded"


class SubscriptionAccessError(ForbiddenError):
    code = "subscription_access_denied"
