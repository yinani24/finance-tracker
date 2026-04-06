from fastapi import APIRouter

from app.api.accounts import router as accounts_router
from app.api.cards import router as cards_router
from app.api.goals import router as goals_router
from app.api.plaid import router as plaid_router
from app.api.me import router as me_router
from app.api.transactions import router as transactions_router

api_router = APIRouter()
api_router.include_router(me_router)
api_router.include_router(accounts_router)
api_router.include_router(transactions_router)
api_router.include_router(goals_router)
api_router.include_router(cards_router)
api_router.include_router(plaid_router)
