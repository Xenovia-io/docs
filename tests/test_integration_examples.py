"""Execute the guides' Python snippets against in-memory HTTP fixtures."""

import io
import json
import os
import re
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import httpx
from langchain_core.embeddings import FakeEmbeddings
from langchain_openai import ChatOpenAI
from llama_index.llms.openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
ENV = {
    "XENOVIA_API_KEY": "fixture-only",
    "XENOVIA_PROXY_ID": "fixture-proxy",
    "OPENAI_API_KEY": "fixture-only",
}


def snippets(page, section):
    text = (ROOT / "integrations" / f"{page}.mdx").read_text()
    body = text.split(f"## {section}\n", 1)[1].split("\n## ", 1)[0]
    return [
        textwrap.dedent(code)
        for code in re.findall(r" *```python\n(.*?) *```", body, re.DOTALL)
    ]


def execute(code, namespace):
    with redirect_stdout(io.StringIO()):
        exec(compile(code, "<documentation example>", "exec"), namespace)  # noqa: S102 - execute checked-in guide snippets


def causes(error):
    while error is not None:
        yield error
        error = error.__cause__


class BrokenStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b'data: {"id":"fixture","object":"chat.completion.chunk","created":1,"model":"gpt-4o-mini","choices":[{"index":0,"delta":{"role":"assistant","content":"Partial"},"finish_reason":null}]}\n\n'
        raise httpx.ReadError("fixture interrupted stream")


