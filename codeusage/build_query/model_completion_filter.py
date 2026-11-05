from .completion_filter import CompletionFilter
from openai import AsyncClient, Client
from concurrent.futures import ThreadPoolExecutor

class ModelCompletionFilter(CompletionFilter):
    client: Client
    model_name: str
    top_k: int
    max_code_lines: int | None
    def __init__(
        self,
        client: Client,
        model_name: str,
        top_k: int,
        max_code_lines: int | None = 20
    ) -> None:
        self.client = client
        self.model_name = model_name
        self.top_k = top_k
        self.max_code_lines = max_code_lines

        super().__init__()

    def _score_single_completion(self, code: str, completion: str) -> float:
        full_input = code + completion
        response = self.client.completions.create(
            model=self.model_name,
            prompt=full_input,
            max_tokens=0,
            temperature=0,
            logprobs=1,
            echo=True
        )
        choice = response.choices[0]
        logprops = choice.logprobs
        if logprops is None:
            raise TypeError("logprobs is None")
        token_logprobs = logprops.token_logprobs
        if token_logprobs is None:
            raise TypeError("token_logprobs is None")
        text_offsets = logprops.text_offset
        if text_offsets is None:
            raise TypeError("text_offsets is None")
        completion_start = len(code)
        total_logprob = 0.0
        count = 0

        tokens = logprops.tokens
        if tokens is None:
            raise TypeError("logprops.tokens is None")
        token_texts = tokens

        for logprob, offset, tok in zip(token_logprobs, text_offsets, token_texts, strict=True):
            token_end = offset + len(tok)
            if token_end > completion_start:
                total_logprob += logprob
                count += 1

        if count == 0:
            return float("-inf")
        return total_logprob
    def _score_all(self, code: str, completions: list[str]) -> list[float]:
        max_workers = min(256, len(completions))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self._score_single_completion, code, c)
                                            for c in completions]
        results = [f.result() for f in futures]
        return results

    def filter_name(self, code: str, completions: list[str]) -> list[bool]:
        if len(completions) <= self.top_k:
            return [True] * len(completions)
        max_len_each_line = 300
        if self.max_code_lines is not None:
            code_lines = code.splitlines()
            code_lines = [it[:max_len_each_line] for it in code_lines]
            code = "\n".join(code_lines[-self.max_code_lines:])
        scores = self._score_all(code, completions)
        sorted_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        result = [False] * len(completions)
        for idx in sorted_indices[:self.top_k]:
            result[idx] = True
        return result