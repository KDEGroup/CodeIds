from typing import List
from loguru import logger
from codeusage.evaluation.metrics import compute_EM, compute_ES, compute_identifier_match
from codeusage.evaluation import EvaluationResult, EvaluationItem
from codeusage.interfaces.benchmark import load_benchmark
from operator import itemgetter
from pathlib import Path
from codeusage.config import settings
import json

def main():
    inference_result: list[str] = []
    with open(settings.evaluation.use_inference_file, "r") as f:
        inference_result = json.load(f)
    benchmark = load_benchmark()

    total = len(benchmark.data_list)

    result = EvaluationResult(
        count=total,
        EM=0.0,
        ES=0.0,
        identifier_F1=0.0,
        identifier_EM=0.0,
        details=[]
    )



    for idx, (benchmark_it, generation) in enumerate(zip(benchmark.data_list, inference_result, strict=True)):
        gt = benchmark_it.ground_truth
        ES = compute_ES(target=gt, prediction=generation)
        EM = compute_EM(target=gt, prediction=generation)
        identifier_EM, identifier_F1 = compute_identifier_match(
            prediction=generation,
            target=gt
        )
        result.ES += ES
        result.EM += EM
        result.identifier_F1 += identifier_F1
        result.identifier_EM += identifier_EM
        result.details.append(EvaluationItem(
            task_name=benchmark_it.task_name,
            idx=idx,
            ES=ES,
            EM=EM,
            identifier_EM=identifier_EM,
            identifier_F1=identifier_F1
        ))
    result.EM /= total
    result.ES /= total
    result.identifier_F1 /= total
    result.identifier_EM /= total
    logger.info("Evaluation completed.")
        


    logger.info(f"Batch count: {result.count}")
    logger.info(f"Batch ES: {result.ES}")
    logger.info(f"Batch EM: {result.EM}")
    logger.info(f"Batch identifier EM: {result.identifier_EM}")
    logger.info(f"Batch identifier F1: {result.identifier_F1}")
    output_file = settings.evaluation.output_file
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        json_result = result.model_dump_json(indent=4)
        f.write(json_result)
    logger.info(f"Evaluation completed and results saved in {output_file}")

if __name__ == "__main__":
    main()