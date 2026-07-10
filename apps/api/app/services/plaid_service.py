from datetime import datetime, timezone

import plaid
from plaid.api import plaid_api
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from sqlalchemy.orm import Session

from app.config import settings
from app.models.account import Account
from app.models.plaid_item import PlaidItem
from app.models.transaction import Transaction
from app.repositories.plaid_item import PlaidItemRepository
from app.services.dedupe import generate_dedupe_hash as _generate_dedupe_hash
from app.services.enrichment import EnrichmentInput
from app.services.enrichment.apply import apply_enrichment as _apply_enrichment
from app.services.plaid_errors import map_plaid_exception

PLAID_ENV_MAP = {
    "sandbox": plaid.Environment.Sandbox,
    "production": plaid.Environment.Production,
}


def _call(fn, *args, **kwargs):
    """Invoke a Plaid SDK method, translating failures into ``PlaidError``.

    Centralizing the try/except here keeps the three call sites clean and
    guarantees the sandbox-harness path (which reuses these functions) is
    protected too. Only ``plaid.ApiException`` is mapped; other exceptions
    propagate unchanged.
    """
    try:
        return fn(*args, **kwargs)
    except plaid.ApiException as exc:
        raise map_plaid_exception(exc) from None


def _get_plaid_client() -> plaid_api.PlaidApi:
    configuration = plaid.Configuration(
        host=PLAID_ENV_MAP.get(settings.plaid_env, plaid.Environment.Sandbox),
        api_key={
            "clientId": settings.plaid_client_id,
            "secret": settings.plaid_secret,
        },
    )
    api_client = plaid.ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)


def get_plaid_client() -> plaid_api.PlaidApi:
    return _get_plaid_client()


def create_link_token(client: plaid_api.PlaidApi, user_id: int) -> dict:
    request_kwargs = dict(
        products=[Products("transactions")],
        client_name="Finance Tracker",
        country_codes=[CountryCode("US")],
        language="en",
        user=LinkTokenCreateRequestUser(client_user_id=str(user_id)),
    )
    # Only register a webhook callback when a URL is configured, so local /
    # sandbox links without a public URL keep working.
    if settings.plaid_webhook_url:
        request_kwargs["webhook"] = settings.plaid_webhook_url
    # OAuth institutions (Chase, BofA, Wells Fargo, Capital One, …) require a
    # redirect_uri registered in the Plaid Dashboard; without it Link fails when
    # the user selects one. Only send it when configured so non-OAuth sandbox
    # links keep working without any Dashboard setup.
    if settings.plaid_redirect_uri:
        request_kwargs["redirect_uri"] = settings.plaid_redirect_uri
    request = LinkTokenCreateRequest(**request_kwargs)
    response = _call(client.link_token_create, request)
    return {
        "link_token": response.link_token,
        "expiration": response.expiration,
    }


def exchange_public_token(client: plaid_api.PlaidApi, public_token: str) -> dict:
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = _call(client.item_public_token_exchange, request)
    return {
        "access_token": response.access_token,
        "item_id": response.item_id,
    }


