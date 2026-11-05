from codeusage.interfaces.benchmark import load_benchmark
from transformers import AutoTokenizer, AutoModel
from codeusage.build_prompt.merge_retrieval import merge_retrieval
from codeusage.retrieve import RetrievalResult
from transformers import AutoTokenizer
from codeusage.retrieve.sparse_retrieve import sparse_retrieve_docs
from codeusage.retrieve.dense_retrieve import dense_retrieve_docs
from loguru import logger
from codeusage.build_db import Doc, merge_docs_by_reading_file
from codeusage.rerank.cross_encoder import CrossEncoderReranker
from pathlib import Path
from tqdm import tqdm
import json
from codeusage.config import settings
from contexttimer import Timer

def main():
    benchmark = load_benchmark()
    sample_n = len(benchmark.data_list)
    print(f"sample_n={sample_n}")

    retrieval_result_path = settings.build_prompt.use_retrieve_file
    retrieval_result: RetrievalResult | None = None
    if retrieval_result_path is not None:
        with open(retrieval_result_path, "r") as f:
            retrieval_result = RetrievalResult.model_validate_json(f.read())
            print(f"retrieval len={len(retrieval_result.data_list)}")
            print(f"retrieval path={retrieval_result_path}")
            retrieval_result.data_list = retrieval_result.data_list[:sample_n]

    prompts: list[str] = []
    tokenizer = AutoTokenizer.from_pretrained(settings.build_prompt.tokenizer_path_or_name, trust_remote=True)

    reranker: CrossEncoderReranker | None = None
    if settings.build_prompt.enable_usage_rerank:
        model_id = settings.build_prompt.rerank_model
        assert model_id is not None
        reranker = CrossEncoderReranker(model_id)
        

    for i in tqdm(range(sample_n)):
        benchmark_item = benchmark.data_list[i]
        retrieval_strs: list[str] = []
        if retrieval_result is not None:
            retrieval_item = retrieval_result.data_list[i]
            if settings.build_prompt.enable_id_info:
                retrieval_strs.extend(retrieval_item.definitions)
            usage_docs: list[Doc] = []
            retrieval_docs: list[Doc] = []
            if settings.build_prompt.enable_usage_retrieval:
                for it in retrieval_item.usages:
                    usage_docs.extend(it.usages[:settings.build_prompt.use_each_usage_n])
                if settings.build_prompt.enable_usage_rerank:
                    lines = benchmark_item.code_context.splitlines()
                    query = "\n".join(lines[-settings.build_prompt.usage_rerank_query_last_k:])
                    assert reranker is not None
                    with Timer(factor=1000) as t:
                        usage_docs = reranker.rerank(
                            query=query,
                            docs=usage_docs,
                            exclude_path=benchmark_item.code_context_location.path,
                            top_k=settings.build_prompt.use_total_usage_n
                        )
                    retrieval_item.time_consuming.reranking_ms = round(t.elapsed)
                usage_docs = merge_docs_by_reading_file(usage_docs)
            retrieval_docs.extend(usage_docs)
            if settings.build_prompt.enable_sparse_retrieval:
                retrieval_docs.extend(merge_docs_by_reading_file(retrieval_item.sparse_retrievals[:settings.build_prompt.use_sparse_n]))
            for it in retrieval_docs:
                code_prefix ="# " + str(it.path.resolve().relative_to(benchmark_item.repo.path.resolve()))
                retrieval_strs.append(f"{code_prefix}\n{it.content}")
            
            
                
        retrieval_strs = [it.replace("'''", '"""') for it in retrieval_strs]
        prompt = merge_retrieval(
            retrieval_infos=retrieval_strs,
            source_code_prefix="# " + str(benchmark_item.code_context_location.path.resolve().relative_to(benchmark_item.repo.path.resolve())),
            source_code=benchmark_item.code_context,
            tokenizer=tokenizer,
            max_prompt_token_n=settings.build_prompt.max_token_n
        )
        prompts.append(prompt[0])

    if retrieval_result is not None:
        aver_reranking_ms = 0
        for it in retrieval_result.data_list:
            aver_reranking_ms += (it.time_consuming.reranking_ms or 0)
        retrieval_result.average_time_consuming.reranking_ms = aver_reranking_ms // len(retrieval_result.data_list)
        assert settings.build_prompt.use_retrieve_file is not None
        with open(str(settings.build_prompt.use_retrieve_file) + "-time", "w") as f:
            f.write(retrieval_result.model_dump_json(indent=4))


    save_path = Path(settings.build_prompt.output_file)
    save_path.parent.mkdir(exist_ok=True, parents=True)
    with open(save_path, "w") as f:
        json.dump(prompts, f, indent=4)
        logger.info(f"result saved in {save_path}")

if __name__ == "__main__":
    main()