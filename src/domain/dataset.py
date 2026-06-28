from pydantic import BaseModel


class ColumnSchema(BaseModel):
    name: str
    type: str


class DatasetResponse(BaseModel):
    id: str
    filename: str
    row_count: int
    column_count: int
    schema_: list[ColumnSchema]
    sample_rows: list[dict]

    def model_dump_api(self) -> dict:
        d = self.model_dump()
        d["schema"] = d.pop("schema_")
        return d
