from __future__ import annotations

import json
import os
import time
from typing import Any

import requests

from collector.llm.base import ReviewProvider
from collector.llm.schema import review_schema
from collector.models import ArticleCandidate


class OpenAIReviewProvider(ReviewProvider):
    """Review articles through OpenAI or an OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_style: str | None = None,
        structured_output: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5-mini")
        self.base_url = (
            base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        ).rstrip("/")
        self.api_style = (
            api_style or os.getenv("OPENAI_API_STYLE", "auto")
        ).strip().lower().replace("-", "_")
        self.structured_output = (
            structured_output or os.getenv("OPENAI_STRUCTURED_OUTPUT", "auto")
        ).strip().lower()
        default_timeout = max(30, int(os.getenv("REQUEST_TIMEOUT_SECONDS", "15")) * 4)
        self.timeout = max(
            10, int(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", str(default_timeout)))
        )
        self.max_retries = max(1, int(os.getenv("LLM_MAX_RETRIES", "2")))
        self.enable_thinking = os.getenv("OPENAI_ENABLE_THINKING", "").strip().lower()
        self.reasoning_effort = os.getenv("OPENAI_REASONING_EFFORT", "").strip().lower()
        self._resolved_api_style: str | None = None

    @property
    def available(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def _api_styles(self) -> list[str]:
        if self._resolved_api_style:
            return [self._resolved_api_style]
        if self.api_style in {"chat", "chat_completions"}:
            return ["chat_completions"]
        if self.api_style == "responses":
            return ["responses"]
        if self.api_style != "auto":
            raise ValueError(
                "OPENAI_API_STYLE must be auto, responses, or chat_completions"
            )
        if self.base_url.startswith("https://api.openai.com/"):
            return ["responses", "chat_completions"]
        return ["chat_completions", "responses"]

    def _structured_variants(self) -> list[bool]:
        if self.structured_output in {"1", "true", "yes", "on"}:
            return [True]
        if self.structured_output in {"0", "false", "no", "off"}:
            return [False]
        if self.structured_output != "auto":
            raise ValueError("OPENAI_STRUCTURED_OUTPUT must be auto, true, or false")
        # Many compatible services implement JSON text but not json_schema.
        return [True, False]

    def _endpoint(self, style: str) -> str:
        suffix = "responses" if style == "responses" else "chat/completions"
        return f"{self.base_url}/{suffix}"

    @staticmethod
    def _responses_output_text(payload: dict[str, Any]) -> str:
        if isinstance(payload.get("output_text"), str) and payload["output_text"]:
            return payload["output_text"]
        for item in payload.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    return content["text"]
        raise ValueError("Responses API result did not contain output_text")

    @staticmethod
    def _chat_output_text(payload: dict[str, Any]) -> str:
        choices = payload.get("choices", [])
        if not choices:
            raise ValueError("Chat Completions result did not contain choices")
        content = choices[0].get("message", {}).get("content", "")
        if isinstance(content, str) and content:
            return content
        if isinstance(content, list):
            text = "".join(
                str(item.get("text", ""))
                for item in content
                if isinstance(item, dict) and item.get("type") in {"text", "output_text"}
            )
            if text:
                return text
        raise ValueError("Chat Completions result did not contain message content")

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            if start < 0:
                raise
            parsed, _ = json.JSONDecoder().raw_decode(cleaned[start:])
        if not isinstance(parsed, dict):
            raise ValueError("LLM review must be a JSON object")
        return parsed

    def _request_body(
        self,
        style: str,
        system: str,
        user: str,
        schema: dict[str, Any],
        structured: bool,
    ) -> dict[str, Any]:
        schema_instruction = (
            "返回结果必须严格符合下面的 JSON Schema；所有 required 字段都必须出现，"
            "不要增加 schema 之外的字段：\n"
            + json.dumps(schema, ensure_ascii=False)
        )
        effective_system = (
            system if structured else system + "\n\n" + schema_instruction
        )
        messages = [{"role": "system", "content": effective_system}]
        messages.append({"role": "user", "content": user})
        if style == "responses":
            body: dict[str, Any] = {
                "model": self.model,
                "input": messages,
                "max_output_tokens": 2400,
            }
            if structured:
                body["text"] = {
                    "format": {
                        "type": "json_schema",
                        "name": "signal_radar_review",
                        "strict": True,
                        "schema": schema,
                    }
                }
            return body

        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 2400,
        }
        if self.enable_thinking in {"1", "true", "yes", "on"}:
            body["enable_thinking"] = True
        elif self.enable_thinking in {"0", "false", "no", "off"}:
            body["enable_thinking"] = False
        if self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort
        if structured:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "signal_radar_review",
                    "strict": True,
                    "schema": schema,
                },
            }
        return body

    def review(
        self,
        candidate: ArticleCandidate,
        category: str,
        weights: dict[str, int],
        pre_score: float,
    ) -> dict[str, Any]:
        if not self.available:
            raise RuntimeError("OPENAI_API_KEY, OPENAI_BASE_URL, or OPENAI_MODEL is missing")

        source_text = candidate.content or candidate.snippet or "正文不可用，仅基于元数据判断。"
        system = (
            "你是 Signal Radar 的严谨信息分析师。目标是提高推荐精度，而不是迎合作者。"
            "请用中文提炼独立观点，明确局限与隐藏假设，并按给定 rubric 的每个维度打 0 到 5 分。"
            "如果原文不是中文，translationZh 应提供最多 600 至 1200 字的核心内容中文译文，保留关键事实、论证关系和术语；"
            "原文信息不足 600 字时只翻译已有内容，绝不为达到字数而扩写；"
            "它不是逐段全文翻译，不得添加原文没有的事实。如果原文是中文，translationZh 返回空字符串。"
            "不要复述标题，不要虚构正文中没有的事实。只返回一个 JSON 对象，不要使用 Markdown 代码块。"
        )
        user = json.dumps(
            {
                "title": candidate.title,
                "url": candidate.url,
                "source": candidate.source,
                "author": candidate.author,
                "publishedAt": candidate.published_at,
                "language": candidate.language,
                "proposedCategory": category,
                "rubricWeights": weights,
                "preRankingScore": pre_score,
                "contentAvailability": candidate.content_availability,
                "articleTextOrSnippet": source_text[:14000],
                "readerContext": "正在准备 AI 产品经理求职，并进行 AI 产品深度思考。",
            },
            ensure_ascii=False,
        )
        schema = review_schema(list(weights))
        last_error: Exception | None = None

        for style in self._api_styles():
            for structured in self._structured_variants():
                for attempt in range(self.max_retries):
                    try:
                        response = requests.post(
                            self._endpoint(style),
                            headers={
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json",
                            },
                            json=self._request_body(style, system, user, schema, structured),
                            timeout=self.timeout,
                        )
                        response.raise_for_status()
                        payload = response.json()
                        output_text = (
                            self._responses_output_text(payload)
                            if style == "responses"
                            else self._chat_output_text(payload)
                        )
                        result = self._parse_json(output_text)
                        missing = [
                            field for field in schema.get("required", []) if field not in result
                        ]
                        if missing:
                            raise ValueError(
                                "LLM review omitted required fields: " + ", ".join(missing)
                            )
                        self._resolved_api_style = style
                        return result
                    except (requests.RequestException, json.JSONDecodeError, ValueError) as exc:
                        last_error = exc
                        status = getattr(getattr(exc, "response", None), "status_code", None)
                        if status in {401, 403}:
                            raise RuntimeError(
                                "LLM API rejected the configured API key"
                            ) from exc
                        if status in {400, 404, 405, 415, 422}:
                            break
                        if attempt < self.max_retries - 1:
                            time.sleep(2**attempt)

        raise RuntimeError(f"OpenAI-compatible review failed: {last_error}")

    def translate_to_chinese(self, candidate: ArticleCandidate) -> str:
        """Generate a focused Chinese translation for a selected foreign article."""
        if not self.available:
            raise RuntimeError("LLM API configuration is incomplete")
        source_text = candidate.content or candidate.snippet
        if not source_text.strip():
            raise ValueError("Article text is unavailable for translation")

        messages = [
            {
                "role": "system",
                "content": (
                    "你是严谨的专业翻译。请将文章核心内容翻译为中文，保留事实、论证关系、"
                    "专有名词和重要限定条件，不评论、不扩写、不使用 Markdown 代码块。"
                    "原文较长时控制在 600 至 1200 个中文字符；原文较短时只翻译已有内容。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"title": candidate.title, "articleText": source_text[:14000]},
                    ensure_ascii=False,
                ),
            },
        ]
        last_error: Exception | None = None
        for style in self._api_styles():
            for attempt in range(self.max_retries):
                try:
                    if style == "responses":
                        body: dict[str, Any] = {
                            "model": self.model,
                            "input": messages,
                            "max_output_tokens": 1800,
                        }
                    else:
                        body = {
                            "model": self.model,
                            "messages": messages,
                            "max_tokens": 1800,
                        }
                        if self.enable_thinking in {"1", "true", "yes", "on"}:
                            body["enable_thinking"] = True
                        elif self.enable_thinking in {"0", "false", "no", "off"}:
                            body["enable_thinking"] = False
                        if self.reasoning_effort:
                            body["reasoning_effort"] = self.reasoning_effort

                    response = requests.post(
                        self._endpoint(style),
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=body,
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
                    payload = response.json()
                    text = (
                        self._responses_output_text(payload)
                        if style == "responses"
                        else self._chat_output_text(payload)
                    ).strip()
                    if not text:
                        raise ValueError("Translation response was empty")
                    self._resolved_api_style = style
                    return text
                except (requests.RequestException, ValueError) as exc:
                    last_error = exc
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    if status in {401, 403}:
                        raise RuntimeError("LLM API rejected the configured API key") from exc
                    if attempt < self.max_retries - 1:
                        time.sleep(2**attempt)
        raise RuntimeError(f"Translation failed: {last_error}")
