"""
HTTP Client for IBM watsonx Orchestrate.
Implements authentication, request retries with exponential backoff,
timeouts, and structured error mapping.
"""

import logging
import time
from typing import Any, Optional
import httpx

from backend.common.circuit_breaker import get_circuit_breaker
from backend.integrations.watsonx.config import WatsonxSettings
from backend.integrations.watsonx.errors import (
    WatsonxAuthenticationError,
    WatsonxConfigurationError,
    WatsonxError,
    WatsonxTimeoutError,
    WatsonxWorkflowExecutionError,
)

logger = logging.getLogger("vfx.integrations.watsonx.client")

IAM_TOKEN_URL = "https://iam.cloud.ibm.com/identity/token"
watsonx_circuit_breaker = get_circuit_breaker("watsonx_orchestrate", failure_threshold=3, recovery_timeout_seconds=30.0)


class WatsonxOrchestrateClient:
    """
    Client for interacting with IBM watsonx Orchestrate API.
    Supports token caching, retries with exponential backoff, and robust error handling.
    """

    def __init__(
        self,
        settings: Optional[WatsonxSettings] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.settings = settings or WatsonxSettings.load_from_env()
        self._http_client = http_client
        self._cached_token: Optional[str] = None
        self._token_expiry: float = 0.0

    def _get_client(self) -> httpx.Client:
        if self._http_client is not None:
            return self._http_client
        return httpx.Client(timeout=self.settings.timeout_seconds)

    def validate_configuration(self) -> None:
        """Ensure all required parameters are present for live execution."""
        missing: list[str] = []
        if not self.settings.api_key:
            missing.append("WATSONX_API_KEY")
        if not self.settings.instance_url:
            missing.append("WATSONX_INSTANCE_URL")

        if missing:
            raise WatsonxConfigurationError(
                message=f"Missing required watsonx configuration keys: {', '.join(missing)}",
                missing_keys=missing,
            )

    def get_auth_token(self) -> str:
        """Retrieve IBM Cloud IAM bearer token or use cached token."""
        self.validate_configuration()

        now = time.time()
        if self._cached_token and now < self._token_expiry:
            return self._cached_token

        client = self._get_client()
        headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
        data = {
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": self.settings.api_key,
        }

        try:
            response = client.post(IAM_TOKEN_URL, headers=headers, data=data)
        except httpx.TimeoutException as exc:
            raise WatsonxTimeoutError("IAM token request timed out", timeout_seconds=self.settings.timeout_seconds) from exc
        except httpx.RequestError as exc:
            raise WatsonxError(f"Network error connecting to IAM token endpoint: {exc}") from exc

        if response.status_code != 200:
            raise WatsonxAuthenticationError(
                f"Failed to authenticate with IBM Cloud IAM: {response.text}",
                status_code=response.status_code,
            )

        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise WatsonxAuthenticationError("IAM response did not contain access_token")

        expires_in = payload.get("expires_in", 3600)
        self._cached_token = token
        # Expire 60 seconds early to avoid token boundary races
        self._token_expiry = now + max(60, expires_in - 60)
        return token

    def run_workflow(
        self,
        skill_or_workflow_id: str,
        inputs: dict[str, Any],
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """
        Invoke an IBM watsonx Orchestrate workflow or skill with retries, exponential backoff,
        and circuit breaker protection.
        """
        return watsonx_circuit_breaker.call(
            self._execute_workflow_http,
            skill_or_workflow_id=skill_or_workflow_id,
            inputs=inputs,
            headers=headers,
        )

    def _execute_workflow_http(
        self,
        skill_or_workflow_id: str,
        inputs: dict[str, Any],
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        self.validate_configuration()
        token = self.get_auth_token()

        base_url = (self.settings.instance_url or "").rstrip("/")
        endpoint = f"{base_url}/v1/skills/{skill_or_workflow_id}/run"

        request_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            **(headers or {}),
        }
        if self.settings.service_instance_id:
            request_headers["X-Watsonx-Instance-ID"] = self.settings.service_instance_id

        client = self._get_client()
        max_attempts = max(1, self.settings.max_retries)
        last_exception: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                response = client.post(
                    endpoint,
                    headers=request_headers,
                    json={"inputs": inputs},
                )

                # Success
                if response.status_code in (200, 201, 202):
                    try:
                        return response.json()
                    except Exception:
                        return {"success": True, "raw_response": response.text}

                # Authentication error (do not retry without refreshed token)
                if response.status_code in (401, 403):
                    self._cached_token = None  # Invalidate cached token
                    raise WatsonxAuthenticationError(
                        f"watsonx authentication rejected: {response.text}",
                        status_code=response.status_code,
                    )

                # Transient errors (retryable: 429 rate limit, 502 Bad Gateway, 503 Service Unavailable, 504 Gateway Timeout)
                if response.status_code in (429, 502, 503, 504):
                    if attempt < max_attempts:
                        sleep_time = self.settings.retry_backoff_factor * (2 ** (attempt - 1))
                        logger.warning(
                            "watsonx returned status %d. Retrying attempt %d/%d after %.2fs...",
                            response.status_code,
                            attempt,
                            max_attempts,
                            sleep_time,
                        )
                        time.sleep(sleep_time)
                        continue
                    raise WatsonxWorkflowExecutionError(
                        f"watsonx workflow '{skill_or_workflow_id}' failed after {max_attempts} attempts: {response.text}",
                        workflow_id=skill_or_workflow_id,
                        status_code=response.status_code,
                    )

                # Client error (4xx: unprocessable, bad request)
                raise WatsonxWorkflowExecutionError(
                    f"watsonx workflow '{skill_or_workflow_id}' client error: {response.text}",
                    workflow_id=skill_or_workflow_id,
                    status_code=response.status_code,
                )

            except httpx.TimeoutException as exc:
                last_exception = exc
                if attempt < max_attempts:
                    sleep_time = self.settings.retry_backoff_factor * (2 ** (attempt - 1))
                    logger.warning("watsonx request timed out. Retrying attempt %d/%d after %.2fs...", attempt, max_attempts, sleep_time)
                    time.sleep(sleep_time)
                    continue
                raise WatsonxTimeoutError(
                    f"watsonx workflow '{skill_or_workflow_id}' timed out after {max_attempts} attempts",
                    timeout_seconds=self.settings.timeout_seconds,
                ) from exc

            except httpx.RequestError as exc:
                last_exception = exc
                if attempt < max_attempts:
                    sleep_time = self.settings.retry_backoff_factor * (2 ** (attempt - 1))
                    logger.warning("watsonx network error: %s. Retrying attempt %d/%d after %.2fs...", exc, attempt, max_attempts, sleep_time)
                    time.sleep(sleep_time)
                    continue
                raise WatsonxError(f"Network error communicating with watsonx Orchestrate: {exc}") from exc

        raise WatsonxError(f"Failed to execute watsonx workflow: {last_exception}")
