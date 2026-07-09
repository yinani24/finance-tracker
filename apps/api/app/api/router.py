from fastapi import APIRouter

from app.api.accounts import router as accounts_router
from app.api.card_bonuses import router as card_bonuses_router
from app.api.cards import router as cards_router
from app.api.chat import router as chat_router
from app.api.goals import router as goals_router
from app.api.imports import router as imports_router
from app.api.insights import router as insights_router
from app.api.me import router as me_router
from app.api.plaid import router as plaid_router
from app.api.recommendations import router as recommendations_router
from app.api.transactions import router as transactions_router

api_router = APIRouter()
api_router.include_router(me_router)
api_router.include_router(accounts_router)
api_router.include_router(transactions_router)
api_router.include_router(imports_router)
api_router.include_router(goals_router)
api_router.include_router(cards_router)
api_router.include_router(card_bonuses_router)
api_router.include_router(plaid_router)
api_router.include_router(recommendations_router)
api_router.include_router(insights_router)
api_router.include_router(chat_router)
