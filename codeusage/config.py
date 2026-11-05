from pathlib import Path
from typing import Literal
from pydantic import BaseModel
from loguru import logger
import sys



from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)


class Benchmark(BaseModel):
    name: Literal["recceval", "cceval"]
    repos_path: Path
    benchmark_path: Path


class ModelCompletionFilterConfig(BaseModel):
    enable: bool
    top_k: int
    model_name: str
    api_url: str
    api_key: str
    max_code_lines: int | None = None

class Retrieve(BaseModel):
    output_file: Path

    use_usage: bool
    max_usage_n: int
    usage_context_lines: int
    model_completion_filter: ModelCompletionFilterConfig
    use_usage_analysis: bool
    use_usage_ast: bool


    use_sparse: bool
    sparse_lask_k: int
    sparse_window_size: int
    sparse_overlap: int
    sparse_n: int

    static_analysis_time_limit_ms: int
    max_completion_n: int | None = None
    max_static_usage_time_ms: int | None = None
class BuildPrompt(BaseModel):
    use_retrieve_file: Path | None = None

    enable_id_info: bool
    enable_usage_retrieval: bool
    enable_sparse_retrieval: bool

    use_each_usage_n: int
    use_total_usage_n: int
    enable_usage_rerank: bool
    usage_rerank_query_last_k: int
    rerank_model: str | None
    use_sparse_n: int

    output_file: Path
    max_token_n: int
    tokenizer_path_or_name: str

class Inference(BaseModel):
    use_prompt_file: Path
    output_file: Path
    api_url: str
    api_key: str
    model: str
    max_new_tokens: int

class Evaluation(BaseModel):
    use_inference_file: Path
    output_file: Path

class Settings(BaseSettings):
    benchmark: Benchmark
    retrieve: Retrieve
    build_prompt: BuildPrompt
    inference: Inference
    evaluation: Evaluation

    sample_n: int | None = None
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"

    model_config = SettingsConfigDict(toml_file='config.toml')

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (TomlConfigSettingsSource(settings_cls),)

settings = Settings()
logger.remove()
logger.add(sys.stderr, level=settings.log_level)