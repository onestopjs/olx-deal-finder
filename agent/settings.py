"""Settings module for the OLX agent."""

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings for agent configuration."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    llm_provider: str = Field(
        description="LLM provider", choices=["ollama", "openai", "anthropic"]
    )

    ollama_url: str | None = Field(default=None, description="Ollama URL")
    ollama_model: str | None = Field(default=None, description="Ollama model")

    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    openai_model: str | None = Field(default=None, description="OpenAI model")
    openai_url: str | None = Field(default=None, description="OpenAI URL")

    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key")
    anthropic_model: str | None = Field(default=None, description="Anthropic model")

    tool_calling_enabled: bool = Field(
        default=False, description="Whether to enable tool calling"
    )

    relevancy_score_weight: int = Field(
        default=1, description="Weight of the relevancy score"
    )
    price_score_weight: int = Field(default=1, description="Weight of the price score")
    relevancy_gamma: float = Field(
        default=1.5,
        description="Exponent to curve relevance in [0,1]; >1 punishes low relevance more",
    )
    max_pages_to_search: int = Field(
        default=20,
        description="Maximum number of pages to search for listings",
    )
    enable_markdown: bool = Field(
        default=True, description="Whether to enable markdown in the response"
    )
    listings_batch_size: int = Field(
        default=20, description="Maximum number of listings to filter at once"
    )
    debug_scoring: bool = Field(
        default=False, description="Whether to return scoring details in the response"
    )
    log_level: str = Field(default="INFO", description="Logging level")

    @model_validator(mode="after")
    def validate_provider_specific_fields(self):
        """Validate that provider-specific fields are set when required."""
        if self.llm_provider == "ollama":
            if not self.ollama_url:
                raise ValueError("ollama_url is required when llm_provider is 'ollama'")
            if not self.ollama_model:
                raise ValueError(
                    "ollama_model is required when llm_provider is 'ollama'"
                )
        elif self.llm_provider == "openai":
            if not self.openai_api_key:
                raise ValueError(
                    "openai_api_key is required when llm_provider is 'openai'"
                )
            if not self.openai_model:
                raise ValueError(
                    "openai_model is required when llm_provider is 'openai'"
                )
        elif self.llm_provider == "anthropic":
            if not self.anthropic_api_key:
                raise ValueError(
                    "anthropic_api_key is required when llm_provider is 'anthropic'"
                )
            if not self.anthropic_model:
                raise ValueError(
                    "anthropic_model is required when llm_provider is 'anthropic'"
                )
        return self


settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings
