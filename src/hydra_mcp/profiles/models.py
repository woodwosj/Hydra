"""Profile models for Hydra agent definitions."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ChecklistItem(BaseModel):
    """Represents a checklist step that an agent should complete."""

    id: str = Field(..., description="Stable identifier for the checklist item.")
    description: str = Field(..., description="Human-friendly description of the action.")
    required: bool = Field(
        default=True,
        description="Whether the agent must complete this item before finishing.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata to aid filtering or reporting.",
    )

    @field_validator("id")
    @classmethod
    def _normalize_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Checklist item id must not be empty")
        return normalized


class AgentProfile(BaseModel):
    """Configuration describing how Hydra should prime an agent."""

    id: str = Field(..., description="Unique identifier for the profile.")
    title: str = Field(..., description="Display title for the agent profile.")
    persona: str = Field(..., description="Narrative framing for the agent's tone and role.")
    system_prompt: str = Field(
        ...,
        description="System-level instructions presented to Codex when spawning this agent.",
    )
    goalset: list[str] = Field(
        default_factory=list,
        description="Ordered list of high-level goals this agent must achieve.",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Constraints or guardrails imposed on the agent.",
    )
    checklist_template: list[ChecklistItem] = Field(
        default_factory=list,
        description="Template describing required checklist items for the agent run.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary metadata to attach to runs for search and filtering.",
    )

    @field_validator("id")
    @classmethod
    def _normalize_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Agent profile id must not be empty")
        return normalized

    @field_validator("goalset", "constraints", mode="before")
    @classmethod
    def _ensure_list(cls, value: Any):  # type: ignore[override]
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return list(value)
        raise TypeError("Goalset and constraints must be sequences of strings")


__all__ = ["AgentProfile", "ChecklistItem"]
