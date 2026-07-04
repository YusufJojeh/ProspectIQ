from enum import StrEnum


class SearchJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"


class WebsitePreference(StrEnum):
    ANY = "any"
    MUST_HAVE = "must_have"
    MUST_BE_MISSING = "must_be_missing"


class LeadStatus(StrEnum):
    NEW = "new"
    REVIEWED = "reviewed"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    INTERESTED = "interested"
    WON = "won"
    LOST = "lost"
    ARCHIVED = "archived"


class LeadScoreBand(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NOT_QUALIFIED = "not_qualified"
    HOT_LEAD = "hot_lead"
    WARM_LEAD = "warm_lead"
    RESEARCH_MORE = "research_more"
    LOW_PRIORITY = "low_priority"
    DO_NOT_CONTACT = "do_not_contact"


class ProviderFetchStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"


class OutreachTone(StrEnum):
    FORMAL = "formal"
    FRIENDLY = "friendly"
    CONSULTATIVE = "consultative"
    SHORT_PITCH = "short_pitch"
