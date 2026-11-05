from codeusage.interfaces.benchmark import load_benchmark
from codeusage.build_query.extract_node_needs_retrieve import find_last_statement_identifiers
from codeusage.build_query.infer_nodes import infer_nodes
from codeusage.retrieve.find_usage import find_usage, UsageTimeConsuming
from codeusage.retrieve.format_usage import format_usage
from codeusage.retrieve.sparse_retrieve import sparse_retrieve, SparseTimeConsuming
from codeusage.config import settings
from codeusage.retrieve import RetrievalResult, RetrievalResultItem, TimeComsuming
from codeusage.interfaces.completion_filter import create_completion_filter
from codeusage.config import settings
import contexttimer
from loguru import logger
import time
import sys

def main():
    logger_handler = logger.add(f"{settings.retrieve.output_file}" + ".{time}.log", enqueue=True, backtrace=True, level=settings.log_level)
    benchmark = load_benchmark()
    sample_n = len(benchmark.data_list)
    start = time.time()
    result = RetrievalResult(data_list=[], average_time_consuming=TimeComsuming(
        find_last_ids_ms=0,
        infer_types_ms=0,
        ppl_ms=0,
        find_usages_ms=0,
        sparse_ms=0,
        static_usage_ms=0,
        ast_usage_ms=0
    ))
    completion_filter = create_completion_filter()

    for i in range(sample_n):
        retrieval_item = RetrievalResultItem(
            definitions=[],
            usages=[],
            sparse_retrievals=[],
            time_consuming=TimeComsuming()
        )
        result.data_list.append(retrieval_item)
        benchmark_item = benchmark.data_list[i]
        lines = benchmark_item.code_context.splitlines()
        query = "\n".join(lines[-settings.retrieve.sparse_lask_k:])
        logger.debug(f"start benchmark[{i}]")
        logger.debug(f"benchmark item path: {benchmark_item.code_context_location.path}")
        code_lines = benchmark_item.code_context.splitlines()
        last_3_lines = code_lines[-3:]
        logger.debug(f"last 3 lines:\n{"\n".join(last_3_lines)}")
        logger.debug(f"ground truth [{benchmark_item.ground_truth}]")
        logger.debug(f"start find ids")
        with contexttimer.Timer(factor=1000) as t:
            find_ids_result = find_last_statement_identifiers(benchmark_item.code_context)
        retrieval_item.time_consuming.find_last_ids_ms = round(t.elapsed)
        logger.debug(f"found ids:\n")
        for it in find_ids_result:
            logger.debug(it)
        logger.debug(f"start infer nodes")
        infer_result = infer_nodes(
            repo_path=benchmark_item.repo.path,
            file_path=benchmark_item.code_context_location.path,
            code=benchmark_item.code_context,
            ids=find_ids_result,
            completion_filter=completion_filter,
            time_consuming=retrieval_item.time_consuming,
            time_limit_ms=settings.retrieve.static_analysis_time_limit_ms
        )
        logger.debug(f"infer result:\n")
        logger.debug(f"ids:" + "-"*30)
        for it in infer_result.ids:
            logger.debug(f"{it.model_dump_json(indent=4)}")
        logger.debug(f"completions:" + "-"*30)
        for it in infer_result.completions:
            logger.debug(f"{it.model_dump_json(indent=4)}")
        logger.debug(f"start finding usages")
        usage_time_consuming = UsageTimeConsuming()
        usages = find_usage(
            repo_path=benchmark_item.repo.path,
            exclude_path=benchmark_item.code_context_location.path,
            infer_result=infer_result,
            max_usage_n=settings.retrieve.max_usage_n,
            context_lines=settings.retrieve.usage_context_lines,
            enable_usage_analysis=settings.retrieve.use_usage_analysis,
            enable_usage_ast=settings.retrieve.use_usage_ast,
            time_consuming=usage_time_consuming
        )
        retrieval_item.time_consuming.find_usages_ms = usage_time_consuming.static_usage_ms + usage_time_consuming.ast_usage_ms
        retrieval_item.time_consuming.static_usage_ms = usage_time_consuming.static_usage_ms
        retrieval_item.time_consuming.ast_usage_ms = usage_time_consuming.ast_usage_ms
        logger.debug(f"finished finding usages")
        codes, id_usages_list = format_usage(usages)
        retrieval_item.definitions.extend(codes)
        retrieval_item.usages.extend(id_usages_list)

        # sparse
        if settings.retrieve.use_sparse:
            logger.debug("start sparse retrieval")
            sparse_consuming = SparseTimeConsuming()
            sparse_docs = sparse_retrieve(
                repo_path=benchmark_item.repo.path,
                query=query,
                exclude_path=benchmark_item.code_context_location.path,
                top_k=settings.retrieve.sparse_n,
                time_consuming=sparse_consuming
            )
            retrieval_item.time_consuming.sparse_ms = sparse_consuming.search_ms
            retrieval_item.sparse_retrievals.extend(sparse_docs)

    for it in result.data_list:
        assert result.average_time_consuming.find_last_ids_ms is not None
        result.average_time_consuming.find_last_ids_ms += (it.time_consuming.find_last_ids_ms or 0)
        assert result.average_time_consuming.infer_types_ms is not None
        result.average_time_consuming.infer_types_ms += (it.time_consuming.infer_types_ms or 0)
        assert result.average_time_consuming.ppl_ms is not None
        result.average_time_consuming.ppl_ms += (it.time_consuming.ppl_ms or 0)
        assert result.average_time_consuming.find_usages_ms is not None
        result.average_time_consuming.find_usages_ms += (it.time_consuming.find_usages_ms or 0)
        assert result.average_time_consuming.sparse_ms is not None
        result.average_time_consuming.sparse_ms += (it.time_consuming.sparse_ms or 0)
        assert result.average_time_consuming.static_usage_ms is not None
        result.average_time_consuming.static_usage_ms += (it.time_consuming.static_usage_ms or 0)
        assert result.average_time_consuming.ast_usage_ms is not None
        result.average_time_consuming.ast_usage_ms += (it.time_consuming.ast_usage_ms or 0)
    
    assert result.average_time_consuming.find_last_ids_ms is not None
    result.average_time_consuming.find_last_ids_ms //= len(result.data_list)
    assert result.average_time_consuming.infer_types_ms is not None
    result.average_time_consuming.infer_types_ms //= len(result.data_list)
    assert result.average_time_consuming.ppl_ms is not None
    result.average_time_consuming.ppl_ms //= len(result.data_list)
    assert result.average_time_consuming.find_usages_ms is not None
    result.average_time_consuming.find_usages_ms //= len(result.data_list)
    assert result.average_time_consuming.sparse_ms is not None
    result.average_time_consuming.sparse_ms //= len(result.data_list)
    assert result.average_time_consuming.static_usage_ms is not None
    result.average_time_consuming.static_usage_ms //= len(result.data_list)
    assert result.average_time_consuming.ast_usage_ms is not None
    result.average_time_consuming.ast_usage_ms //= len(result.data_list)

    end = time.time()
    print(f"time cost = {end - start}s")
    save_path = settings.retrieve.output_file
    save_path.parent.mkdir(exist_ok=True, parents=True)
    with open(save_path, "w") as f:
        f.write(result.model_dump_json(indent=4))
        logger.info(f"result saved in {save_path}")

    logger.remove(logger_handler)

if __name__ == "__main__":
    main()
