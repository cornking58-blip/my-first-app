from datetime import datetime, timedelta
import os
import secrets
from typing import Any, Dict, Optional
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request


PRO_PRICE_RUB = 740
PRO_DURATION_DAYS = 30
PAYMENT_CURRENCY = "RUB"
SUPPORTED_PAYMENT_MODES = {"mock", "yookassa"}


def normalize_payment_mode(value: Optional[str] = None) -> str:
    mode = (value or os.environ.get("PAYMENTS_MODE") or "mock").strip().lower()
    return mode if mode in SUPPORTED_PAYMENT_MODES else "mock"


def get_pro_usage_period_key(user: Dict[str, Any], now: Optional[datetime] = None) -> str:
    now = now or datetime.utcnow()
    started_at = user.get("pro_started_at") or user.get("subscription_started_at")
    if not isinstance(started_at, datetime):
        pro_until = user.get("pro_until")
        started_at = pro_until - timedelta(days=PRO_DURATION_DAYS) if isinstance(pro_until, datetime) else now
    if started_at > now:
        started_at = now
    period_seconds = PRO_DURATION_DAYS * 24 * 60 * 60
    period_index = max(0, int((now - started_at).total_seconds() // period_seconds))
    period_started_at = started_at + timedelta(days=period_index * PRO_DURATION_DAYS)
    return f"pro:{period_started_at.strftime('%Y-%m-%d')}"


def _payment_return_url() -> str:
    return (
        os.environ.get("PAYMENTS_RETURN_URL")
        or "https://frontend-production-2220.up.railway.app/payment"
    ).strip()


def _yookassa_credentials() -> tuple[str, str]:
    shop_id = (os.environ.get("YOOKASSA_SHOP_ID") or "").strip()
    secret_key = (os.environ.get("YOOKASSA_SECRET_KEY") or "").strip()
    if not shop_id or not secret_key:
        raise HTTPException(
            status_code=503,
            detail="Тестовый магазин ЮKassa ещё не подключён. Добавьте YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY.",
        )
    return shop_id, secret_key


def _serialize_payment(payment: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": payment.get("id"),
        "provider": payment.get("provider"),
        "provider_payment_id": payment.get("provider_payment_id"),
        "status": payment.get("status"),
        "paid": bool(payment.get("paid")),
        "test": bool(payment.get("test", True)),
        "amount": payment.get("amount"),
        "currency": payment.get("currency"),
        "plan": payment.get("plan"),
        "duration_days": payment.get("duration_days"),
        "confirmation_url": payment.get("confirmation_url"),
        "created_at": payment.get("created_at"),
        "updated_at": payment.get("updated_at"),
        "activated_at": payment.get("activated_at"),
        "pro_until": payment.get("pro_until"),
    }


async def _request_yookassa_payment(payload: Dict[str, Any], idempotence_key: str) -> Dict[str, Any]:
    shop_id, secret_key = _yookassa_credentials()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://api.yookassa.ru/v3/payments",
                auth=(shop_id, secret_key),
                headers={"Idempotence-Key": idempotence_key},
                json=payload,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail="ЮKassa отклонила создание тестового платежа.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Не удалось связаться с ЮKassa.") from exc


async def _get_yookassa_payment(provider_payment_id: str) -> Dict[str, Any]:
    shop_id, secret_key = _yookassa_credentials()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"https://api.yookassa.ru/v3/payments/{provider_payment_id}",
                auth=(shop_id, secret_key),
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail="Не удалось проверить платёж в ЮKassa.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Не удалось связаться с ЮKassa.") from exc


def _validate_successful_provider_payment(provider_payment: Dict[str, Any], local_payment: Dict[str, Any]) -> None:
    amount = provider_payment.get("amount") or {}
    metadata = provider_payment.get("metadata") or {}
    if provider_payment.get("status") != "succeeded" or not provider_payment.get("paid"):
        raise HTTPException(status_code=409, detail="Платёж ещё не завершён.")
    if amount.get("value") != f"{PRO_PRICE_RUB:.2f}" or amount.get("currency") != PAYMENT_CURRENCY:
        raise HTTPException(status_code=400, detail="Сумма платежа не совпадает с тарифом.")
    if metadata.get("local_payment_id") != local_payment.get("id"):
        raise HTTPException(status_code=400, detail="Платёж не связан с заказом bAIkov.")
    if provider_payment.get("id") != local_payment.get("provider_payment_id"):
        raise HTTPException(status_code=400, detail="Идентификатор платежа не совпадает.")


