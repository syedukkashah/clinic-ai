from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

# In a real application, these would come from environment variables
ALLOWED_ORIGINS = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8000",
]

def setup_cors(app: FastAPI):
    """
    Configures CORS middleware for the FastAPI application.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
