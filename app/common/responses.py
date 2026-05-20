from typing import Any


def success_response(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data}


def error_response(code: str, message: str) -> dict[str, Any]:
    return {"success": False, "error": {"code": code, "message": message}}

