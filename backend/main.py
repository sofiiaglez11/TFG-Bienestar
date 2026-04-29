from fastapi import FastAPI

app = FastAPI()




# to test the backend server
@app.get("/test")
def read_test():
    return {"message": "Hello, world!"}