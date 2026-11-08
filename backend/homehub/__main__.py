import logging
import os
import warnings

import uvicorn

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

uvicorn.run("homehub.api:app", host="0.0.0.0", port=int(os.environ.get("HUB_PORT", "8080")))
