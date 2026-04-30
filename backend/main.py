# lógica central del servidor con fastApi, aquí se importan las herramientas y recursos definidos en server.py y se definen los endpoints de la API

from fastapi import FastAPI

app = FastAPI()




# to test the backend server
@app.get("/test")
def read_test():
    return {"message": "Hello, world!"}