from pydantic import BaseModel

class TimeComsuming(BaseModel):
    find_last_ids_ms: int | None = None
    infer_types_ms: int | None = None
    ppl_ms: int | None = None
    find_usages_ms: int | None = None
    static_usage_ms: int | None = None
    ast_usage_ms: int | None = None
    sparse_ms: int | None = None
    reranking_ms: int | None = None

    @property
    def static_analysis_ms(self) -> int:
        return (self.find_last_ids_ms or 0) + (self.infer_types_ms or 0) + (self.find_usages_ms or 0)
    