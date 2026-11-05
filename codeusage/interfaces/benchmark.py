from codeusage.benchmark import load_cceval, load_recceval, Benchmark
from codeusage.config import settings
benchmark_settings = settings.benchmark
def load_benchmark() -> Benchmark:
    if benchmark_settings.name == "recceval":
        result = load_recceval(
            benchmark_path=benchmark_settings.benchmark_path,
            repos_path=benchmark_settings.repos_path
        )
    elif benchmark_settings.name == "cceval":
        result = load_cceval(
            benchmark_path=benchmark_settings.benchmark_path,
            repos_path=benchmark_settings.repos_path
        )
    else:
        raise NotImplementedError(f"benchmark: [{benchmark_settings.name}] is not supported.")
    
    result.data_list = result.data_list[:settings.sample_n]
    return result