async def _activate_pro(db: Any, payment: Dict[str, Any]) -> Dict[str, Any]:
    payment_id = str(payment["id"])
    user_id = str(payment["user_id"])
    now = datetime.utcnow()
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь платежа не найден.")

    processed = user.get("processed_payment_ids") or []
    if payment_id not in processed:
        current_until = user.get("pro_until")
        is_active = (
            user.get("subscription_status") == "active"
            and isinstance(current_until, datetime)
            and current_until > now
        )
        base_date = current_until if is_active else now
        pro_started_at = user.get("pro_started_at") if is_active else now
        if not isinstance(pro_started_at, datetime):
            pro_started_at = now
        new_until = base_date + timedelta(days=PRO_DURATION_DAYS)
        result = await db.users.update_one(
            {"id": user_id, "processed_payment_ids": {"$ne": payment_id}},
            {
                "$set": {
                    "subscription_status": "active",
                    "subscription_provider": payment.get("provider"),
                    "pro_started_at": pro_started_at,
                    "pro_until": new_until,
                    "last_payment_at": now,
                    "updated_at": now,
                },
                "$push": {
                    "processed_payment_ids": {
                        "$each": [payment_id],
                        "$slice": -100,
                    }
                },
            },
        )
        if result.modified_count == 0:
            user = await db.users.find_one({"id": user_id})
            if payment_id not in (user or {}).get("processed_payment_ids", []):
                raise HTTPException(status_code=409, detail="Не удалось активировать PRO. Повторите проверку.")
        else:
            user = await db.users.find_one({"id": user_id})
    else:
        new_until = user.get("pro_until")

    await db.payments.update_one(
        {"id": payment_id},
        {
            "$set": {
                "status": "succeeded",
                "paid": True,
                "activated_at": payment.get("activated_at") or now,
                "pro_until": new_until,
                "updated_at": now,
            }
        },
    )
    return user or {}


