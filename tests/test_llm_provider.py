from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from collector.llm import OpenAIReviewProvider  # noqa: E402
from collector.models import ArticleCandidate  # noqa: E402


class CompatibleApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.candidate = ArticleCandidate(
            id="article-1",
            title="A useful product essay",
            url="https://example.com/article",
            source="Example",
            language="en",
            snippet="A short source excerpt.",
        )

    @staticmethod
    def _response(payload: dict) -> Mock:
        response = Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = payload
        return response

    @staticmethod
    def _review(summary: str) -> dict:
        return {
            "category": "product-insight",
            "titleZh": "测试标题",
            "summaryZh": summary,
            "translationZh": "测试译文",
            "keyIdeas": ["观点一", "观点二"],
            "counterPoint": "测试质疑",
            "whyForMe": "测试价值",
            "topics": ["测试主题"],
            "importantTerms": [],
            "scores": {"impact": 4},
        }

    @patch("collector.llm.openai_provider.requests.post")
    def test_third_party_auto_uses_chat_completions(self, post: Mock) -> None:
        post.return_value = self._response(
            {
                "choices": [
                    {"message": {"content": json.dumps(self._review("测试摘要"))}}
                ]
            }
        )
        provider = OpenAIReviewProvider(
            api_key="third-party-key",
            model="vendor-model",
            base_url="https://llm.vendor.example/v1",
            api_style="auto",
            structured_output="false",
        )

        result = provider.review(self.candidate, "product-insight", {"impact": 100}, 80)

        self.assertEqual(result["summaryZh"], "测试摘要")
        self.assertEqual(
            post.call_args.args[0],
            "https://llm.vendor.example/v1/chat/completions",
        )
        self.assertNotIn("response_format", post.call_args.kwargs["json"])

    @patch("collector.llm.openai_provider.requests.post")
    def test_official_auto_uses_responses(self, post: Mock) -> None:
        post.return_value = self._response(
            {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(self._review("官方接口摘要")),
                            }
                        ],
                    }
                ]
            }
        )
        provider = OpenAIReviewProvider(
            api_key="openai-key",
            model="gpt-test",
            base_url="https://api.openai.com/v1",
            api_style="auto",
            structured_output="true",
        )

        result = provider.review(self.candidate, "product-insight", {"impact": 100}, 80)

        self.assertEqual(result["summaryZh"], "官方接口摘要")
        self.assertEqual(
            post.call_args.args[0],
            "https://api.openai.com/v1/responses",
        )
        self.assertIn("text", post.call_args.kwargs["json"])

    def test_markdown_wrapped_json_is_accepted(self) -> None:
        parsed = OpenAIReviewProvider._parse_json(
            '```json\n{"summaryZh": "兼容返回"}\n```'
        )
        self.assertEqual(parsed["summaryZh"], "兼容返回")


if __name__ == "__main__":
    unittest.main()
