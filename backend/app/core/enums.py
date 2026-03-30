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
    BROADCAST = "BROADCAST"
    WITHDRAWAL = "WITHDRAWAL"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Intent(str, Enum):
    PAY = "PAY"
    BALANCE = "BALANCE"
    REGISTER = "REGISTER"
    HISTORY = "HISTORY"
    COOP_STATUS = "COOP_STATUS"
    SEND_REMINDERS = "SEND_REMINDERS"
    COOP_SUMMARY = "COOP_SUMMARY"
    BROADCAST = "BROADCAST"
    MEMBER_LOOKUP = "MEMBER_LOOKUP"
    VIEW_MEMBERS = "VIEW_MEMBERS"
    MEMBERS_NEXT = "MEMBERS_NEXT"
    MEMBERS_PREV = "MEMBERS_PREV"
    VIEW_UNPAID = "VIEW_UNPAID"
    ADD_PERIOD = "ADD_PERIOD"
    CONFIRM_PAY = "CONFIRM_PAY"
    CONFIRM_BROADCAST = "CONFIRM_BROADCAST"
    SHOW_MORE = "SHOW_MORE"
    SWITCH_COOP = "SWITCH_COOP"
    CANCEL = "CANCEL"
    GREETING = "GREETING"
    SHOW_SWITCHER = "SHOW_SWITCHER"
    SHOW_MENU = "SHOW_MENU"
    UNKNOWN = "UNKNOWN"