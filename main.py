import json

from wslib import MinistrySiteDataGetter

site_dict = dict()
with open("./urlList.json", encoding="utf-8") as f:
    site_dict = json.load(f)

with open("/home/runner/firebase_credentials.json", "r") as f:
    print(f.readall())

print(site_dict)

ws_machine = MinistrySiteDataGetter()
ret = ws_machine.update_all_data(site_dict)

print(ret)
