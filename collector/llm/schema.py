from __future__ import annotations


def review_schema(score_dimensions: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": ["ai-news", "product-insight", "career", "other"]},
            "titleZh": {"type": "string"},
            "summaryZh": {"type": "string"},
            "translationZh": {"type": "string"},
            "keyIdeas": {
                "type": "array",
                "minItems": 2,
                "maxItems": 5,
                "items": {"type": "string"},
            },
            "counterPoint": {"type": "string"},
            "whyForMe": {"type": "string"},
            "topics": {"type": "array", "minItems": 1, "maxItems": 6, "items": {"type": "string"}},
            "importantTerms": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {"term": {"type": "string"}, "explanationZh": {"type": "string"}},
                    "required": ["term", "explanationZh"],
                    "additionalProperties": False,
                },
            },
            "scores": {
                "type": "object",
                "properties": {dimension: {"type": "number", "minimum": 0, "maximum": 5} for dimension in score_dimensions},
                "required": score_dimensions,
                "additionalProperties": False,
            },
        },
        "required": [
            "category",
            "titleZh",
            "summaryZh",
            "translationZh",
            "keyIdeas",
            "counterPoint",
            "whyForMe",
            "topics",
            "importantTerms",
            "scores",
        ],
        "additionalProperties": False,
    }
