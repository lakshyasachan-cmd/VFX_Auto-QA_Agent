"""
Configuration settings for the IBM watsonx Orchestrate Integration.
Loads all parameters strictly from environment variables without hardcoding.
"""

import os
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class WatsonxSettings(BaseModel):
    """
    Settings for IBM watsonx Orchestrate client and workflow adapter.
    Reads strictly from environment variables with sensible defaults.
    """
    model_config = ConfigDict(extra="ignore")

    # Mock mode flag: default to True for local testing / sandbox execution
    mock_mode: bool = Field(
        default_factory=lambda: os.getenv("WATSONX_MOCK", "true").lower() in ("true", "1", "yes")
    )

    # IBM Cloud / watsonx instance configuration
    api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("WATSONX_API_KEY")
    )
    instance_url: Optional[str] = Field(
        default_factory=lambda: os.getenv("WATSONX_INSTANCE_URL")
    )
    service_instance_id: Optional[str] = Field(
        default_factory=lambda: os.getenv("WATSONX_SERVICE_INSTANCE_ID")
    )
    project_id: Optional[str] = Field(
        default_factory=lambda: os.getenv("WATSONX_PROJECT_ID")
    )
    space_id: Optional[str] = Field(
        default_factory=lambda: os.getenv("WATSONX_SPACE_ID")
    )

    # HTTP client resilience configuration
    timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("WATSONX_TIMEOUT_SECONDS", "15.0"))
    )
    max_retries: int = Field(
        default_factory=lambda: int(os.getenv("WATSONX_MAX_RETRIES", "3"))
    )
    retry_backoff_factor: float = Field(
        default_factory=lambda: float(os.getenv("WATSONX_RETRY_BACKOFF_FACTOR", "0.5"))
    )

    @classmethod
    def load_from_env(cls) -> "WatsonxSettings":
        """Factory method to load fresh configuration from current environment."""
        return cls()
