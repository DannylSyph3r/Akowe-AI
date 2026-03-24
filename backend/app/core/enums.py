from enum import Enum


class Role(str, Enum):
    MEMBER = "member"
    EXCO = "exco"


class ContributionStatus(str, Enum):
    UNPAID = "unpaid"
    PAID = "paid"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    INVALIDATED = "invalidated"


class ReminderStage(str, Enum):
    SEVEN_DAY = "7_day"
    THREE_DAY = "3_day"
    ONE_DAY = "1_day"
    DUE_DATE = "due_date"
    ONE_WEEK_OVERDUE = "1_week_overdue"
    TWO_WEEKS_OVERDUE = "2_weeks_overdue"


class ReminderStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    CANCELLED = "cancelled"


class Frequency(str, Enum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    TRIWEEKLY = "triweekly"
    MONTHLY = "monthly"
    BIMONTHLY = "bimonthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class ConversationFlow(str, Enum):
    REGISTER = "REGISTER"
    PAY_SELECTION = "PAY_SELECTION"
    BROADCAST = "BROADCAST"
    MEMBER_LOOKUP = "MEMBER_LOOKUP"


class StepUpAction(str, Enum):
    SETTINGS = "SETTINGS"
    WITHDRAWAL = "WITHDRAWAL"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"