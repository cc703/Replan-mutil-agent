"""Start the scheduler on loopback using the configured local port."""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "service.app:app", host="127.0.0.1", port=int(os.getenv("P7_SCHEDULER_PORT", "8000"))
    )
