"""Project pipelines."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kedro.pipeline import Pipeline

from .pipelines.data_embeddings.pipeline import create_pipeline as data_embeddings
from .pipelines.data_processing.pipeline import create_pipeline as data_processing


def register_pipelines() -> dict[str, Pipeline]:
    """Register the project's pipelines.

    Returns:
        A mapping from pipeline names to ``Pipeline`` objects.
    """
    dp = data_processing()
    de = data_embeddings()

    full_pipeline = dp + de

    return {
        "data_processing": dp,
        "data_embeddings": de,
        "__default__": full_pipeline,
    }
