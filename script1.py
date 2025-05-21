import json
from datetime import datetime as dt

from wslib import MinistrySiteDataGetter

site_dict = dict()
with open("./urlList.json", encoding="utf-8") as f:
    site_dict = json.load(f)

del site_dict["metiShingikai"]

ws_machine = MinistrySiteDataGetter()
ws_result = ws_machine.update_all_data(site_dict)

recode_dict = {
    "ws_result": ws_result,
    "timestamp": dt.now().strftime("%m/%d %H:%M:%S"),
}

with open("sample.json", "w") as f:
    json.dump(recode_dict, f)

print("DONE")
