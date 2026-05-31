from __future__ import annotations

from importlib.util import find_spec
from typing import Any

from yl_rag.core.customer_service import CustomerChatRequest
from yl_rag.services.customer_service import customer_service_rag


class SocketIODependencyMissingApp:
    """ASGI fallback used when python-socketio is not installed locally."""

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        """Return a clear dependency error instead of breaking FastAPI startup."""
        if scope["type"] != "http":
            await send({"type": "websocket.close", "code": 1013})
            return
        body = b"python-socketio is required for /ws/socket.io"
        await send(
            {
                "type": "http.response.start",
                "status": 503,
                "headers": [(b"content-type", b"text/plain; charset=utf-8")],
            }
        )
        await send({"type": "http.response.body", "body": body})


if find_spec("socketio") is not None:
    import socketio

    sio = socketio.AsyncServer(
        async_mode="asgi",
        cors_allowed_origins="*",
        logger=False,
        engineio_logger=False,
    )
    socket_app = socketio.ASGIApp(sio, socketio_path="socket.io")

    @sio.event
    async def connect(sid: str, environ: dict, auth: dict | None = None) -> None:
        """Acknowledge Socket.IO client connections."""
        await sio.emit("customer:ready", {"sid": sid}, to=sid)

    @sio.event
    async def disconnect(sid: str) -> None:
        """Handle Socket.IO client disconnects."""

    @sio.on("customer:message")
    async def handle_customer_message(sid: str, data: dict) -> None:
        """Receive a customer message and emit a RAG-grounded answer."""
        try:
            request = CustomerChatRequest.model_validate(data)
            response = customer_service_rag.answer(
                message=request.message,
                tenant_id=request.tenant_id,
                session_id=request.session_id or sid,
                top_k=request.top_k,
            )
            await sio.emit("customer:answer", response.model_dump(), to=sid)
        except Exception as exc:
            await sio.emit(
                "customer:error",
                {"message": "客服消息处理失败", "detail": str(exc)},
                to=sid,
            )
else:
    socket_app = SocketIODependencyMissingApp()
