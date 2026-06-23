import io

import pandas as pd
from fastapi import UploadFile, HTTPException

MAX_ROWS = 500_000


async def parse_upload(file: UploadFile) -> pd.DataFrame:
    """Parse an uploaded CSV or Excel file into a pandas DataFrame."""
    content = await file.read()
    name = file.filename or ""

    if name.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(content))
    elif name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(content))
    else:
        raise HTTPException(422, detail="Only .csv and .xlsx/.xls files are supported")

    if len(df) == 0:
        raise HTTPException(422, detail="Uploaded file has no data rows")

    if len(df) > MAX_ROWS:
        raise HTTPException(
            422,
            detail=f"File has {len(df)} rows; maximum is {MAX_ROWS}",
        )

    return df
