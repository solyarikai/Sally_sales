"""Fireflies.ai integration service for call recording transcripts.

Uses Fireflies GraphQL API: https://docs.fireflies.ai
"""
import httpx
from typing import Optional, List, Dict, Any
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

FIREFLIES_GRAPHQL_URL = "https://api.fireflies.ai/graphql"


class FirefliesService:
    """Service for interacting with Fireflies.ai GraphQL API."""

    def __init__(self):
        self._api_key: Optional[str] = settings.FIREFLIES_API_KEY

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key

    def set_api_key(self, api_key: str):
        """Set the API key."""
        self._api_key = api_key

    def is_connected(self) -> bool:
        """Check if we have an API key configured."""
        return bool(self._api_key)

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for GraphQL requests."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def _query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query against Fireflies API."""
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                FIREFLIES_GRAPHQL_URL,
                headers=self._get_headers(),
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

    async def test_connection(self) -> bool:
        """Test the API connection by fetching current user info."""
        if not self._api_key:
            return False

        try:
            data = await self._query("{ user { name email } }")
            return data.get("user") is not None
        except Exception as e:
            logger.error(f"Fireflies connection test failed: {e}")
            return False

    async def get_user(self) -> Optional[Dict[str, Any]]:
        """Get current user info."""
        if not self._api_key:
            return None

        try:
            data = await self._query("{ user { name email user_id } }")
            return data.get("user")
        except Exception as e:
            logger.error(f"Error fetching Fireflies user: {e}")
            return None

    async def get_transcripts(
        self,
        limit: int = 20,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """Fetch list of transcripts."""
        if not self._api_key:
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
            data = await self._query(query, {"limit": limit, "skip": skip})
            return data.get("transcripts", [])
        except Exception as e:
            logger.error(f"Error fetching Fireflies transcripts: {e}")
            return []

    async def get_transcript(self, transcript_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single transcript with full details."""
        if not self._api_key:
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
            data = await self._query(query, {"id": transcript_id})
            return data.get("transcript")
        except Exception as e:
            logger.error(f"Error fetching Fireflies transcript {transcript_id}: {e}")
            return None


# Global instance
fireflies_service = FirefliesService()
