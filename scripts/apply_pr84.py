from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, found {count}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "backend/server.py",
    "    from .photo_diagnosis import analyze_photo_with_ai\n",
    "    from .photo_diagnosis import analyze_photo_with_ai\n    from .payments import create_payments_router, get_pro_usage_period_key\n",
    "package payment import",
)

replace_once(
    "backend/server.py",
    "    from photo_diagnosis import analyze_photo_with_ai\n",
    "    from photo_diagnosis import analyze_photo_with_ai\n    from payments import create_payments_router, get_pro_usage_period_key\n",
    "local payment import",
)

replace_once(
    "backend/server.py",
    "    return f\"pro:{datetime.utcnow().strftime('%Y-%m')}\"",
    "    return get_pro_usage_period_key(user, datetime.utcnow())",
    "pro usage period",
)

replace_once(
    "backend/server.py",
    "app.include_router(create_products_router(db))\napp.include_router(api_router)",
    "app.include_router(create_products_router(db))\napp.include_router(\n    create_payments_router(\n        db,\n        require_current_user,\n        serialize_user_account,\n        build_usage_snapshot,\n    )\n)\napp.include_router(api_router)",
    "payment router",
)

replace_once(
    "backend/server.py",
    "    await db.ai_usage.create_index([(\"user_id\", 1), (\"period_key\", 1)], unique=True)\n    schedule_catalog_migration(db)",
    "    await db.ai_usage.create_index([(\"user_id\", 1), (\"period_key\", 1)], unique=True)\n    await db.payments.create_index(\"id\", unique=True)\n    await db.payments.create_index([(\"user_id\", 1), (\"created_at\", -1)])\n    await db.payments.create_index(\"provider_payment_id\", sparse=True)\n    schedule_catalog_migration(db)",
    "payment indexes",
)

replace_once(
    "frontend/app/account.tsx",
    """  const handlePro = () => {\n    Alert.alert(\n      'bAIkov PRO — 740 ₽/месяц',\n      'Тариф и лимиты уже зафиксированы. Подключение оплаты — следующий этап разработки.',\n      [{ text: 'Понятно' }],\n    );\n  };""",
    """  const handlePro = () => {\n    router.push('/payment');\n  };""",
    "account payment button",
)

replace_once(
    "frontend/app/_layout.tsx",
    "          <Stack.Screen name=\"account\" />",
    "          <Stack.Screen name=\"account\" />\n          <Stack.Screen name=\"payment\" />",
    "payment route",
)

replace_once(
    ".github/workflows/baikov-regression.yml",
    "run: python -m py_compile backend/product_catalog.py backend/strict_catalog_ai.py backend/photo_diagnosis.py backend/server.py",
    "run: python -m py_compile backend/product_catalog.py backend/strict_catalog_ai.py backend/photo_diagnosis.py backend/payments.py backend/server.py",
    "payment syntax check",
)

replace_once(
    ".github/workflows/baikov-regression.yml",
    "      - name: Run account and limits tests\n        run: python -m unittest -v tests/test_account_limits.py",
    "      - name: Run account and limits tests\n        run: python -m unittest -v tests/test_account_limits.py\n      - name: Run payment tests\n        run: python -m unittest -v tests/test_payments.py",
    "payment tests",
)

replace_once(
    "frontend/app/payment.tsx",
    "color: colors.error",
    "color: colors.danger",
    "danger color",
)

replace_once(
    "frontend/app/payment.tsx",
    "fontWeight: '850'",
    "fontWeight: '800'",
    "price font weight",
)

replace_once(
    "backend/payments.py",
    "        if current_user.get(\"access\", {}).get(\"plan\") == \"owner\":",
    "        if serialize_user_account(current_user).get(\"access\", {}).get(\"plan\") == \"owner\":",
    "owner payment protection",
)

Path("scripts/apply_pr84.py").unlink(missing_ok=True)
Path(".github/workflows/apply-pr84.yml").unlink(missing_ok=True)
