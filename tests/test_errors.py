import asyncio
import json

from fastapi.exceptions import RequestValidationError

from app.errors import RembgError, validation_error_handler


def test_error_body_shape():
    e = RembgError(
        "model missing",
        type="invalid_request_error",
        code="model_not_found",
        status=404,
        param="model",
    )
    body = e.to_body()
    assert body == {
        "error": {
            "message": "model missing",
            "type": "invalid_request_error",
            "code": "model_not_found",
            "param": "model",
        }
    }
    assert e.status == 404


def test_validation_error_openai_shape():
    exc = RequestValidationError(
        [
            {
                "loc": ("body", "image"),
                "msg": "Field required",
                "type": "missing",
            }
        ]
    )
    resp = asyncio.run(validation_error_handler(None, exc))  # type: ignore[arg-type]
    assert resp.status_code == 400
    body = json.loads(resp.body)
    assert body["error"]["type"] == "invalid_request_error"
    assert body["error"]["param"] == "image"
    assert body["error"]["message"] == "Field required"
