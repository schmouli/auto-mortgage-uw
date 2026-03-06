"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mortgage_underwriting.config import settings
from mortgage_underwriting.logger import logger

# Create app
app = FastAPI(
    title=settings.api.title,
    version=settings.api.version,
    debug=settings.api.debug,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.security.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": settings.api.version}

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Mortgage Underwriting System"}

# Register module routes would go here
# from mortgage_underwriting.modules.authentication.routes import router as auth_router
# app.include_router(auth_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api.host, port=settings.api.port)
