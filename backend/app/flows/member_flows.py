import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_session import ConversationSession
from app.models.member import Member
from app.repositories.member_repository import MemberRepository
from app.services.contribution_service import ContributionService
from app.services.join_code_service import JoinCodeService
from app.services.payment_service import PaymentService
from app.services.period_service import PeriodService
from app.services.whatsapp_service import (
    send_cta_url_button,
    send_list_message,
    send_reply_buttons,
    send_text_message,
)

logger = logging.getLogger("akoweai")


def _format_naira(amount_kobo: int) -> str:
    return f"₦{amount_kobo / 100:,.0f}"


def _serialize_period_for_session(p: dict) -> dict:
    """
    Convert a period dict to JSON-safe form for storage in session flow_data.
    UUID and date objects are not JSON-serializable — convert them to strings.
    """
    from datetime import date
    import uuid as _uuid

    serialized = dict(p)
    # UUID → str
    if serialized.get("id") is not None:
        serialized["id"] = str(serialized["id"])
    # date → ISO string
    for key in ("start_date", "due_date"):
        val = serialized.get(key)
        if isinstance(val, date):
            serialized[key] = val.isoformat()
    return serialized


# Registration flow
async def handle_register_flow(
    phone: str,
    session: ConversationSession,
    db: AsyncSession,
) -> None:
    """
    Multi-step registration flow for WhatsApp-only members.
    Step 0: Ask for full name
    Step 1: Receive name, ask for join code
    Step 2: Validate join code, create member, join coop
    """
    step = session.current_step if session.current_flow == "REGISTER" else 0

    if step == 0:
        session.current_flow = "REGISTER"
        session.current_step = 1
        session.flow_data = {}
        await send_text_message(phone, "Welcome! 👋 What's your full name?")

    elif step == 1:
        # The incoming message_data text is captured in the webhook handler
        # and passed as the current message. We retrieve it from session.flow_data.
        # The webhook handler stores it there before calling dispatch.
        full_name = session.flow_data.get("current_text", "").strip()
        if not full_name:
            await send_text_message(phone, "Please enter your full name.")
            return
        session.flow_data["name"] = full_name
        session.current_step = 2
        await send_text_message(
            phone,
            f"Nice to meet you, {full_name.split()[0]}! 😊\n\nNow, please enter your cooperative's join code:"
        )

    elif step == 2:
        join_code = session.flow_data.get("current_text", "").strip().upper()
        if not join_code:
            await send_text_message(phone, "Please enter the join code:")
            return

        full_name = session.flow_data.get("name", "")

        try:
            result = await _register_whatsapp_member(
                phone=phone,
                full_name=full_name,
                join_code=join_code,
                db=db,
            )
        except Exception as exc:
            error_msg = str(exc)
            await send_text_message(
                phone,
                f"❌ {error_msg}\n\nPlease check your join code and try again:"
            )
            return

        # Success — reset flow and show confirmation
        session.current_flow = None
        session.current_step = 0
        session.flow_data = {}
        session.active_cooperative_id = result["cooperative_id"]

        due_date = result.get("next_due_date")
        due_str = f" (due {due_date.strftime('%d %b %Y')})" if due_date else ""
        amount_str = _format_naira(result["contribution_amount_kobo"])

        await send_text_message(
            phone,
            f"✅ You've joined *{result['cooperative_name']}*!\n\n"
            f"• Contribution: {amount_str} per period{due_str}\n\n"
            f"Here's what you can do 👇",
        )
        from app.flows.dispatch import send_member_main_menu
        await send_member_main_menu(phone)


