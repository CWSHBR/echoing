import base64
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import FastAPI, Request


app = FastAPI(title="Echoing API", description="Expose all request details for debugging.")


def _normalize_scope(scope: Dict[str, Any]) -> Dict[str, Any]:
	"""Extract serialisable values from ASGI scope."""
	serialisable: Dict[str, Any] = {}
	for key, value in scope.items():
		if key in {"headers", "raw_headers", "app", "router", "endpoint", "state"}:
			# These keys contain non-serialisable or redundant data.
			continue
		if isinstance(value, (str, int, float, bool)) or value is None:
			serialisable[key] = value
		elif isinstance(value, (list, tuple)):
			# Preserve simple sequences when possible.
			if all(isinstance(item, (str, int, float, bool, type(None))) for item in value):
				serialisable[key] = list(value)
	return serialisable


def _headers_to_list(headers: Any) -> List[Dict[str, str]]:
	"""Represent headers as a list to keep duplicate header names."""

	def _to_str(value: Any) -> str:
		if isinstance(value, bytes):
			return value.decode("latin-1", errors="replace")
		return str(value)

	items: Iterable[Tuple[Any, Any]]
	if hasattr(headers, "raw"):
		items = headers.raw  # type: ignore[attr-defined]
	elif hasattr(headers, "multi_items"):
		items = headers.multi_items()  # type: ignore[attr-defined]
	elif hasattr(headers, "items"):
		items = headers.items()
	else:
		items = []

	return [{"name": _to_str(name), "value": _to_str(value)} for name, value in items]


@app.api_route(
	"/",
	methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def echo(request: Request) -> Dict[str, Any]:
	raw_body: bytes = await request.body()
	body_text: Optional[str] = None
	if raw_body:
		try:
			body_text = raw_body.decode(request.headers.get("content-type", "utf-8"), errors="replace")
		except LookupError:
			body_text = raw_body.decode("utf-8", errors="replace")

	json_payload: Any = None
	if raw_body:
		try:
			json_payload = await request.json()
		except Exception:  # noqa: BLE001 - surface best-effort JSON info.
			json_payload = None

	body_base64 = base64.b64encode(raw_body).decode("ascii") if raw_body else None

	query_params: List[Tuple[str, str]] = list(request.query_params.multi_items())

	client_host, client_port = (request.client.host, request.client.port) if request.client else (None, None)
	server_host, server_port = (request.scope.get("server") or (None, None))

	return {
		"method": request.method,
		"http_version": request.scope.get("http_version"),
		"scheme": request.scope.get("scheme"),
		"url": str(request.url),
		"base_url": str(request.base_url),
		"path": request.url.path,
		"path_params": request.path_params,
		"query_string": request.scope.get("query_string", b"").decode("latin-1") if isinstance(request.scope.get("query_string"), bytes) else request.scope.get("query_string"),
		"query_params": query_params,
		"headers": _headers_to_list(request.headers),
		"cookies": request.cookies,
		"client": {"host": client_host, "port": client_port},
		"server": {"host": server_host, "port": server_port},
		"body": {
			"text": body_text,
			"base64": body_base64,
			"length": len(raw_body),
		},
		"json": json_payload,
		"scope": _normalize_scope(request.scope),
	}
