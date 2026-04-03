"""
GatheringAdapter ABC — base class for all gathering source adapters.

The system is source-agnostic. The DB stores opaque JSONB filters.
Each adapter owns its filter schema and execution logic.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Type, Callable, Any
from pydantic import BaseModel


@dataclass
class EstimateResult:
    estimated_companies: int = 0
    estimated_credits: int = 0
    estimated_cost_usd: float = 0.0
    notes: str = ""


@dataclass
class GatheringResult:
    """Standard result from adapter execution."""
    companies: list[dict] = field(default_factory=list)
    raw_results_count: int = 0
    credits_used: int = 0
    cost_usd: float = 0.0
    error_message: str = ""
    metadata: dict = field(default_factory=dict)


class GatheringAdapter(ABC):
    """Base class for all gathering source adapters."""

    source_type: str = ""
    source_label: str = ""
    filter_model: Optional[Type[BaseModel]] = None

    @abstractmethod
    async def validate(self, raw_filters: dict) -> dict:
        """Validate & normalize filters. Returns cleaned dict. Raises on invalid."""

    @abstractmethod
    async def estimate(self, filters: dict) -> EstimateResult:
        """Estimate cost/results without executing."""

    @abstractmethod
    async def execute(self, filters: dict, on_progress: Optional[Callable] = None) -> GatheringResult:
        """Execute gathering. Returns companies list + metadata."""

    def get_filter_schema(self) -> Optional[dict]:
        """JSON Schema for MCP tool registration."""
        if self.filter_model:
            return self.filter_model.model_json_schema()
        return None

    def get_capabilities(self) -> dict:
        """What this adapter can do. Used by UI and MCP for discovery."""
        return {
            "source_type": self.source_type,
            "source_label": self.source_label,
            "has_estimate": True,
            "has_filter_schema": self.filter_model is not None,
            "cost_model": "free",
            "requires_auth": False,
            "filter_schema": self.get_filter_schema(),
        }
