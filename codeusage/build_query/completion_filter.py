from abc import ABC, abstractmethod

class CompletionFilter(ABC):
    @abstractmethod
    def filter_name(
        self,
        code: str,
        completions: list[str]
    ) -> list[bool]: ...

class MagicMethodFilter(CompletionFilter):
    def filter_name(self, code: str, completions: list[str]) -> list[bool]:
        return [not (it.startswith("__") and it.endswith("__")) for it in completions]

class LimitFilter(CompletionFilter):
    n: int
    def __init__(self, n: int) -> None:
        self.n = n
    def filter_name(self, code: str, completions: list[str]) -> list[bool]:
        if len(completions) <= self.n:
            return [True] * len(completions)
        else:
            return [True] * self.n + [False] * (len(completions) - self.n)
        

class PipeFilter(CompletionFilter):
    filters: list[CompletionFilter]
    def __init__(self, *filters: CompletionFilter) -> None:
        self.filters = list(filters)
    
    def filter_name(self, code: str, completions: list[str]) -> list[bool]:
        result = [True] * len(completions)
        real_idx = list(range(len(completions)))
        for filter in self.filters:
            cur_completions = [completions[idx] for idx in real_idx]
            tmp_result = filter.filter_name(code, completions=cur_completions)
            next_real_idx = []
            for idx, valid in zip(real_idx, tmp_result, strict=True):
                if valid:
                    next_real_idx.append(idx)
                else:
                    result[idx] = False
            real_idx = next_real_idx
        return result