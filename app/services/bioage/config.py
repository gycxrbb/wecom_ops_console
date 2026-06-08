from pydantic import BaseModel, ConfigDict
from pathlib import Path

_PARAMS_DIR = Path(__file__).parent / "params"


class BioageConfig(BaseModel):
    """bioage 模块独立配置。从宿主 settings 中提取，迁移时只需替换此配置源。"""

    model_config = ConfigDict(extra="ignore")

    llm_api_key: str = ""
    llm_base_url: str = "https://aihubmix.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 30


def get_params_dir() -> Path:
    return _PARAMS_DIR