class Endpoint:
    def __init__(self):
        self.requests = []
        self.mode = "allow"

    def handle(self, request):
        body = json.loads(request.content)
        self.requests.append((request, body))
        if self.mode in ("block", "server_error"):
            status = 403 if self.mode == "block" else 500
            return httpx.Response(
                status,
                json={"error": {"message": "fixture policy or server error"}},
                headers={"X-Xenovia-Trace-Id": "fixture-trace"},
            )
        if self.mode == "broken_stream":
            return httpx.Response(
                200,
                headers={"Content-Type": "text/event-stream"},
                stream=BrokenStream(),
            )
        tools = body.get("tools", [])
        has_result = any(message["role"] == "tool" for message in body["messages"])
        if tools and not has_result:
            name = tools[0]["function"]["name"]
            arguments = {
                "input" if name == "docs_search" else "query": "governance policies"
            }
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_fixture",
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(arguments)},
                    }
                ],
            }
            finish = "tool_calls"
        else:
            message = {"role": "assistant", "content": "Xenovia governs model calls."}
            finish = "stop"
        envelope = {"id": "fixture", "created": 1, "model": "gpt-4o-mini"}
        if body.get("stream"):
            if "tool_calls" in message:
                message["tool_calls"][0]["index"] = 0
            chunks = [
                {
                    **envelope,
                    "object": "chat.completion.chunk",
                    "choices": [{"index": 0, "delta": message, "finish_reason": None}],
                },
                {
                    **envelope,
                    "object": "chat.completion.chunk",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
                },
            ]
            content = (
                "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)
                + "data: [DONE]\n\n"
            )
            return httpx.Response(
                200, headers={"Content-Type": "text/event-stream"}, content=content
            )
        return httpx.Response(
            200,
            json={
                **envelope,
                "object": "chat.completion",
                "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            },
        )


class QueryEngine:
    def __init__(self):
        self.queries = []

    async def aquery(self, query):
        self.queries.append(query)
        return "Governance policy documentation."


class LlamaIndexExamples(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.endpoint = Endpoint()
        self.client = httpx.AsyncClient(
            transport=httpx.MockTransport(self.endpoint.handle)
        )
        self.engine = QueryEngine()
        self.namespace = {"__name__": "docs_example", "query_engine": self.engine}

        def make_llm(**kwargs):
            return OpenAI(**kwargs, async_http_client=self.client, max_retries=0)

        with (
            patch.dict(os.environ, ENV),
            patch("llama_index.llms.openai.OpenAI", side_effect=make_llm),
        ):
            execute(snippets("llamaindex", "Setup")[0], self.namespace)
        execute(snippets("llamaindex", "Agentic query engine")[0], self.namespace)
        execute(snippets("llamaindex", "Handling policy blocks")[1], self.namespace)

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_native_query_tool_round_trip_and_session(self):
        result = await self.namespace["run_with_policy_handling"](
            "Find governance policies"
        )
        self.assertIn("Xenovia", str(result))
        self.assertEqual(self.engine.queries, ["governance policies"])
        self.assertEqual(len(self.endpoint.requests), 2)
        for request, body in self.endpoint.requests:
            self.assertEqual(request.url.path, "/fixture-proxy/v1/chat/completions")
            self.assertEqual(
                request.headers["X-Xenovia-Session-Id"], self.namespace["session_id"]
            )
            self.assertEqual(body["tools"][0]["function"]["name"], "docs_search")
        self.assertTrue(
            any(
                message["role"] == "tool"
                for message in self.endpoint.requests[1][1]["messages"]
            )
        )

    async def test_agent_script_entry_point(self):
        with redirect_stdout(io.StringIO()) as output:
            await self.namespace["main"]()
        self.assertIn("Xenovia", output.getvalue())

    async def test_policy_block_is_handled_without_running_tool(self):
        self.endpoint.mode = "block"
        with redirect_stdout(io.StringIO()) as output:
            result = await self.namespace["run_with_policy_handling"](
                "Find governance policies"
            )
        self.assertIsNone(result)
        self.assertIn("Blocked by policy", output.getvalue())
        self.assertIn("fixture-trace", output.getvalue())
        self.assertEqual(self.engine.queries, [])

    async def test_unrelated_server_error_is_reraised(self):
        self.endpoint.mode = "server_error"
        with self.assertRaises(Exception) as caught:
            await self.namespace["run_with_policy_handling"]("Find governance policies")
        self.assertTrue(
            any(
                getattr(error, "status_code", None) == 500
                for error in causes(caught.exception)
            )
        )
        self.assertEqual(self.engine.queries, [])

    async def test_interrupted_stream_is_not_reported_as_policy_block(self):
        self.endpoint.mode = "broken_stream"
        with (
            redirect_stdout(io.StringIO()) as output,
            self.assertRaises(Exception) as caught,
        ):
            await self.namespace["run_with_policy_handling"]("Find governance policies")
        self.assertTrue(
            any(
                isinstance(error, httpx.ReadError) for error in causes(caught.exception)
            )
        )
        self.assertNotIn("Blocked by policy", output.getvalue())
        self.assertEqual(self.engine.queries, [])


class LangChainExamples(unittest.TestCase):
    def setUp(self):
        self.endpoint = Endpoint()
        self.client = httpx.Client(transport=httpx.MockTransport(self.endpoint.handle))
        self.namespace = {"__name__": "docs_example"}

        def make_llm(**kwargs):
            return ChatOpenAI(**kwargs, http_client=self.client, max_retries=0)

        with (
            patch.dict(os.environ, ENV),
            patch("langchain_openai.ChatOpenAI", side_effect=make_llm),
        ):
            execute(snippets("langchain", "Setup")[0], self.namespace)

    def tearDown(self):
        self.client.close()

    def test_native_tool_round_trip_and_session(self):
        execute(snippets("langchain", "Agents with tools")[0], self.namespace)
        self.assertIn("Xenovia", self.namespace["result"]["messages"][-1].content)
        self.assertEqual(len(self.endpoint.requests), 2)
        for request, body in self.endpoint.requests:
            self.assertEqual(request.url.path, "/fixture-proxy/v1/chat/completions")
            self.assertEqual(
                request.headers["X-Xenovia-Session-Id"], self.namespace["session_id"]
            )
            self.assertEqual(body["tools"][0]["function"]["name"], "search")
        self.assertTrue(
            any(
                message["role"] == "tool"
                for message in self.endpoint.requests[1][1]["messages"]
            )
        )

    def test_policy_block_handler_reports_trace(self):
        execute(snippets("langchain", "Agents with tools")[0], self.namespace)
        self.endpoint.requests.clear()
        self.endpoint.mode = "block"
        with redirect_stdout(io.StringIO()) as output:
            exec(snippets("langchain", "Handling policy blocks")[0], self.namespace)  # noqa: S102 - checked-in snippet
        self.assertIn("Blocked by policy", output.getvalue())
        self.assertIn("fixture-trace", output.getvalue())
        self.assertEqual(len(self.endpoint.requests), 1)

    def test_rag_prompt_receives_context_and_question(self):
        with (
            patch.dict(os.environ, ENV),
            patch(
                "langchain_openai.OpenAIEmbeddings", return_value=FakeEmbeddings(size=8)
            ),
        ):
            execute(snippets("langchain", "RAG pipeline")[0], self.namespace)
        self.assertIn("Xenovia", self.namespace["answer"])
        messages = self.endpoint.requests[-1][1]["messages"]
        self.assertIn("runtime governance", messages[0]["content"])
        self.assertEqual(messages[1]["content"], "What does Xenovia provide?")


if __name__ == "__main__":
    unittest.main()
