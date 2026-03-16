"""Fireflies.ai integration service for call recording transcripts.

Uses Fireflies GraphQL API: https://docs.fireflies.ai

Supports per-project API keys (token passed explicitly) and
legacy global key for backward compatibility.
"""
import httpx
from typing import Optional, List, Dict, Any
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

FIREFLIES_GRAPHQL_URL = "https://api.fireflies.ai/graphql"


class FirefliesService:
    """Service for interacting with Fireflies.ai GraphQL API.

    All methods accept an optional `api_key` parameter.
    When provided, it takes precedence over the global key.
    """

    def __init__(self):
        self._api_key: Optional[str] = settings.FIREFLIES_API_KEY

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key

    def set_api_key(self, api_key: str):
        """Set the global API key (legacy)."""
        self._api_key = api_key

    def _resolve_key(self, api_key: Optional[str] = None) -> Optional[str]:
        """Return explicit key if given, else fall back to global."""
        return api_key or self._api_key

    def is_connected(self, api_key: Optional[str] = None) -> bool:
        return bool(self._resolve_key(api_key))

    def _get_headers(self, api_key: Optional[str] = None) -> Dict[str, str]:
        key = self._resolve_key(api_key)
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    async def _query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query against Fireflies API."""
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                FIREFLIES_GRAPHQL_URL,
                headers=self._get_headers(api_key),
                json=payload,
            )

            if response.status_code != 200:
                logger.error(f"Fireflies API error: {response.status_code} - {response.text}")
                raise Exception(f"Fireflies API returned {response.status_code}")

            data = response.json()
            if "errors" in data:
                logger.error(f"Fireflies GraphQL errors: {data['errors']}")
                raise Exception(f"Fireflies GraphQL error: {data['errors'][0].get('message', 'Unknown')}")

            return data.get("data", {})

    async def test_connection(self, api_key: Optional[str] = None) -> bool:
        key = self._resolve_key(api_key)
        if not key:
            return False
        try:
            data = await self._query("{ user { name email } }", api_key=key)
            return data.get("user") is not None
        except Exception as e:
            logger.error(f"Fireflies connection test failed: {e}")
            return False

    async def get_user(self, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        key = self._resolve_key(api_key)
        if not key:
            return None
        try:
            data = await self._query("{ user { name email user_id } }", api_key=key)
            return data.get("user")
        except Exception as e:
            logger.error(f"Error fetching Fireflies user: {e}")
            return None

    async def get_transcripts(
        self,
        limit: int = 20,
        skip: int = 0,
        api_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        key = self._resolve_key(api_key)
        if not key:
            return []

        query = """
        query Transcripts($limit: Int, $skip: Int) {
            transcripts(limit: $limit, skip: $skip) {
                id
                title
                date
                duration
                organizer_email
                participants
                transcript_url
            }
        }
        """

        try:
            data = await self._query(query, {"limit": limit, "skip": skip}, api_key=key)
            return data.get("transcripts", [])
        except Exception as e:
            logger.error(f"Error fetching Fireflies transcripts: {e}")
            return []

    async def get_transcript(
        self,
        transcript_id: str,
        api_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        key = self._resolve_key(api_key)
        if not key:
            return None

        query = """
        query Transcript($id: String!) {
            transcript(id: $id) {
                id
                title
                date
                dateString
                duration
                organizer_email
                host_email
                participants
                transcript_url
                audio_url
                video_url

                speakers {
                    id
                    name
                }

                sentences {
                    index
                    speaker_name
                    speaker_id
                    text
                    raw_text
                    start_time
                    end_time
                    ai_filters {
                        task
                        pricing
                        metric
                        question
                        sentiment
                    }
                }

                summary {
                    keywords
                    action_items
                    outline
                    overview
                    short_summary
                    topics_discussed
                }

                meeting_attendees {
                    displayName
                    email
                    phoneNumber
                    name
                }
            }
        }
        """

        try:
            data = await self._query(query, {"id": transcript_id}, api_key=key)
            return data.get("transcript")
        except Exception as e:
            logger.error(f"Error fetching Fireflies transcript {transcript_id}: {e}")
            return None


# Global instance
fireflies_service = FirefliesService()