def _find_or_create_account(
    db: Session, user_id: int, plaid_account: dict, plaid_item: PlaidItem
) -> Account:
    from sqlalchemy import select

    account_id = plaid_account.get("account_id", "")
    stmt = select(Account).where(
        Account.user_id == user_id,
        Account.external_account_id == account_id,
    )
    account = db.scalars(stmt).first()
    if account:
        account.balance = plaid_account.get("balances", {}).get("current", 0.0) or 0.0
        account.last_synced_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(account)
        return account

    type_map = {
        "depository": "checking",
        "credit": "credit",
        "loan": "loan",
        "investment": "investment",
    }
    plaid_type = plaid_account.get("type", "depository")
    account = Account(
        user_id=user_id,
        name=plaid_account.get("name", "Unknown Account"),
        type=type_map.get(plaid_type, "checking"),
        institution_name=plaid_item.institution_name,
        external_account_id=account_id,
        balance=plaid_account.get("balances", {}).get("current", 0.0) or 0.0,
        last_synced_at=datetime.now(timezone.utc),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def sync_transactions(
    client: plaid_api.PlaidApi, db: Session, plaid_item: PlaidItem, user_id: int
) -> dict:
    repo = PlaidItemRepository(db)
    cursor = plaid_item.cursor

    added_count = 0
    modified_count = 0
    removed_count = 0

    has_more = True
    while has_more:
        request_kwargs = {"access_token": plaid_item.access_token}
        if cursor:
            request_kwargs["cursor"] = cursor
        request = TransactionsSyncRequest(**request_kwargs)
        response = _call(client.transactions_sync, request)

        accounts_by_id = {}
        for plaid_acct in response.accounts:
            acct_dict = plaid_acct.to_dict()
            account = _find_or_create_account(db, user_id, acct_dict, plaid_item)
            accounts_by_id[acct_dict["account_id"]] = account

        new_rows: list[tuple[Transaction, EnrichmentInput]] = []
        for txn in response.added:
            txn_dict = txn.to_dict()
            account = accounts_by_id.get(txn_dict.get("account_id"))
            if not account:
                continue
            merchant = txn_dict.get("merchant_name") or txn_dict.get("name", "Unknown")
            amount = txn_dict.get("amount", 0.0)
            # Plaid: positive = money leaving account (expense), negative = income
            stored_amount = -amount
            occurred_on = txn_dict.get("date")
            dedupe_hash = _generate_dedupe_hash(
                str(occurred_on), amount, merchant, account.id
            )
            from sqlalchemy import select

            existing = db.scalars(
                select(Transaction).where(Transaction.dedupe_hash == dedupe_hash)
            ).first()
            if existing:
                continue

            category_list = txn_dict.get("personal_finance_category", {})
            category = None
            if isinstance(category_list, dict):
                primary = (
                    (category_list.get("primary") or "").lower().replace("_", " ")
                )
                detailed = (
                    (category_list.get("detailed") or "").lower().replace("_", " ")
                )
                # Plaid's primary FOOD_AND_DRINK conflates restaurants with
                # groceries; the detailed label (FOOD_AND_DRINK_GROCERIES vs
                # _RESTAURANT/_COFFEE/...) splits them, which the dining-first
                # recommender depends on. Other primaries are already granular
                # enough — and their detailed labels aren't in the taxonomy —
                # so keep using primary for them. Fall back to primary when
                # detailed is absent (no regression for older data).
                if primary == "food and drink" and detailed:
                    category = detailed
                else:
                    category = primary

            row = Transaction(
                user_id=user_id,
                account_id=account.id,
                external_id=txn_dict.get("transaction_id"),
                occurred_on=occurred_on,
                amount=stored_amount,
                merchant=merchant,
                normalized_merchant=merchant.lower().strip(),
                category=category or None,
                is_income=stored_amount > 0,
                is_savings=False,
                source="plaid",
                dedupe_hash=dedupe_hash,
            )
            db.add(row)
            new_rows.append(
                (
                    row,
                    EnrichmentInput(
                        external_id=txn_dict.get("transaction_id"),
                        merchant=merchant,
                        amount=stored_amount,
                        plaid_category=category or None,
                    ),
                )
            )
            added_count += 1

        # Overwrite category / normalized_merchant from the enrichment provider
        # (noop by default → no change). Done before commit so the enriched
        # values persist in the same transaction as the insert.
        _apply_enrichment(new_rows)

        for txn in response.modified:
            txn_dict = txn.to_dict()
            ext_id = txn_dict.get("transaction_id")
            if not ext_id:
                continue
            from sqlalchemy import select

            existing = db.scalars(
                select(Transaction).where(
                    Transaction.external_id == ext_id, Transaction.user_id == user_id
                )
            ).first()
            if existing:
                merchant = txn_dict.get("merchant_name") or txn_dict.get("name", "Unknown")
                amount = txn_dict.get("amount", 0.0)
                existing.amount = -amount
                existing.merchant = merchant
                existing.normalized_merchant = merchant.lower().strip()
                existing.is_income = (-amount) > 0
                modified_count += 1

        for txn in response.removed:
            txn_dict = txn.to_dict()
            ext_id = txn_dict.get("transaction_id")
            if not ext_id:
                continue
            from sqlalchemy import select

            existing = db.scalars(
                select(Transaction).where(
                    Transaction.external_id == ext_id, Transaction.user_id == user_id
                )
            ).first()
            if existing:
                db.delete(existing)
                removed_count += 1

        db.commit()

        cursor = response.next_cursor
        has_more = response.has_more

    repo.update_cursor(plaid_item, cursor)

    accounts_synced = len(accounts_by_id) if "accounts_by_id" in dir() else 0
    return {
        "accounts_synced": accounts_synced,
        "transactions_added": added_count,
        "transactions_modified": modified_count,
        "transactions_removed": removed_count,
    }
