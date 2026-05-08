import uvicorn
import sys

if __name__ == "__main__":
    sys.stdout.write("Starting backend server on http://127.0.0.1:8000...\n")
    sys.stdout.flush()
    uvicorn.run("main:app", host="127.0.0.1", port=8000, log_level="info")