def create_payments_router(
    db: Any,
    require_current_user: Any,
    serialize_user_account: Any,
    build_usage_snapshot: Any,
) -> APIRouter:
    router = APIRouter(prefix="/api/payments", tags=["payments"])

    @router.get("/config")
    async def payment_config():
        mode = normalize_payment_mode()
        yookassa_ready = bool(
            (os.environ.get("YOOKASSA_SHOP_ID") or "").strip()
            and (os.environ.get("YOOKASSA_SECRET_KEY") or "").strip()
        )
        return {
            "mode": mode,
            "test": True,
            "price": PRO_PRICE_RUB,
            "currency": PAYMENT_CURRENCY,
            "duration_days": PRO_DURATION_DAYS,
            "provider_ready": mode == "mock" or yookassa_ready,
        }

    @router.post("/pro/create")
    async def create_pro_payment(current_user: Dict[str, Any] = Depends(require_current_user)):
        if current_user.get("access", {}).get("plan") == "owner":
            raise HTTPException(status_code=400, detail="Для владельца PRO уже доступен без ограничений.")

        now = datetime.utcnow()
        existing = await db.payments.find_one(
            {
                "user_id": current_user["id"],
                "status": "pending",
                "created_at": {"$gte": now - timedelta(minutes=30)},
            },
            sort=[("created_at", -1)],
        )
        if existing:
            return {"payment": _serialize_payment(existing), "mode": existing.get("provider")}

        mode = normalize_payment_mode()
        payment_id = f"pay_{uuid.uuid4().hex}"
        payment = {
            "id": payment_id,
            "user_id": current_user["id"],
            "provider": mode,
            "status": "pending",
            "paid": False,
            "test": True,
            "amount": f"{PRO_PRICE_RUB:.2f}",
            "currency": PAYMENT_CURRENCY,
            "plan": "pro",
            "duration_days": PRO_DURATION_DAYS,
            "idempotence_key": str(uuid.uuid4()),
            "created_at": now,
            "updated_at": now,
        }

        if mode == "yookassa":
            provider_payment = await _request_yookassa_payment(
                {
                    "amount": {"value": f"{PRO_PRICE_RUB:.2f}", "currency": PAYMENT_CURRENCY},
                    "capture": True,
                    "confirmation": {"type": "redirect", "return_url": _payment_return_url()},
                    "description": "bAIkov PRO на 30 дней",
                    "metadata": {
                        "local_payment_id": payment_id,
                        "user_id": current_user["id"],
                        "plan": "pro",
                    },
                },
                payment["idempotence_key"],
            )
            payment["provider_payment_id"] = provider_payment.get("id")
            payment["status"] = provider_payment.get("status") or "pending"
            payment["test"] = bool(provider_payment.get("test", True))
            payment["confirmation_url"] = (provider_payment.get("confirmation") or {}).get("confirmation_url")
        else:
            payment["provider_payment_id"] = f"mock_{secrets.token_hex(12)}"
            payment["confirmation_url"] = None

        await db.payments.insert_one(payment)
        return {"payment": _serialize_payment(payment), "mode": mode}

    @router.get("/history")
    async def payment_history(current_user: Dict[str, Any] = Depends(require_current_user)):
        cursor = db.payments.find({"user_id": current_user["id"]}).sort("created_at", -1).limit(20)
        payments = await cursor.to_list(length=20)
        return {"payments": [_serialize_payment(payment) for payment in payments]}

    @router.post("/mock/{payment_id}/complete")
    async def complete_mock_payment(
        payment_id: str,
        current_user: Dict[str, Any] = Depends(require_current_user),
    ):
        payment = await db.payments.find_one({"id": payment_id, "user_id": current_user["id"]})
        if not payment:
            raise HTTPException(status_code=404, detail="Платёж не найден.")
        if payment.get("provider") != "mock":
            raise HTTPException(status_code=400, detail="Это не mock-платёж.")
        user = await _activate_pro(db, payment)
        updated = await db.payments.find_one({"id": payment_id})
        return {
            "payment": _serialize_payment(updated or payment),
            "user": serialize_user_account(user),
            "usage": await build_usage_snapshot(user),
        }

    @router.post("/yookassa/webhook")
    async def yookassa_webhook(request: Request):
        body = await request.json()
        if body.get("event") != "payment.succeeded":
            return {"ok": True}
        object_data = body.get("object") or {}
        provider_payment_id = object_data.get("id")
        if not provider_payment_id:
            raise HTTPException(status_code=400, detail="В уведомлении нет идентификатора платежа.")
        provider_payment = await _get_yookassa_payment(provider_payment_id)
        metadata = provider_payment.get("metadata") or {}
        local_payment_id = metadata.get("local_payment_id")
        payment = await db.payments.find_one(
            {"id": local_payment_id, "provider_payment_id": provider_payment_id, "provider": "yookassa"}
        )
        if not payment:
            raise HTTPException(status_code=404, detail="Платёж bAIkov не найден.")
        _validate_successful_provider_payment(provider_payment, payment)
        await _activate_pro(db, payment)
        return {"ok": True}

    @router.get("/{payment_id}")
    async def get_payment_status(
        payment_id: str,
        current_user: Dict[str, Any] = Depends(require_current_user),
    ):
        payment = await db.payments.find_one({"id": payment_id, "user_id": current_user["id"]})
        if not payment:
            raise HTTPException(status_code=404, detail="Платёж не найден.")
        if payment.get("provider") == "yookassa" and payment.get("status") == "pending":
            provider_payment = await _get_yookassa_payment(str(payment.get("provider_payment_id")))
            if provider_payment.get("status") == "succeeded" and provider_payment.get("paid"):
                _validate_successful_provider_payment(provider_payment, payment)
                user = await _activate_pro(db, payment)
                payment = await db.payments.find_one({"id": payment_id}) or payment
                return {
                    "payment": _serialize_payment(payment),
                    "user": serialize_user_account(user),
                    "usage": await build_usage_snapshot(user),
                }
            if provider_payment.get("status") == "canceled":
                await db.payments.update_one(
                    {"id": payment_id},
                    {"$set": {"status": "canceled", "updated_at": datetime.utcnow()}},
                )
                payment["status"] = "canceled"
        return {"payment": _serialize_payment(payment)}

    return router
