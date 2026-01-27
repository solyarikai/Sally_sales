import asyncio
import re
from typing import Dict, Any, List, Optional, Callable
from openai import AsyncOpenAI
from app.core.config import settings
import logging
import time

logger = logging.getLogger(__name__)


# Model-specific configurations
MODEL_CONFIGS = {
    "gpt-4o": {"max_tokens": 4096, "supports_system": True, "rate_limit_rpm": 500},
    "gpt-4o-mini": {"max_tokens": 4096, "supports_system": True, "rate_limit_rpm": 1000},
    "gpt-4-turbo": {"max_tokens": 4096, "supports_system": True, "rate_limit_rpm": 500},
    "gpt-3.5-turbo": {"max_tokens": 4096, "supports_system": True, "rate_limit_rpm": 1000},
    "o1": {"max_tokens": 4096, "supports_system": False, "rate_limit_rpm": 100},
    "o1-mini": {"max_tokens": 4096, "supports_system": False, "rate_limit_rpm": 200},
    "o3-mini": {"max_tokens": 4096, "supports_system": False, "rate_limit_rpm": 200},
}


class OpenAIService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None
        self._request_times: List[float] = []
    
    def set_api_key(self, api_key: str):
        self.api_key = api_key
        self.client = AsyncOpenAI(api_key=api_key)
    
    def render_prompt(self, template: str, row_data: Dict[str, Any]) -> str:
        """Replace {{column_name}} placeholders with actual values"""
        result = template
        for key, value in row_data.items():
            placeholder = f"{{{{{key}}}}}"
            result = result.replace(placeholder, str(value) if value is not None else "")
        return result
    
    def _get_model_config(self, model: str) -> Dict[str, Any]:
        """Get configuration for a model"""
        return MODEL_CONFIGS.get(model, MODEL_CONFIGS["gpt-4o-mini"])
    
    async def _rate_limit_wait(self, model: str):
        """Simple rate limiting based on model RPM limits"""
        config = self._get_model_config(model)
        rpm_limit = config.get("rate_limit_rpm", 500)
        min_interval = 60.0 / rpm_limit
        
        now = time.time()
        # Clean old request times (older than 60 seconds)
        self._request_times = [t for t in self._request_times if now - t < 60]
        
        if len(self._request_times) >= rpm_limit:
            # Wait until oldest request is 60 seconds old
            wait_time = 60 - (now - self._request_times[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)
        
        self._request_times.append(time.time())
    
    async def enrich_single_row(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "gpt-4o-mini",
        retry_count: int = 3,
    ) -> Dict[str, Any]:
        """Enrich a single row with OpenAI with retry logic"""
        if not self.client:
            raise ValueError("OpenAI API key not configured")
        
        config = self._get_model_config(model)
        
        # Build messages based on model capabilities
        messages = []
        if system_prompt and config.get("supports_system", True):
            messages.append({"role": "system", "content": system_prompt})
        elif system_prompt:
            # For models without system support, prepend to user message
            prompt = f"Instructions: {system_prompt}\n\nTask: {prompt}"
        
        messages.append({"role": "user", "content": prompt})
        
        for attempt in range(retry_count):
            try:
                await self._rate_limit_wait(model)
                
                # Different parameters for reasoning models (o1, o3)
                if model.startswith("o1") or model.startswith("o3"):
                    response = await self.client.chat.completions.create(
                        model=model,
                        messages=messages,
                        max_completion_tokens=config.get("max_tokens", 4096),
                    )
                else:
                    response = await self.client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=0.3,
                        max_tokens=min(1000, config.get("max_tokens", 4096)),
                    )
                
                return {
                    "success": True,
                    "result": response.choices[0].message.content.strip(),
                    "tokens_used": response.usage.total_tokens if response.usage else 0,
                }
            except Exception as e:
                error_str = str(e)
                logger.warning(f"OpenAI API attempt {attempt + 1} failed: {error_str}")
                
                # Retry on rate limit or temporary errors
                if "rate_limit" in error_str.lower() or "timeout" in error_str.lower():
                    wait_time = (attempt + 1) * 5  # Exponential backoff
                    await asyncio.sleep(wait_time)
                    continue
                
                # Don't retry on other errors
                return {
                    "success": False,
                    "error": error_str,
                    "tokens_used": 0,
                }
        
        return {
            "success": False,
            "error": "Max retries exceeded",
            "tokens_used": 0,
        }
    
    async def enrich_batch(
        self,
        rows: List[Dict[str, Any]],
        prompt_template: str,
        system_prompt: Optional[str] = None,
        model: str = "gpt-4o-mini",
        max_concurrent: int = 10,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Enrich multiple rows with concurrency control.
        Optimized for large datasets (1000-10000+ rows).
        """
        # Adjust concurrency based on model limits
        config = self._get_model_config(model)
        rpm_limit = config.get("rate_limit_rpm", 500)
        
        # Calculate optimal concurrency (don't exceed ~80% of RPM limit)
        optimal_concurrent = min(max_concurrent, int(rpm_limit * 0.8 / 60 * 5))
        optimal_concurrent = max(3, optimal_concurrent)  # At least 3
        
        semaphore = asyncio.Semaphore(optimal_concurrent)
        completed_count = 0
        total_count = len(rows)
        
        async def process_row(row: Dict[str, Any]) -> Dict[str, Any]:
            nonlocal completed_count
            async with semaphore:
                prompt = self.render_prompt(prompt_template, row["data"])
                result = await self.enrich_single_row(prompt, system_prompt, model)
                
                completed_count += 1
                if progress_callback:
                    progress_callback(completed_count, total_count)
                
                return {
                    "row_id": row["id"],
                    **result
                }
        
        # Process in chunks for very large datasets to avoid memory issues
        chunk_size = 500
        all_results = []
        
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i:i + chunk_size]
            tasks = [process_row(row) for row in chunk]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for j, result in enumerate(results):
                if isinstance(result, Exception):
                    all_results.append({
                        "row_id": chunk[j]["id"],
                        "success": False,
                        "error": str(result),
                        "tokens_used": 0,
                    })
                else:
                    all_results.append(result)
            
            # Small delay between chunks to prevent overwhelming
            if i + chunk_size < len(rows):
                await asyncio.sleep(0.5)
        
        return all_results
    
    async def generate_single(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "gpt-4o-mini",
    ) -> str:
        """Generate a single response (not tied to row enrichment)"""
        result = await self.enrich_single_row(prompt, system_prompt, model)
        if result["success"]:
            return result["result"]
        raise Exception(result.get("error", "Unknown error"))

    async def test_connection(self) -> bool:
        """Test if the API key is valid"""
        if not self.client:
            return False
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False


# Global instance
openai_service = OpenAIService()
