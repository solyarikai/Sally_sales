"""Shared test fixtures for MCP pipeline tests."""
import json
import os
import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Test data paths
TEST_DATA_DIR = Path(__file__).parent / "test_data"
TEST_CSV_PATH = TEST_DATA_DIR / "test_csv_source.csv"
TEST_SHEET_CSV_PATH = TEST_DATA_DIR / "test_sheet_source.csv"
TEST_DRIVE_DIR = TEST_DATA_DIR / "drive_folder"
TEST_METADATA_PATH = TEST_DATA_DIR / "test_metadata.json"


@pytest.fixture
def test_metadata():
    with open(TEST_METADATA_PATH) as f:
        return json.load(f)


@pytest.fixture
def csv_domains(test_metadata):
    return set(test_metadata["csv_test"]["domains"])


@pytest.fixture
def sheet_domains(test_metadata):
    return set(test_metadata["sheet_test"]["domains"])


@pytest.fixture
def drive_domains(test_metadata):
    return set(test_metadata["drive_test"]["unique_domains"])


@pytest.fixture
def overlap_csv_sheet(test_metadata):
    return set(test_metadata["overlaps"]["csv_sheet"])


@pytest.fixture
def overlap_csv_drive(test_metadata):
    return set(test_metadata["overlaps"]["csv_drive"])


@pytest.fixture
def overlap_sheet_drive(test_metadata):
    return set(test_metadata["overlaps"]["sheet_drive"])


class FakeSession:
    """Minimal async session mock for adapter-level tests (no DB)."""

    def __init__(self):
        self.added = []
        self.flushed = False
        self._discovered = {}  # domain -> DiscoveredCompany-like dict

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushed = True

    async def execute(self, stmt):
        return FakeResult(None)

    async def get(self, model, pk):
        return None


class FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return FakeScalars(self._value)

    def all(self):
        return []


class FakeScalars:
    def __init__(self, value):
        self._value = value

    def all(self):
        return [self._value] if self._value else []


@pytest.fixture
def fake_session():
    return FakeSession()
