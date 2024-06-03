import json
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.append("src")
import wslib

app = FastAPI()
ws_machine = wslib.MinistrySiteDataGetter()

origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:5173",
    "http://localhost:4173",
    "*",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

site_dict = dict()
with open("./urlList.json", encoding="utf-8") as f:
    site_dict = json.load(f)


@app.get("/")
async def get_root():
    return {"message": "Hello World"}


@app.get("/help")
async def get_help():
    return {"message": "Help"}


@app.get("/update")
async def update():
    n_news = ws_machine.update_all_data(site_dict)
    return {
        "msg": "SUCCESS",
        "nNewRecode": n_news,
    }


@app.get("/newSiteData")
async def new_site_data():
    n_new_sites = ws_machine.add_site(site_dict)
    return {"msg": "SUCCESS", "nNewSites": n_new_sites}
