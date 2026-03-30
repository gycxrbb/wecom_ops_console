from typing import Callable
import json
import uuid
from fastapi.routing import APIRoute
from fastapi import Request, Response
from fastapi.responses import JSONResponse

class UnifiedResponseRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            try:
                response = await original_route_handler(request)
                if hasattr(response, "body") and getattr(response, "media_type", "") == "application/json":
                    try:
                        body_json = json.loads(response.body.decode())
                        if isinstance(body_json, dict) and "code" in body_json and "message" in body_json:
                            # Add request_id if missing
                            if "request_id" not in body_json:
                                body_json["request_id"] = str(uuid.uuid4())
                                response.body = json.dumps(body_json).encode()
                                response.headers["content-length"] = str(len(response.body))
                            return response 
                        
                        unified_body = {
                            "code": 0,
                            "message": "ok",
                            "data": body_json,
                            "request_id": str(uuid.uuid4())
                        }
                        response = JSONResponse(content=unified_body, status_code=response.status_code)
                    except json.JSONDecodeError:
                        pass
                elif isinstance(response, JSONResponse) and hasattr(response, 'body'):
                    pass # Handled by media_type application/json above
                return response
            except Exception as e:
                # Let global exception handlers deal with actual exceptions
                raise e

        return custom_route_handler