async def _register_whatsapp_member(
    phone: str,
    full_name: str,
    join_code: str,
    db: AsyncSession,
) -> dict:
    """
    Validate join code, get-or-create member, then join coop.
    Member creation only happens AFTER code validation succeeds.
    join_cooperative() handles its own commit — no second commit needed here.
    """
    from app.repositories.join_code_repository import JoinCodeRepository

    # 1. Pre-validate the code without consuming it
    join_svc = JoinCodeService(db)
    code_repo = JoinCodeRepository(db)
    jc = await code_repo.get_by_code(join_code)
    join_svc._validate_code(jc)  # raises BadRequestException if invalid

    # 2. Get or create the member record (only after code is confirmed valid)
    member_repo = MemberRepository(db)
    member = await member_repo.get_by_phone(phone)
    if member is None:
        member = await member_repo.create(
            phone_number=phone,
            full_name=full_name,
            pin_hash=None,
        )
        await db.flush()

    # 3. Join cooperative — validates again, redeems code, creates CoopMember
    #    and first Contribution record, then commits internally
    return await join_svc.join_cooperative(join_code, member.id)


# Payment flows
async def handle_pay_intent(
    phone: str,
    member: Member,
    session: ConversationSession,
    coop_id: UUID,
    db: AsyncSession,
) -> None:
    """Decide between single-period quick pay and multi-period selection."""
    period_svc = PeriodService(db)
    periods = await period_svc.get_payable_periods(coop_id, member.id)

    if not periods:
        await send_text_message(
            phone,
            "✅ You're all caught up! There are no outstanding contributions.",
        )
        await send_reply_buttons(
            phone,
            "What would you like to do?",
            [
                {"id": "my_balance", "title": "📊 My Balance"},
                {"id": "full_history", "title": "📜 Full History"},
            ],
        )
        return

    if len(periods) == 1:
        await handle_pay_flow_single(phone, member, coop_id, periods[0], db)
    else:
        await handle_pay_flow_select(phone, member, coop_id, periods, session, db)


async def handle_pay_flow_single(
    phone: str,
    member: Member,
    coop_id: UUID,
    period: dict,
    db: AsyncSession,
) -> None:
    """Quick pay for a single period — directly sends the payment link."""
    payment_svc = PaymentService(db)
    transaction = await payment_svc.create_pending_transaction(
        member_id=member.id,
        coop_id=coop_id,
        period_data=[period],
        amount_kobo=period["amount"],
    )
    url = payment_svc.build_payment_initiation_url(transaction.reference)
    amount_str = _format_naira(period["amount"])
    label = period.get("label", "Current Period")

    await send_cta_url_button(
        to=phone,
        body=f"💳 Pay your contribution for *{label}*\n\nAmount: *{amount_str}*",
        button_text="Pay Now",
        url=url,
    )


async def handle_pay_flow_select(
    phone: str,
    member: Member,
    coop_id: UUID,
    periods: list[dict],
    session: ConversationSession,
    db: AsyncSession,
) -> None:
    """Show a list of payable periods for the member to choose from."""
    rows = []
    period_options: dict[str, dict] = {}

    for p in periods:
        label = p.get("label", f"Period {p['period_number']}")
        amount_str = _format_naira(p["amount"])

        from datetime import date as _date
        start = p.get("start_date")
        if isinstance(start, str):
            from datetime import datetime
            start = datetime.fromisoformat(start).date()
        short_title = start.strftime("%d %b %Y") if start else f"Period {p['period_number']}"

        if p.get("is_debt"):
            description = f"⚠️ Overdue · {amount_str}"
        elif p.get("is_future"):
            description = f"🔮 Future · {amount_str}"
        else:
            description = f"{label[:20]} · {amount_str}" if len(label) > 20 else f"{label} · {amount_str}"

        # Row ID uses the period's DB id or a future placeholder
        if p.get("id"):
            row_id = f"period_{p['id']}"
        else:
            row_id = f"future_{p['period_number']}"

        rows.append({"id": row_id, "title": short_title, "description": description})
        # Serialize before storing in JSONB flow_data (UUIDs and dates → strings)
        period_options[row_id] = _serialize_period_for_session(p)

    session.current_flow = "PAY_SELECTION"
    session.current_step = 1
    session.flow_data = {
        **session.flow_data,
        "period_options": period_options,
        "selected_periods": [],
        "selected_total": 0,
    }

    await send_list_message(
        to=phone,
        header="Select Period to Pay",
        body="Choose one or more periods to pay for:",
        button_text="Select Period",
        sections=[{"title": "Payable Periods", "rows": rows[:10]}],
    )


