import json

from wslib import MinistrySiteDataGetter

site_dict = dict()
with open("./checkUrlList.json", encoding="utf-8") as f:
    site_dict = json.load(f)

ws_machine = MinistrySiteDataGetter()

n = 1

k = list(site_dict.keys())[n]

print(k)

data = ws_machine._scraper(k, site_dict[k])
print(data)
