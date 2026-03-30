"""Apollo Taxonomy Service — self-growing knowledge base of Apollo's filter vocabulary.

3 maps:
  - industries: 112+ known Apollo industry names (fixed list, grows via enrichment)
  - keywords: Apollo keyword tags seen on real company profiles (grows via enrichment)
  - employee_ranges: 8 fixed values

Embedding pre-filter: user query → embed → cosine similarity → top N keywords.
Scales to any map size. GPT only sees the shortlist.

Storage: JSON file cache (apollo_taxonomy_cache.json) for now.
Migration to pgvector DB table later.
"""
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx
import numpy as np

logger = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).parent.parent.parent.parent / "apollo_filters" / "apollo_taxonomy_cache.json"
EMBEDDINGS_PATH = Path(__file__).parent.parent.parent.parent / "apollo_filters" / "apollo_embeddings.npz"
TAXONOMY_PATH = Path(__file__).parent.parent.parent.parent / "apollo_filters" / "apollo_taxonomy.json"

EMPLOYEE_RANGES = [
    "1,10", "11,50", "51,200", "201,500",
    "501,1000", "1001,5000", "5001,10000", "10001,",
]


class TaxonomyService:
    """Self-growing Apollo filter vocabulary with embedding similarity search."""

    def __init__(self):
        self._cache: Dict = {"industries": {}, "keywords": {}, "employee_ranges": {}}
        self._embeddings: Dict[str, List[float]] = {}  # key -> embedding vector
        self._loaded = False

    def _load(self):
        """Load taxonomy from cache file + seed file."""
        if self._loaded:
            return

        # Load cached data (metadata only, no embeddings — those are in npz)
        if CACHE_PATH.exists():
            try:
                self._cache = json.loads(CACHE_PATH.read_text())
                logger.info(f"Loaded taxonomy cache: {len(self._cache.get('industries', {}))} industries, "
                            f"{len(self._cache.get('keywords', {}))} keywords")
            except Exception as e:
                logger.warning(f"Failed to load taxonomy cache: {e}")

        # Load embeddings from numpy file (fast, compact)
        if EMBEDDINGS_PATH.exists():
            try:
                data = np.load(EMBEDDINGS_PATH, allow_pickle=True)
                keys = data["keys"].tolist()
                vectors = data["vectors"]
                for i, key in enumerate(keys):
                    self._embeddings[key] = vectors[i].tolist()
                logger.info(f"Loaded {len(self._embeddings)} embeddings from npz")
            except Exception as e:
                logger.warning(f"Failed to load embeddings: {e}")

        # Migrate: if cache has inline embeddings, extract them
        for map_type in ("keywords", "industries"):
            for key, val in self._cache.get(map_type, {}).items():
                if val.get("embedding"):
                    self._embeddings[key] = val.pop("embedding")

        # Seed industries from static file if not in cache
        if not self._cache.get("industries") and TAXONOMY_PATH.exists():
            try:
                data = json.loads(TAXONOMY_PATH.read_text())
                for ind in data.get("industries", []):
                    if ind not in self._cache.get("industries", {}):
                        self._cache.setdefault("industries", {})[ind] = {
                            "seen_count": 0,
                            "segments": [],
                        }
                logger.info(f"Seeded {len(self._cache['industries'])} industries from taxonomy file")
            except Exception:
                pass

        # Seed employee ranges
        for r in EMPLOYEE_RANGES:
            self._cache.setdefault("employee_ranges", {})[r] = {}

        self._loaded = True
        # Save cleaned cache (without inline embeddings)
        self._save()

    def _save(self):
        """Persist cache to file (metadata only, embeddings separate)."""
        try:
            # Save metadata (small, fast)
            CACHE_PATH.write_text(json.dumps(self._cache, indent=2, default=str))
            # Save embeddings (numpy, compact)
            if self._embeddings:
                keys = list(self._embeddings.keys())
                vectors = np.array([self._embeddings[k] for k in keys], dtype=np.float32)
                np.savez_compressed(EMBEDDINGS_PATH, keys=np.array(keys), vectors=vectors)
        except Exception as e:
            logger.warning(f"Failed to save taxonomy: {e}")

    # ── Public API ──

    def get_all_industries(self) -> List[str]:
        """Return full list of known Apollo industry names."""
        self._load()
        return list(self._cache.get("industries", {}).keys())

    def get_all_keywords(self) -> List[str]:
        """Return full list of known Apollo keyword tags."""
        self._load()
        return list(self._cache.get("keywords", {}).keys())

    def get_employee_ranges(self) -> List[str]:
        """Return the 8 fixed employee ranges."""
        return EMPLOYEE_RANGES.copy()

    async def get_keyword_shortlist(
        self, query: str, openai_key: str, top_n: int = 50
    ) -> List[str]:
        """Embedding pre-filter: return top N keywords most similar to query.

        If keyword map is empty (cold start), returns empty list.
        If keyword map has <top_n entries, returns all.
        """
        self._load()
        keywords = self._cache.get("keywords", {})

        if not keywords:
            logger.info("Keyword map empty (cold start) — no shortlist available")
            return []

        if len(keywords) <= top_n:
            return list(keywords.keys())

        # Ensure all keywords have embeddings
        needs_embedding = [k for k in keywords if k not in self._embeddings]
        if needs_embedding:
            await self._compute_embeddings(needs_embedding, "keywords", openai_key)

        # Embed the query
        query_emb = await self._embed_text(query, openai_key)
        if query_emb is None:
            return list(keywords.keys())[:top_n]

        # Cosine similarity using numpy (fast)
        scored = []
        for kw in keywords:
            emb = self._embeddings.get(kw)
            if emb:
                sim = self._cosine_sim(query_emb, emb)
                scored.append((kw, sim))

        scored.sort(key=lambda x: -x[1])
        result = [kw for kw, _ in scored[:top_n]]
        logger.info(f"Keyword shortlist: {len(result)} from {len(keywords)} total "
                    f"(top sim: {scored[0][1]:.3f}, bottom: {scored[min(top_n-1, len(scored)-1)][1]:.3f})")
        return result

    def add_from_enrichment(self, enriched_org: Dict, segment: str = ""):
        """Learn from an enriched Apollo company. Grows the keyword + industry maps."""
        self._load()

        # Industry
        industry = enriched_org.get("industry")
        if industry:
            entry = self._cache.setdefault("industries", {}).setdefault(industry, {
                "seen_count": 0, "segments": [],
            })
            entry["seen_count"] = entry.get("seen_count", 0) + 1
            if segment and segment not in entry.get("segments", []):
                entry.setdefault("segments", []).append(segment)

        # Keywords
        kw_tags = enriched_org.get("keywords") or enriched_org.get("keyword_tags") or []
        if isinstance(kw_tags, str):
            kw_tags = [k.strip() for k in kw_tags.split(",")]

        new_keywords = 0
        new_kw_values = []
        for kw in kw_tags:
            kw = kw.strip().lower()
            if not kw or len(kw) < 3:
                continue
            entry = self._cache.setdefault("keywords", {}).setdefault(kw, {
                "seen_count": 0, "segments": [],
            })
            entry["seen_count"] = entry.get("seen_count", 0) + 1
            if segment and segment not in entry.get("segments", []):
                entry.setdefault("segments", []).append(segment)
            if entry["seen_count"] == 1:
                new_keywords += 1
                new_kw_values.append(kw)

        if new_keywords > 0:
            logger.info(f"Taxonomy: +{new_keywords} new keywords from enrichment (total: {len(self._cache['keywords'])})")
            # Mark that embeddings need recompute on next shortlist call
            self._needs_embedding_update = True

        self._save()
        return new_keywords

    async def rebuild_embeddings_if_needed(self, openai_key: str):
        """Compute embeddings for any keywords missing them. Call after enrichment."""
        self._load()
        needs = [k for k in self._cache.get("keywords", {}) if k not in self._embeddings]
        if not needs:
            return 0
        await self._compute_embeddings(needs, "keywords", openai_key)
        self._save()
        logger.info(f"Rebuilt embeddings for {len(needs)} new keywords")
        return len(needs)

    # ── Embedding helpers ──

    async def _embed_text(self, text: str, openai_key: str) -> Optional[List[float]]:
        """Embed a single text using OpenAI text-embedding-3-small."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                    json={"model": "text-embedding-3-small", "input": text},
                )
                data = resp.json()
                return data["data"][0]["embedding"]
        except Exception as e:
            logger.warning(f"Embedding failed for '{text[:50]}': {e}")
            return None

    async def _compute_embeddings(self, values: List[str], map_type: str, openai_key: str):
        """Batch compute embeddings for values that don't have them yet."""
        # OpenAI supports batch embedding (up to 2048 inputs)
        batch_size = 100
        for i in range(0, len(values), batch_size):
            batch = values[i:i + batch_size]
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/embeddings",
                        headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                        json={"model": "text-embedding-3-small", "input": batch},
                    )
                    data = resp.json()
                    for item in data.get("data", []):
                        idx = item["index"]
                        value = batch[idx]
                        self._embeddings[value] = item["embedding"]
            except Exception as e:
                logger.warning(f"Batch embedding failed: {e}")

        self._save()
        logger.info(f"Computed embeddings for {len(values)} {map_type}")

    @staticmethod
    def _cosine_sim(a: List[float], b: List[float]) -> float:
        """Cosine similarity between two vectors."""
        a_arr = np.array(a)
        b_arr = np.array(b)
        dot = np.dot(a_arr, b_arr)
        norm = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
        return float(dot / norm) if norm > 0 else 0.0

    # ── Stats ──

    def stats(self) -> Dict:
        self._load()
        kw = self._cache.get("keywords", {})
        ind = self._cache.get("industries", {})
        kw_with_emb = sum(1 for k in kw if k in self._embeddings)
        return {
            "industries": len(ind),
            "keywords": len(kw),
            "keywords_with_embeddings": kw_with_emb,
            "employee_ranges": len(EMPLOYEE_RANGES),
        }


# Singleton
taxonomy_service = TaxonomyService()
