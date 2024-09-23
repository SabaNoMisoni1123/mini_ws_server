import json

import wslib

site_dict = dict()
new_site_dict = dict()
with open("./urlList.json", encoding="utf-8") as f:
    site_dict = json.load(f)

with open("./checkUrlList.json", encoding="utf-8") as f:
    new_site_dict = json.load(f)

#  新しいキーがあればsite_dictに追加

for k in new_site_dict.keys():
    if k not in site_dict.keys():
        print("New source:", k)
        site_dict[k] = new_site_dict[k]

# データベースへの反映
ws_machine = wslib.MinistrySiteDataGetter()
ws_machine.add_site(site_dict)
print("DONE")
