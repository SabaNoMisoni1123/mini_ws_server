import os

tmp_cred_path = os.getenv("FIREBASE_CRED_FNAME_TMP")
final_cred_path = os.getenv("FIREBASE_CRED_FNAME")

with open(tmp_cred_path, 'r') as f:
    content = f.read()

# 改行を適切に処理
content = content.replace('\\n', '\n')

with open(final_cred_path, 'w') as f:
    f.write(content)
