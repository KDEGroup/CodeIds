# CodeIds

Source code for the WSDM '27 paper **"CodeIds: Enhancing Repository-Level Code Completion with Identifier-Grounded Retrieval"**.

CodeIds augments repository-level code completion with context grounded in identifiers from the code being completed. The implementation identifies relevant names, resolves their definitions and usage sites in the repository, combines that context with sparse retrieval, and builds prompts for a completion model. This repository includes the retrieval, prompt construction, inference, and evaluation pipeline.

## Requirements

- Linux x86-64, Python 3.12, and [Pixi](https://pixi.sh/). The Pixi environment specifies CUDA 12 or newer.
- The ReccEval or CCEval benchmark data, including the corresponding source repositories (see below).
- Model files for the tokenizer and reranker, plus OpenAI-compatible completion endpoints for the model-assisted retrieval filter and the completion model. The example configuration names Qwen2.5-Coder-0.5B, `ms-marco-MiniLM-L6-v2`, and Qwen2.5-Coder-7B; model files are not included in this repository.

Install the environment from the repository root:

```bash
pixi install
```

## Benchmark data

Obtain the benchmark metadata and source repositories from the original projects:

| Benchmark | Source | Expected metadata format |
| --- | --- | --- |
| ReccEval | [DraCo](https://github.com/nju-websoft/DraCo) | JSONL records with `pkg`, `fpath`, `input`, and `gt` |
| CCEval | [CCEval](https://github.com/amazon-science/cceval) | JSONL records with `metadata`, `prompt`, and `groundtruth` |

Set `[benchmark].name`, `repos_path`, and `benchmark_path` in `config.toml` to the locations of your downloaded data. The paths in `config.example.toml` illustrate the expected layout; the benchmark data is not bundled here. For ReccEval, `repos_path` contains a directory for each package. For CCEval, it contains a directory for each repository named in the metadata.

## Configuration

```bash
cp config.example.toml config.toml
```

Edit `config.toml` before running the pipeline:

1. Set the benchmark paths and select `recceval` or `cceval`.
2. Set `[retrieve.model_completion_filter]` to an endpoint serving the filter model. With the example settings, the endpoint must support completion log probabilities and `echo` requests.
3. Set `[build_prompt].rerank_model` to the local reranker directory and `tokenizer_path_or_name` to the tokenizer for the completion model.
4. Set `[inference]` to an endpoint serving the completion model. The example uses the completions API with `Qwen2.5-Coder-7B`.
5. Check that each stage's input path matches the preceding stage's output path: `retrieve.output_file` → `build_prompt.use_retrieve_file` → `inference.use_prompt_file` → `evaluation.use_inference_file`.

The example uses `cache/` for benchmark files and generated artifacts; this directory and `config.toml` are ignored by Git. You can set `sample_n` at the top of the configuration to process only the first *n* benchmark items during a trial run. Leave it unset to use the full benchmark.

## Run the pipeline

With the benchmark data, model files, and configured endpoints available, run all four stages:

```bash
pixi run python scripts/run_tasks.py
```

You can also run stages separately, in order:

```bash
pixi run python scripts/retrieve.py
pixi run python scripts/build_prompt.py
pixi run python scripts/inference.py
pixi run python scripts/evaluation.py
```

| Stage | Script | Output |
| --- | --- | --- |
| Retrieval | `scripts/retrieve.py` | Identifier definitions, usage snippets, sparse results, and timing data |
| Prompt construction | `scripts/build_prompt.py` | Completion prompts assembled from retrieved context |
| Inference | `scripts/inference.py` | Generated completions |
| Evaluation | `scripts/evaluation.py` | Aggregate and per-item metrics |

Output locations are set by each stage's `output_file` in `config.toml`. The evaluation JSON reports exact match (`EM`), edit similarity (`ES`), identifier exact match, and identifier F1. These metrics are computed against the selected benchmark's ground-truth completions.

## Repository layout

```text
codeusage/           Core benchmark, retrieval, prompt, inference, and evaluation code
scripts/             Entry points for each stage and the full pipeline
config.example.toml  Example experiment configuration
pyproject.toml       Python and Pixi environment specification
pixi.lock            Locked environment dependencies
```

## Citation

If you use this code, please cite **"CodeIds: Enhancing Repository-Level Code Completion with Identifier-Grounded Retrieval"** (WSDM '27). A BibTeX entry is not included yet.

## License

This repository does not currently include a license file.
