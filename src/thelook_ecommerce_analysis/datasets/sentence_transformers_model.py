from typing import Any

from kedro.io import AbstractDataset
from sentence_transformers import SentenceTransformer

_MODEL_CACHE = {}


class SentenceTransformerDataset(AbstractDataset[SentenceTransformer, Any]):
    def __init__(
        self,
        model_name: str,
        device: str = "cpu",
        metadata: dict[str, Any] | None = None,
    ):
        self._model_name = model_name
        self._device = device

    def _load(self) -> SentenceTransformer:
        # Carrega na RAM/VRAM apenas na primeira vez que o Kedro acionar o método
        if self._model_name not in _MODEL_CACHE:
            _MODEL_CACHE[self._model_name] = SentenceTransformer(
                self._model_name, device=self._device
            )

        # Nas próximas chamadas, retorna instantaneamente o modelo já em memória
        return _MODEL_CACHE[self._model_name]

    def _save(self, data: Any) -> None:
        raise NotImplementedError("Este dataset é apenas para leitura.")

    def _describe(self) -> dict[str, Any]:
        return {"model_name": self._model_name, "device": self._device}
