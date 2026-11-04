"""FastAPI entry points retained while coding_gepa shares the bounded GEPA runner."""
from coding_instructions import build_coding_instructions
from coding_gepa import HEADING, MAX_MODEL_CALLS, MAX_REFLECTION_CALLS, METRIC_CALLS, compose_prompt, optimize_coding


def fastapi_draft(raw):
    draft = build_coding_instructions(raw)
    if draft['profile']['language'].casefold() != 'python' or draft['profile']['framework'].casefold() != 'fastapi':
        raise ValueError('현재 GEPA 개선은 Python · FastAPI 조합에서 사용할 수 있어요.')
    return draft


def optimize_fastapi(profile, *, task_model, reflection_model, progress=None, generate=None, optimizer=None):
    fastapi_draft(profile)
    return optimize_coding(profile, task_model=task_model, reflection_model=reflection_model,
                           progress=progress, generate=generate, optimizer=optimizer)
