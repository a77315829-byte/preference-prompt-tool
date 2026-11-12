"""Container-only driver for the official evaluator, with bounded dataset batches.

Do not import this on the host: evalplus lives only in the pinned Docker image.
No model generation or provider arguments are accepted.
"""
import gc
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path
import platform


def main():
    version = importlib.metadata.version("evalplus")
    if version != "0.4.0.dev2":
        raise RuntimeError(f"Unexpected EvalPlus package: {version}")
    print(json.dumps({"evalplus": version, "python": platform.python_version()}), flush=True)
    evaluator = importlib.import_module("evalplus.evaluate")
    # The process-pool queue serializes large reference outputs into additional
    # copies (>0.7GB for one MBPP batch). A single scheduling thread shares those
    # read-only outputs. Official untrusted_check still executes EACH candidate
    # in its own guarded child process; Docker isolation and oracles are unchanged.
    evaluator.ProcessPoolExecutor = ThreadPoolExecutor

    manifest = json.loads(Path("/datasets/batches.json").read_text())
    for batch in manifest:
        dataset = batch["dataset"]
        if dataset not in ("humaneval", "mbpp"):
            raise ValueError("Unsupported dataset")
        dataset_path = Path("/datasets") / batch["file"]
        if dataset_path.parent != Path("/datasets"):
            raise ValueError("Invalid dataset path")
        if hashlib.sha256(dataset_path.read_bytes()).hexdigest() != batch["sha256"]:
            raise ValueError("Batch input hash mismatch")
        loader = importlib.import_module("evalplus.data." + dataset)
        # Same official override mechanism as the documented environment variables,
        # updated between calls because all batches share one interpreter.
        setattr(loader, dataset.upper() + "_OVERRIDE_PATH", str(dataset_path))
        for control in ("reference", "negative"):
            samples = Path("/work") / batch[control]
            if samples.parent != Path("/work"):
                raise ValueError("Invalid sample path")
            print(f"CONTROL {dataset} {batch['index']} {control} ({len(batch['task_ids'])} tasks)", flush=True)
            evaluator.evaluate(dataset=dataset, samples=str(samples), parallel=1, test_details=True)
            gc.collect()


if __name__ == "__main__":
    main()
