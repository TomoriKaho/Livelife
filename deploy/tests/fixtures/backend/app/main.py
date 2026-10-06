"""Infrastructure smoke fixture, not the project's #24 backend."""
from fastapi import FastAPI

app = FastAPI()


@app.get("/test/hello")
def hello():
    return {"message": "hello world"}
