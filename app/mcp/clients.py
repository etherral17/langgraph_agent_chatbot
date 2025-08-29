import httpx
from typing import Dict, Any, Optional
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import settings
from loguru import logger

class MCPClientError(Exception):
    pass

class BaseMCPClient:
    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = str(base_url).rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def call(self, ability: str, payload: Dict[str, Any], path: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{path or ability}"

        # ✅ async for instead of for
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(settings.RETRY_ATTEMPTS),
            wait=wait_exponential(multiplier=1, min=settings.RETRY_WAIT_SECONDS, max=10),
            retry=retry_if_exception_type((httpx.TransportError, httpx.RequestError)),
            reraise=True
        ):
            with attempt:
                logger.debug("MCP call", url=url, ability=ability, attempt=str(attempt.retry_state.attempt_number))
                resp = await self._client.post(url, json=payload)

                if resp.status_code >= 500:
                    raise MCPClientError(f"server error {resp.status_code}")

                return resp.json()

        raise MCPClientError("Retries exhausted")

class CommonMCPClient(BaseMCPClient):
    pass

class AtlasMCPClient(BaseMCPClient):
    pass

# Factory
common_client = CommonMCPClient(settings.MCP_COMMON_URL, timeout=settings.MCP_TIMEOUT_SECONDS)
atlas_client = AtlasMCPClient(settings.MCP_ATLAS_URL, timeout=settings.MCP_TIMEOUT_SECONDS)
