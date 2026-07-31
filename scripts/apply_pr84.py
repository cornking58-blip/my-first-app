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

payment_screen = Path("frontend/app/payment.tsx")
payment_text = payment_screen.read_text(encoding="utf-8")
payment_text = payment_text.replace("fontWeight: '750'", "fontWeight: '700'")
payment_text = payment_text.replace("fontWeight: '650'", "fontWeight: '600'")
payment_screen.write_text(payment_text, encoding="utf-8")

replace_once(
    "backend/payments.py",
    "        if current_user.get(\"access\", {}).get(\"plan\") == \"owner\":",
    "        if serialize_user_account(current_user).get(\"access\", {}).get(\"plan\") == \"owner\":",
    "owner payment protection",
)

final_workflow = """name: bAIkov regression

on:
  pull_request:
    branches:
      - main
  push:
    branches:
      - main

permissions:
  contents: read

jobs:
  backend-regression:
    runs-on: ubuntu-latest
    env:
      MONGO_URL: mongodb://127.0.0.1:27017
      DB_NAME: baikov_test
      AUTH_JWT_SECRET: test-secret-with-at-least-thirty-two-characters
      PAYMENTS_MODE: mock
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
          cache: pip
      - name: Install focused backend dependencies
        run: >-
          python -m pip install --quiet
          fastapi==0.110.1
          python-dotenv
          motor==3.3.1
          pymongo==4.5.0
          httpx==0.28.1
          openai==1.99.9
          PyJWT==2.12.1
          pandas==3.0.1
          email-validator==2.3.0
          python-multipart==0.0.22
      - name: Validate backend syntax
        run: python -m py_compile backend/product_catalog.py backend/strict_catalog_ai.py backend/photo_diagnosis.py backend/payments.py backend/server.py
      - name: Run permanent scenario suite
        run: python -m unittest -v tests/test_baikov_regression_suite.py
      - name: Run strict catalog tests
        run: python -m unittest -v tests/test_supabase_strict_catalog.py
      - name: Run AI chat tests
        run: python -m unittest -v tests/test_ai_chat.py
      - name: Run unified catalog tests
        run: python -m unittest -v tests/test_unified_catalog.py
      - name: Run photo diagnosis tests
        run: python -m unittest -v tests/test_photo_diagnosis.py
      - name: Run account and limits tests
        run: python -m unittest -v tests/test_account_limits.py
      - name: Run payment tests
        run: python -m unittest -v tests/test_payments.py

  frontend-types:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install Yarn 1
        run: npm install --global yarn@1.22.22 --silent
      - name: Install frontend dependencies
        run: yarn install --frozen-lockfile --silent
      - name: TypeScript check
        run: yarn exec tsc --noEmit
"""
Path(".github/workflows/baikov-regression.yml").write_text(final_workflow, encoding="utf-8")

Path("scripts/apply_pr84.py").unlink(missing_ok=True)
Path(".github/workflows/apply-pr84.yml").unlink(missing_ok=True)
