import json
from collections.abc import AsyncGenerator
from datetime import date, timedelta
from typing import Any

import anthropic
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.config import settings
from app.database import get_db
from app.models.account import Account
from app.models.card import Card
from app.models.goal import Goal
from app.models.transaction import Transaction

router = APIRouter(prefix="/chat", tags=["chat"])

SYSTEM_PROMPT = f"""You are a helpful financial assistant for a personal finance tracker app. \
Today's date is {date.today().isoformat()}.

You have access to the user's financial data through tools. When the user asks about their \
finances, use the appropriate tool to look up real data before answering. Be concise, specific, \
and use exact numbers from the data.

Format currency values with $ and two decimal places. When listing items, use clean formatting. \
Keep responses conversational but data-driven."""

TOOLS = [
    {
        "name": "get_accounts",
        "description": "Get all of the user's financial accounts with current balances. "
        "Returns account name, type, institution, and balance.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_transactions",
        "description": "Get the user's transactions. Can filter by category or account. "
        "Returns date, merchant, amount, category, and whether it's income.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by spending category (e.g. 'food', 'transport')",
                },
                "account_id": {
                    "type": "integer",
                    "description": "Filter by account ID",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of transactions to return (default 50)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_spending_by_category",
        "description": "Get total spending broken down by category for a given time period. "
        "Useful for understanding where money is going.",
        "input_schema": {
            "type": "object",
            "properties": {
                "months": {
                    "type": "integer",
                    "description": "Number of months to look back (default 1)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_net_worth",
        "description": "Calculate the user's total net worth by summing all account balances.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_goals",
        "description": "Get all of the user's financial goals with progress toward each target.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_cards",
        "description": "Get all of the user's credit cards with annual fees and network info.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


def execute_tool(tool_name: str, tool_input: dict[str, Any], db: Session, user_id: int) -> str:
    if tool_name == "get_accounts":
        accounts = db.scalars(select(Account).where(Account.user_id == user_id)).all()
        return json.dumps(
            [
                {
                    "id": a.id,
                    "name": a.name,
                    "type": a.type,
                    "institution": a.institution_name,
                    "balance": float(a.balance),
                    "currency": a.currency,
                }
                for a in accounts
            ]
        )

    if tool_name == "get_transactions":
        stmt = select(Transaction).where(Transaction.user_id == user_id)
        if cat := tool_input.get("category"):
            stmt = stmt.where(Transaction.category == cat)
        if acc_id := tool_input.get("account_id"):
            stmt = stmt.where(Transaction.account_id == acc_id)
        stmt = stmt.order_by(Transaction.occurred_on.desc())
        limit = tool_input.get("limit", 50)
        stmt = stmt.limit(limit)
        txns = db.scalars(stmt).all()
        return json.dumps(
            [
                {
                    "date": t.occurred_on.isoformat() if hasattr(t.occurred_on, "isoformat") else str(t.occurred_on),
                    "merchant": t.merchant,
                    "amount": float(t.amount),
                    "category": t.category,
                    "is_income": t.is_income,
                    "account_id": t.account_id,
                }
                for t in txns
            ]
        )

    if tool_name == "get_spending_by_category":
        months = tool_input.get("months", 1)
        cutoff = date.today() - timedelta(days=months * 30)
        stmt = (
            select(Transaction.category, func.sum(func.abs(Transaction.amount)).label("total"))
            .where(
                Transaction.user_id == user_id,
                Transaction.is_income.is_(False),
                Transaction.occurred_on >= cutoff,
            )
            .group_by(Transaction.category)
            .order_by(func.sum(func.abs(Transaction.amount)).desc())
        )
        rows = db.execute(stmt).all()
        return json.dumps(
            [{"category": r.category or "uncategorized", "total": float(r.total)} for r in rows]
        )

    if tool_name == "get_net_worth":
        total = db.scalar(
            select(func.sum(Account.balance)).where(Account.user_id == user_id)
        )
        return json.dumps({"net_worth": float(total or 0)})

    if tool_name == "get_goals":
        goals = db.scalars(select(Goal).where(Goal.user_id == user_id)).all()
        return json.dumps(
            [
                {
                    "name": g.name,
                    "type": g.goal_type,
                    "target": float(g.target_amount),
                    "current": float(g.current_amount),
                    "progress_pct": round(
                        (float(g.current_amount) / float(g.target_amount) * 100)
                        if g.target_amount
                        else 0,
                        1,
                    ),
                    "deadline": str(g.deadline) if g.deadline else None,
                    "is_monthly": g.is_monthly,
                }
                for g in goals
            ]
        )

    if tool_name == "get_cards":
        cards = db.scalars(select(Card).where(Card.user_id == user_id)).all()
        return json.dumps(
            [
                {
                    "name": c.name,
                    "network": c.network,
                    "annual_fee": float(c.annual_fee),
                }
                for c in cards
            ]
        )

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


async def stream_chat(
    messages: list[ChatMessage], db: Session, user_id: int
) -> AsyncGenerator[str, None]:
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    api_messages = [{"role": m.role, "content": m.content} for m in messages]

    while True:
        with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=api_messages,
            tools=TOOLS,
        ) as stream:
            # Stream text tokens as they arrive
            for text in stream.text_stream:
                yield f'0:{json.dumps(text)}\n'

            # After streaming completes, check if tool calls were made
            response = stream.get_final_message()

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        if not tool_use_blocks:
            break

        # Process tool calls and loop for the follow-up response
        api_messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in tool_use_blocks:
            result = execute_tool(block.name, block.input, db, user_id)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                }
            )

        api_messages.append({"role": "user", "content": tool_results})


@router.post("")
async def chat(
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> StreamingResponse:
    body = await request.json()
    chat_req = ChatRequest(**body)

    return StreamingResponse(
        stream_chat(chat_req.messages, db, user_id),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Vercel-AI-Data-Stream": "v1",
        },
    )
