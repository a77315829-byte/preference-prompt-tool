"""Offline-container driver; never import on the host."""
import gc
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path


def main():
    assert importlib.metadata.version("evalplus") == "0.4.0.dev2"
    evaluator = importlib.import_module("evalplus.evaluate")
    # Same memory-saving scheduling wrapper as the separately validated controls.
    # Each candidate still runs in the official guarded child process.
    evaluator.ProcessPoolExecutor = ThreadPoolExecutor
    for batch in json.loads(Path("/datasets/batches.json").read_text()):
        dataset = batch["dataset"]
        assert dataset in ("humaneval", "mbpp")
        archive = Path("/datasets") / batch["file"]
        assert archive.parent == Path("/datasets")
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == batch["sha256"]
        loader = importlib.import_module("evalplus.data." + dataset)
        setattr(loader, dataset.upper() + "_OVERRIDE_PATH", str(archive))
        for condition, filename in batch["samples"].items():
            samples = Path("/work") / filename
            assert samples.parent == Path("/work")
            print(f"EVALUATING {dataset} {condition}", flush=True)
            evaluator.evaluate(dataset=dataset, samples=str(samples), parallel=1, test_details=True)
            gc.collect()


if __name__ == "__main__":
    main()