async def handle_pay_period_selected(
    phone: str,
    member: Member,
    coop_id: UUID,
    row_id: str,
    session: ConversationSession,
    db: AsyncSession,
) -> None:
    """
    Called when a period is selected from the pay selection list.
    Adds the period to selected_periods and prompts to add more or confirm.
    """
    period_options: dict = session.flow_data.get("period_options", {})
    selected_periods: list = session.flow_data.get("selected_periods", [])
    selected_total: int = session.flow_data.get("selected_total", 0)

    # Session state was lost (expired + reset) — restart pay flow fresh
    if not period_options:
        await handle_pay_intent(phone, member, session, coop_id, db)
        return

    period = period_options.get(row_id)
    if not period:
        await send_text_message(phone, "Sorry, I couldn't find that period. Please try again.")
        return

    # Avoid duplicates
    already_selected_ids = {
        p.get("id") or f"future_{p.get('period_number')}"
        for p in selected_periods
    }
    if (period.get("id") or f"future_{period.get('period_number')}") in already_selected_ids:
        await send_text_message(phone, "You've already selected that period.")
        return

    selected_periods.append(period)
    selected_total += period["amount"]
    session.flow_data["selected_periods"] = selected_periods
    session.flow_data["selected_total"] = selected_total

    total_str = _format_naira(selected_total)
    period_label = period.get("label", "Period")

    await send_reply_buttons(
        phone,
        f"✅ Added: *{period_label}*\n\nTotal selected: *{total_str}*\n\nWhat would you like to do?",
        [
            {"id": "add_period", "title": "➕ Add Another Period"},
            {"id": "confirm_pay", "title": f"💳 Pay {total_str}"},
        ],
    )


async def handle_add_period(
    phone: str,
    member: Member,
    coop_id: UUID,
    session: ConversationSession,
    db: AsyncSession,
) -> None:
    """
    Re-show the period selection list with already-selected periods removed.
    Called when user taps 'Add Another Period' during PAY_SELECTION flow.
    """
    period_options: dict = session.flow_data.get("period_options", {})
    selected_periods: list = session.flow_data.get("selected_periods", [])

    if not period_options:
        await handle_pay_intent(phone, member, session, coop_id, db)
        return
    selected_keys = set()
    for p in selected_periods:
        key = p.get("id") or f"future_{p.get('period_number')}"
        if key:
            selected_keys.add(str(key))

    rows = []
    for row_id, p in period_options.items():
        # Derive the comparable key from the stored (serialized) period
        period_key = p.get("id") or f"future_{p.get('period_number')}"
        if str(period_key) in selected_keys:
            continue  # Already selected

        label = p.get("label", f"Period {p.get('period_number')}")
        amount_str = _format_naira(p["amount"])
        if p.get("is_debt"):
            description = f"⚠️ Overdue · {amount_str}"
        elif p.get("is_future"):
            description = f"🔮 Future · {amount_str}"
        else:
            description = f"{label[:20]} · {amount_str}" if len(label) > 20 else f"{label} · {amount_str}"
        from datetime import date as _date
        start = p.get("start_date")
        if isinstance(start, str):
            from datetime import datetime
            start = datetime.fromisoformat(start).date()
        short_title = start.strftime("%d %b %Y") if start else f"Period {p.get('period_number')}"
        rows.append({"id": row_id, "title": short_title, "description": description})

    if not rows:
        await send_text_message(phone, "No more periods available to add.")
        return

    await send_list_message(
        to=phone,
        header="Select Another Period",
        body="Choose another period to add:",
        button_text="Select Period",
        sections=[{"title": "Payable Periods", "rows": rows[:10]}],
    )


