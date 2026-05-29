# core/response.py

from collections.abc import AsyncIterator, Iterator
from typing import Any, Optional, Union

import inspect
import types
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel


class ResponseModel(BaseModel):
    data: Any | None = None
    code: int = 200
    msg: Any = "SUCCESS"


def response(
    data: Any = None,
    code: int = 200,
    msg: Any = "SUCCESS",
    media_type: Optional[str] = None,
    headers: Optional[dict] = None,
) -> Union[JSONResponse, StreamingResponse]:
    if (
        isinstance(data, types.GeneratorType)
        or inspect.isasyncgen(data)
        or isinstance(data, (Iterator, AsyncIterator))
    ):
        return StreamingResponse(
            data,
            status_code=code,
            media_type=media_type or "application/octet-stream",
            headers=headers,
        )

    if data is None:
        data = []

    payload = ResponseModel(data=data, code=code, msg=msg).model_dump()
    return JSONResponse(content=payload, status_code=code)
