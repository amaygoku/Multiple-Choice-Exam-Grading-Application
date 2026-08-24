import os
import re

out = open('scratch/matches.txt', 'w', encoding='utf-8')

def check_file(path):
    try:
        content = open(path, 'r', encoding='utf-8', errors='ignore').read()
        for match in re.findall(r'"[^"]{150,250}"|\'[^\']{150,250}\'', content):
            stripped = match[1:-1]
            if any(c in stripped for c in 'đĐàáảãạêô'):
                out.write(f"File: {path} (len {len(stripped)})\n")
                out.write(stripped + "\n")
                out.write("=" * 60 + "\n")
    except Exception as e:
        pass

for r, d, files in os.walk('.'):
    if any(x in r for x in ['node_modules', 'zipgrade-web', '.git', '.venv', 'crnn-pytorch-master']):
        continue
    for f in files:
        if f.endswith(('.py', '.txt', '.json', '.yml', '.yaml', '.ipynb')):
            check_file(os.path.join(r, f))

out.close()
print("Done writing matches!")
