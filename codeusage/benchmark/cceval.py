from pathlib import Path
from loguru import logger
from .common import Benchmark, BenchmarkItem, CodeLocation, CodeRepo
from .utils import load_jsonl

def load_cceval(benchmark_path: Path | str, repos_path: Path | str) -> Benchmark:
    benchmark_path = Path(benchmark_path)
    repos_path = Path(repos_path)

    json_objs: list = load_jsonl(benchmark_path)
    
    benchmark_data: list[BenchmarkItem] = []
    pkg_counter = {}
    repo_dict: dict[str, CodeRepo] = {}

    for obj in json_objs:
        metadata = obj["metadata"]
        pkg = metadata["repository"]
        assert isinstance(pkg, str)
        fpath = metadata["file"]
        assert isinstance(fpath, str)
        input_content = obj["prompt"]
        assert isinstance(input_content, str)
        ground_truth = obj["groundtruth"]
        assert isinstance(ground_truth, str)

        if pkg not in pkg_counter:
            pkg_counter[pkg] = 0
        task_id = f"{pkg}/{pkg_counter[pkg]}"
        pkg_counter[pkg] += 1

        context_start_lineno = int(metadata["context_start_lineno"])
        end_line_no = len(input_content.splitlines()) - 1

        repo_path = repos_path.joinpath(pkg)
        if pkg not in repo_dict:
            assert repo_path.exists()
            repo_dict[pkg] = CodeRepo(
                name=pkg,
                path=repo_path
            )
        
        task_file_path = repos_path.joinpath(pkg, fpath)
        assert task_file_path.exists()

        benchmark_data.append(BenchmarkItem(
            code_context=input_content,
            code_context_location=CodeLocation(
                start_line_no = context_start_lineno,
                end_line_no = end_line_no,
                path=task_file_path,
            ),
            ground_truth=ground_truth,
            task_name=task_id,
            repo=CodeRepo(
                name=pkg,
                path=repo_path
            )
        ))
    logger.info(f"Benchmark length: {len(benchmark_data)}")
    
    logger.info(f"Repos length: {len(repo_dict)}")
    
    return Benchmark(
        data_list=benchmark_data,
        repos=list(repo_dict.values())
    )