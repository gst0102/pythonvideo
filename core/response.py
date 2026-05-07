# core/response.py
# 统一接口返回格式

from typing import Any, Union, Optional
from pydantic import BaseModel
from fastapi.responses import JSONResponse, StreamingResponse
import types

class ResponseModel(BaseModel):
    data: Any | None = None
    code: int = 200
    msg: Any = "SUCCESS"

def response(
        data: Any = None,  # 返回的数据，可以是任意类型，也可以是none
        code: int = 200,  # 状态码
        msg: Any = "SUCCESS",  # 状态信息
        media_type: Optional[str] = None,  # 新增：允许指定媒体类型
        headers: Optional[dict] = None  # 新增：允许指定头部（用于下载文件名）
        ) -> Union[JSONResponse, StreamingResponse]:
    # 场景 1：如果是流式数据（生成器），返回 StreamingResponse
    # 检查 data 是否是生成器
    if isinstance(data, types.GeneratorType):
        return StreamingResponse(
            data, 
            status_code=code,
            media_type=media_type or "application/octet-stream",  # 默认二进制流
            headers=headers
        )

    if data is None:
        data = []

    payload = ResponseModel(data=data, code=code, msg=msg).model_dump()
    return JSONResponse(content=payload, status_code=code)
