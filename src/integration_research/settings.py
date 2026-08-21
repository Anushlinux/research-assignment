"""Environment-backed settings for live Milestone 1 execution."""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: SecretStr | None = None
    composio_api_key: SecretStr | None = None
    openai_model_extract: str = "gpt-5.6-luna"
    openai_model_verify: str = "gpt-5.6-terra"
    composio_user_id: str = "composio-takehome-research"
    composio_session_id: str = ""
    research_max_searches_per_app: int = 5
    research_max_fetches_per_app: int = 8
    research_max_verification_searches_per_app: int = 3
    research_max_verification_fetches_per_app: int = 3
    research_max_browser_tasks_per_app: int = 1
    research_max_chars_per_page: int = 20_000
    research_max_chars_per_app: int = 60_000
    runs_dir: Path = Path("runs")
    state_dir: Path = Path(".state")

    def require_live_credentials(self) -> None:
        missing: list[str] = []
        if self.openai_api_key is None or not self.openai_api_key.get_secret_value():
            missing.append("OPENAI_API_KEY")
        if self.composio_api_key is None or not self.composio_api_key.get_secret_value():
            missing.append("COMPOSIO_API_KEY")
        if missing:
            names = ", ".join(missing)
            raise ValueError(f"Missing live credentials in .env: {names}")