async def handle_confirm_pay(
    phone: str,
    member: Member,
    coop_id: UUID,
    session: ConversationSession,
    db: AsyncSession,
) -> None:
    """Bundle all selected periods into one PendingTransaction and send CTA."""
    selected_periods: list = session.flow_data.get("selected_periods", [])
    total_kobo: int = session.flow_data.get("selected_total", 0)

    if not selected_periods:
        await send_text_message(phone, "No periods selected. Please start again.")
        session.current_flow = None
        return

    payment_svc = PaymentService(db)
    transaction = await payment_svc.create_pending_transaction(
        member_id=member.id,
        coop_id=coop_id,
        period_data=selected_periods,
        amount_kobo=total_kobo,
    )
    url = payment_svc.build_payment_initiation_url(transaction.reference)
    total_str = _format_naira(total_kobo)

    # Reset flow state
    session.current_flow = None
    session.current_step = 0
    session.flow_data = {}

    await send_cta_url_button(
        to=phone,
        body=f"💳 You're paying *{total_str}* for {len(selected_periods)} period(s).",
        button_text="Pay Now",
        url=url,
    )



# Balance and history flows
async def handle_balance_intent(
    phone: str,
    member: Member,
    coop_id: UUID,
    db: AsyncSession,
) -> None:
    contrib_svc = ContributionService(db)
    balance = await contrib_svc.get_member_balance(member.id, coop_id)

    total_str = _format_naira(balance["total_contributed_kobo"])
    paid = balance["periods_paid"]
    total = balance["periods_total"]

    lines = [
        f"📊 *Your Balance*\n",
        f"• Total contributed: {total_str}",
        f"• Periods paid: {paid}/{total}",
        "",
        "*Recent Activity:*",
    ]
    for item in balance.get("recent_activity", []):
        status_icon = "✅" if item["status"] == "paid" else "❌"
        lines.append(
            f"{status_icon} {item['period_label']} — {_format_naira(item['amount'])}"
        )

    await send_text_message(phone, "\n".join(lines))
    await send_reply_buttons(
        phone,
        "What next?",
        [
            {"id": "pay_now", "title": "💰 Pay Now"},
            {"id": "full_history", "title": "📜 Full History"},
        ],
    )


async def handle_history_intent(
    phone: str,
    member: Member,
    coop_id: UUID,
    page: int,
    db: AsyncSession,
) -> bool:
    """
    Fetch and display paginated contribution history.
    Returns True if more pages exist (so caller can update session page pointer).
    """
    contrib_svc = ContributionService(db)
    result = await contrib_svc.get_member_history(
        member_id=member.id,
        coop_id=coop_id,
        page=page,
        page_size=6,
    )

    items = result.get("items", [])
    if not items and page == 0:
        await send_text_message(phone, "You have no payment history yet.")
        await send_reply_buttons(
            phone,
            "What would you like to do?",
            [
                {"id": "pay_now", "title": "💰 Pay Now"},
                {"id": "show_menu", "title": "🏠 Menu"},
            ],
        )
        return False

    lines = [f"📜 *Payment History* (page {page + 1})\n"]
    for item in items:
        status_icon = "✅" if item["status"] == "paid" else "❌"
        lines.append(
            f"{status_icon} {item['period_label']} — {_format_naira(item['amount'])}"
        )
        if item.get("paid_at"):
            lines.append(f"   Paid: {item['paid_at'].strftime('%d %b %Y')}")

    await send_text_message(phone, "\n".join(lines))

    has_more = result.get("has_more", False)
    if has_more:
        await send_reply_buttons(
            phone,
            "There are more entries.",
            [
                {"id": "show_more_history", "title": "📄 Show More"},
                {"id": "show_menu", "title": "🏠 Menu"},
            ],
        )
    else:
        await send_reply_buttons(
            phone,
            "That's all your history.",
            [
                {"id": "pay_now", "title": "💰 Pay Now"},
                {"id": "show_menu", "title": "🏠 Menu"},
            ],
        )
    return has_more