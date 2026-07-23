"""Load the bAIkov backend runtime enhancement when Railway starts from repo root."""

try:
    from backend import sitecustomize as _baikov_sitecustomize
except Exception:
    _baikov_sitecustomize = None
