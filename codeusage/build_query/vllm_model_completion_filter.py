from vllm import LLM, SamplingParams
from typing import List, Optional
from .completion_filter import CompletionFilter
from loguru import logger

# 假设 CompletionFilter 和其他基本类型已定义

class VLLMLocalFilter(CompletionFilter):
    # 将 client 替换为 vLLM 的 LLM 实例
    llm: LLM
    model_name: str
    top_k: int
    max_code_lines: Optional[int]

    def __init__(
        self,
        model_name: str,
        top_k: int,
        max_code_lines: Optional[int] = 20,
        # vLLM 初始化参数
        tensor_parallel_size: int = 1,
        dtype: str = "auto",
        trust_remote_code: bool = True
    ) -> None:
        """
        初始化时创建 vLLM LLM 实例，加载模型。
        """
        self.model_name = model_name
        self.top_k = top_k
        self.max_code_lines = max_code_lines

        print(f"Loading vLLM model: {model_name}...")
        
        # 进程内加载 vLLM 核心：LLM 类
        self.llm = LLM(
            model=model_name,
            tensor_parallel_size=tensor_parallel_size,
            dtype=dtype,
            trust_remote_code=trust_remote_code
        )
        self.tokenizer = self.llm.get_tokenizer()
        
        super().__init__()

    def _score_all(self, code: str, completions: List[str]) -> List[float]:
        if not completions:
            return []
            
        full_prompts = [code + c for c in completions]

        sampling_params = SamplingParams(
            n=1,
            temperature=0.0,
            logprobs=1,              
            prompt_logprobs=1,       
            max_tokens=1       
        )

        outputs = self.llm.generate(
            prompts=full_prompts,
            sampling_params=sampling_params,
        )

        # for it in outputs:
        #     assert it.prompt_logprobs is not None
        #     logger.debug(f"ids={it.prompt_token_ids}")
        #     for prompt_logprob in it.prompt_logprobs:
        #         logger.debug(prompt_logprob)
        #     logger.debug("=" * 20)

        scores: List[float] = []
        calc_tokens_score: list[list[tuple[str, float]]] = []

        for response in outputs:
            assert response.prompt_token_ids is not None
            offset = 0
            score = 0.0
            tokens_score: list[tuple[str, float]] = []
            assert response.prompt_logprobs is not None
            for input_token, current_logprobs in zip(response.prompt_token_ids, response.prompt_logprobs):
                if current_logprobs is None:
                    offset += len(self.tokenizer.decode(input_token))
                    continue
                logprob = current_logprobs[input_token]

                assert logprob.decoded_token is not None
                token_len = len(logprob.decoded_token)
                if offset + token_len > len(code):
                    tokens_score.append((logprob.decoded_token, logprob.logprob))
                    score += logprob.logprob
                
                offset += token_len
            calc_tokens_score.append(tokens_score)
            scores.append(score)
        for score, tokens_score in zip(scores, calc_tokens_score, strict=True):
            logger.debug(f"score={score},tokens={tokens_score}")
        return scores

    def filter_name(self, code: str, completions: List[str]) -> List[bool]:
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
