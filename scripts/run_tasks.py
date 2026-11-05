import codeusage.config as config
from pathlib import Path
from scripts.retrieve import main as run_retrieve
from scripts.build_prompt import main as run_build_prompt
from scripts.inference import main as run_inference
from scripts.evaluation import main as run_evaluation
# config.settings.sample_n = None
run_retrieve()
run_build_prompt()
run_inference()
run_evaluation()