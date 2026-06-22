from dotenv import load_dotenv
load_dotenv()  # loads .env into os.environ before settings are constructed

import uvicorn
from data_analyst.config.settings import get_settings


def main() -> None:
    s = get_settings()
    uvicorn.run("data_analyst.api:app", host="0.0.0.0", port=s.port, reload=False)


if __name__ == "__main__":
    main()
