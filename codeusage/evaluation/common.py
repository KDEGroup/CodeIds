from pydantic import BaseModel

class EvaluationItem(BaseModel):
    task_name: str
    idx: int
    ES: float
    EM: float
    identifier_EM: int
    identifier_F1: float

class EvaluationResult(BaseModel):
    count: int
    ES: float
    EM: float
    identifier_EM: float
    identifier_F1: float
    details: list[EvaluationItem]
