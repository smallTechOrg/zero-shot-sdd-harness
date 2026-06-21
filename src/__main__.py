import uvicorn
from src.config import get_settings

if __name__ == "__main__":
    s = get_settings()
    uvicorn.run("src.api.main:app", host=s.host, port=s.port, reload=False)
