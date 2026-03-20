"""
Gathering Adapter Registry — self-registering adapters for TAM gathering sources.

Adding a new source:
1. Write adapter class extending GatheringAdapter
2. Decorate with @register_adapter
3. Import in this file
Done. DB unchanged. UI auto-discovers via /gathering/sources endpoint.
"""
from typing import Type
from .base import GatheringAdapter

# Global registry — adapters self-register on import
ADAPTER_REGISTRY: dict[str, Type[GatheringAdapter]] = {}


def register_adapter(cls: Type[GatheringAdapter]) -> Type[GatheringAdapter]:
    """Decorator. @register_adapter on adapter class auto-registers it."""
    ADAPTER_REGISTRY[cls.source_type] = cls
    return cls


def get_adapter(source_type: str) -> GatheringAdapter:
    """Get adapter instance by source_type string."""
    cls = ADAPTER_REGISTRY.get(source_type)
    if not cls:
        raise ValueError(f"Unknown source: {source_type}. Available: {sorted(ADAPTER_REGISTRY.keys())}")
    return cls()


def list_adapters() -> list[dict]:
    """Returns all registered adapters + capabilities. Used by /gathering/sources endpoint."""
    return [get_adapter(st).get_capabilities() for st in sorted(ADAPTER_REGISTRY.keys())]


# Import adapters to trigger registration
from . import apollo_org_api  # noqa: E402, F401
from . import apollo_people_ui  # noqa: E402, F401
from . import apollo_companies_ui  # noqa: E402, F401
from . import clay_companies  # noqa: E402, F401
from . import clay_people  # noqa: E402, F401
from . import google_sheets  # noqa: E402, F401
from . import csv_import  # noqa: E402, F401
from . import manual  # noqa: E402, F401
