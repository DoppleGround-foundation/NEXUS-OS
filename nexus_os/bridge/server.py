"""Bridge JSON-RPC server with proper error propagation.

Replaces bare ``except: pass`` blocks with structured ``BridgeError``
variants so callers always know why a request failed.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from nexus_os.exceptions import (
    AuthenticationFailed,
    BridgeError,
    RPCError,
    SecretNotFound,
)

logger = logging.getLogger(__name__)

# Standard JSON-RPC 2.0 error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Nexus-specific error codes
KAIJU_DENIED_CODE = -33001
AUTH_FAILED_CODE = -33002
BUDGET_EXCEEDED_CODE = -33003


@dataclass(frozen=True)
class RPCRequest:
    method: str
    params: dict[str, Any] | list[Any]
    request_id: str | int | None = None
    jsonrpc: str = "2.0"


@dataclass(frozen=True)
class RPCResponse:
    result: Any = None
    error: dict[str, Any] | None = None
    request_id: str | int | None = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"jsonrpc": self.jsonrpc, "id": self.request_id}
        if self.error is not None:
            d["error"] = self.error
        else:
            d["result"] = self.result
        return d


class SecretsManager:
    """Per-provider secrets management with health logging.

    Raises ``SecretNotFound`` instead of silently returning ``None``.
    """

    def __init__(self) -> None:
        self._secrets: dict[str, str] = {}
        self._health: dict[str, dict[str, Any]] = {}

    def set_secret(self, provider: str, secret: str) -> None:
        self._secrets[provider] = secret
        self._health[provider] = {"set_at": time.time(), "last_used": None}

    def get_secret(self, provider: str) -> str:
        secret = self._secrets.get(provider)
        if secret is None:
            raise SecretNotFound(
                f"No secret configured for provider {provider!r}",
                details={"provider": provider, "available": list(self._secrets)},
            )
        self._health[provider]["last_used"] = time.time()
        return secret

    def provider_health(self) -> dict[str, dict[str, Any]]:
        return dict(self._health)


class BridgeServer:
    """JSON-RPC 2.0 governance server.

    Dispatches incoming requests to registered handlers, wrapping all
    errors in proper JSON-RPC error responses.  Internal exceptions are
    never swallowed — they are logged and converted to structured
    error payloads.
    """

    def __init__(
        self,
        *,
        kaiju_gate: Any | None = None,
        secrets: SecretsManager | None = None,
    ) -> None:
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._kaiju = kaiju_gate
        self._secrets = secrets or SecretsManager()

    def register_method(self, name: str, handler: Callable[..., Any]) -> None:
        if name in self._handlers:
            logger.warning("Overwriting handler for method %r", name)
        self._handlers[name] = handler

    def handle_raw(self, raw_payload: str | bytes) -> str:
        """Parse and handle a raw JSON-RPC payload, returning a JSON string."""
        try:
            data = json.loads(raw_payload)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.error("JSON parse error: %s", exc)
            return json.dumps(self._error_response(
                None, PARSE_ERROR, f"Parse error: {exc}",
            ))

        try:
            request = self._parse_request(data)
        except RPCError as exc:
            return json.dumps(self._error_response(
                data.get("id"), exc.details.get("rpc_code", INVALID_REQUEST), str(exc),
            ))

        response = self._dispatch(request)
        return json.dumps(response.to_dict())

    def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> Any:
        """Internal call for the executor — bypasses JSON serialization.

        Raises
        ------
        RPCError
            On method dispatch failure.
        BridgeError
            On handler execution failure.
        """
        handler = self._handlers.get(method)
        if handler is None:
            raise RPCError(
                f"Method {method!r} not found",
                rpc_code=METHOD_NOT_FOUND,
                details={"method": method, "available": list(self._handlers)},
            )

        try:
            return handler(**(params or {}))
        except BridgeError:
            raise
        except Exception as exc:
            raise BridgeError(
                f"Handler for {method!r} raised: {exc}",
                details={"method": method},
                cause=exc,
            ) from exc

    # -- internals ------------------------------------------------------------

    def _parse_request(self, data: dict[str, Any]) -> RPCRequest:
        if not isinstance(data, dict):
            raise RPCError(
                "Request must be a JSON object",
                rpc_code=INVALID_REQUEST,
            )
        method = data.get("method")
        if not method or not isinstance(method, str):
            raise RPCError(
                "Missing or invalid 'method' field",
                rpc_code=INVALID_REQUEST,
            )
        params = data.get("params", {})
        if not isinstance(params, (dict, list)):
            raise RPCError(
                "'params' must be a dict or list",
                rpc_code=INVALID_PARAMS,
            )
        return RPCRequest(
            method=method,
            params=params,
            request_id=data.get("id"),
        )

    def _dispatch(self, request: RPCRequest) -> RPCResponse:
        handler = self._handlers.get(request.method)
        if handler is None:
            return RPCResponse(
                error={"code": METHOD_NOT_FOUND, "message": f"Method {request.method!r} not found"},
                request_id=request.request_id,
            )

        try:
            if isinstance(request.params, dict):
                result = handler(**request.params)
            else:
                result = handler(*request.params)
        except AuthenticationFailed as exc:
            logger.warning("Auth failed for %s: %s", request.method, exc)
            return RPCResponse(
                error={"code": AUTH_FAILED_CODE, "message": str(exc), "data": exc.details},
                request_id=request.request_id,
            )
        except BridgeError as exc:
            logger.error("Bridge error in %s: %s", request.method, exc)
            return RPCResponse(
                error={"code": INTERNAL_ERROR, "message": str(exc), "data": exc.details},
                request_id=request.request_id,
            )
        except Exception as exc:
            logger.error(
                "Unhandled error in handler %s: %s", request.method, exc, exc_info=True,
            )
            return RPCResponse(
                error={"code": INTERNAL_ERROR, "message": f"Internal error: {type(exc).__name__}"},
                request_id=request.request_id,
            )

        return RPCResponse(result=result, request_id=request.request_id)

    @staticmethod
    def _error_response(
        request_id: Any,
        code: int,
        message: str,
    ) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }
