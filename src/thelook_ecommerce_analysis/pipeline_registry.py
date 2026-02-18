"""Project pipelines."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kedro.framework.project import find_pipelines

if TYPE_CHECKING:
    from kedro.pipeline import Pipeline

from .pipelines.data_processing.pipeline import create_pipeline as data_processing


def register_pipelines() -> dict[str, Pipeline]:
    """Register the project's pipelines.

    Returns:
        A mapping from pipeline names to ``Pipeline`` objects.
    """
    pipelines = find_pipelines(raise_errors=True)

    pipelines["__default__"] = data_processing()
    return pipelines
