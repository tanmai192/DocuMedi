from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def home():
    return {"message": "Patient Case-Taking System Backend is running!"}