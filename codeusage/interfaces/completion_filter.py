from codeusage.build_query.completion_filter import CompletionFilter, PipeFilter, MagicMethodFilter, LimitFilter
from codeusage.build_query.model_completion_filter import ModelCompletionFilter
from codeusage.config import settings
from openai import OpenAI

def create_completion_filter() -> CompletionFilter:
    completion_filters: list[CompletionFilter] = [MagicMethodFilter()]
    if settings.retrieve.max_completion_n is not None:
        completion_filters.append(LimitFilter(settings.retrieve.max_completion_n))
    config = settings.retrieve.model_completion_filter
    if config.enable:
        client = OpenAI(
            api_key=config.api_key,
            base_url=config.api_url
        )
        completion_filters.append(ModelCompletionFilter(
            client=client,
            model_name=config.model_name,
            top_k=config.top_k,
            max_code_lines=config.max_code_lines
        ))
    return PipeFilter(*completion_filters)