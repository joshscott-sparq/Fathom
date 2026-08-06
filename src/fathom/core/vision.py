"""Vision extraction for dropped images (spec §3.1 ingest, image inputs).

An architecture image can't be read deterministically, so this uses Claude vision
when an ANTHROPIC_API_KEY is present. Consistent with the engine's LLM-optional
posture: if there is no key (or the call fails), it returns a clear placeholder
noting the image was received and that interpretation needs the API key, rather
than raising. The returned markdown flows into the PRD/context field for review.
"""

from __future__ import annotations

import base64
import os

# Model used for image interpretation. Latest Claude vision-capable model.
_VISION_MODEL = "claude-sonnet-5"

_ARCH_PROMPT = (
    "This image is either a set of software requirements or a software architecture "
    "diagram. Transcribe it into clean markdown. If it is an architecture diagram, "
    "list each component (name and inferred type: service, datastore, UI, pipeline, "
    "ML model, gateway, queue, integration, external system) and the connections "
    "between them as 'A -> B: label'. If it is requirements, list them as bullets. "
    "Be faithful to the image; do not invent detail."
)


def describe_image(raw: bytes, media_type: str) -> str:
    """Return a markdown transcription of an image via Claude vision.

    Falls back to a placeholder note when no API key is configured or the call
    fails, so the drop flow never hard-fails on an image.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return (
            "> Image received but not interpreted: set ANTHROPIC_API_KEY to enable "
            "vision extraction of architecture diagrams and requirement images.\n"
        )
    try:
        import anthropic

        client = anthropic.Anthropic()
        message = client.messages.create(
            model=_VISION_MODEL,
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64.standard_b64encode(raw).decode("ascii"),
                            },
                        },
                        {"type": "text", "text": _ARCH_PROMPT},
                    ],
                }
            ],
        )
        parts = [block.text for block in message.content if getattr(block, "type", None) == "text"]
        return "\n".join(parts).strip() or "> Vision returned no text."
    except Exception as exc:  # noqa: BLE001
        return f"> Image received but vision extraction failed: {exc}\n"
