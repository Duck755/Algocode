from __future__ import annotations

import json
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class MockOpenAIServer:
    def __init__(self) -> None:
        self.responses: deque[tuple[int, str, str]] = deque()
        self.requests: list[dict[str, Any]] = []
        self.headers: list[dict[str, str]] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                server.requests.append(payload)
                server.headers.append(dict(self.headers))
                status, content_type, body = server.responses.popleft()
                encoded = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, format: str, *args: object) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def __enter__(self) -> MockOpenAIServer:
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def enqueue_sse(self, chunks: list[dict[str, Any]]) -> None:
        lines = [f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n" for chunk in chunks]
        lines.append("data: [DONE]\n\n")
        self.responses.append((200, "text/event-stream", "".join(lines)))

    def enqueue_tool_call(
        self,
        call_id: str,
        name: str,
        arguments: dict[str, Any],
    ) -> None:
        self.enqueue_sse([_tool_call_chunk(call_id, name, arguments)])

    def enqueue_text(self, text: str) -> None:
        self.enqueue_sse(
            [
                {
                    "id": "text",
                    "choices": [{"delta": {"content": text}, "finish_reason": "stop"}],
                }
            ]
        )

    def enqueue_json(self, status: int, payload: dict[str, Any]) -> None:
        self.responses.append((status, "application/json", json.dumps(payload, ensure_ascii=False)))


def _tool_call_chunk(
    call_id: str,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": "tool-call",
        "choices": [
            {
                "delta": {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": call_id,
                            "function": {
                                "name": name,
                                "arguments": json.dumps(arguments, ensure_ascii=False),
                            },
                        }
                    ]
                },
                "finish_reason": "tool_calls",
            }
        ],
    }
