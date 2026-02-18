import functools
from typing import Any, Protocol, cast, runtime_checkable


# Define que o objeto deve ser chamável e ter um __name__
@runtime_checkable
class NamedCallable(Protocol):
    __name__: str

    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


def create_node_func(func: NamedCallable, **kwargs: Any) -> NamedCallable:
    """
    Creates a partial function (with predefined arguments), but preserves the name and documentation of the original function to ensure readable logs in Kedro.

    Args:
        func (Callable): A função original.
        **kwargs: Argumentos que queremos fixar.
    """
    partial_func = functools.partial(func, **kwargs)
    functools.update_wrapper(partial_func, func)
    return cast("NamedCallable", partial_func)
