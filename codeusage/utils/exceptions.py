from typing import TypeVar, Callable
from loguru import logger
from pydantic import BaseModel
import time
import traceback
from loguru import logger

import multiprocessing as mp
import time


class TimeCost(BaseModel):
    cost_ms: int = 0

T = TypeVar('T')
def exception_handler_wrapper(
    f: Callable[[], T],
    timeout_limit: float,
    default_value: T,
    multiprocessing: bool = False,
    time_cost: TimeCost | None = None
) -> T:
    if timeout_limit <= 0:
        return default_value
    if time_cost is None:
        time_cost = TimeCost()

    def call_with_time_limit() -> tuple[int, tuple[T, None] | tuple[None, Exception]]:
        start_s = time.time()
        try:
            ret = f()
            end_s = time.time()
            return round((end_s - start_s) * 1000), (ret, None)
        except Exception as e:
            logger.error(f"exception is {e}")
            traceback.print_exc()
            end_s = time.time()
            return round((end_s - start_s) * 1000), (None, e)


    result = default_value

    time_ms, retAndE = call_with_time_limit()
    time_cost.cost_ms = time_ms
    if retAndE[1] is not None:
        logger.warning(f"inner exception: {retAndE[1]}")
    else:
        result = retAndE[0]
    # because jedi cannot be interruptted.
    if time_ms > timeout_limit * 1000:
        time_cost.cost_ms = round(timeout_limit * 1000)
        result = default_value
    return result