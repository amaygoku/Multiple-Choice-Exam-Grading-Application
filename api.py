from backend.main import app


if __name__ == "__main__":
    import uvicorn

    print("Starting OMR Backend API on http://0.0.0.0:8000")
    print("API Documentation: http://0.0.0.0:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
