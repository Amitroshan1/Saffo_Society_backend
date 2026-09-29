def success_response(message: str, data=None) -> dict:
    return {"success": True, "message": message, "data": {} if data is None else data}


def error_response(message: str) -> dict:
    return {"success": False, "message": message}
