import re
with open("src/lib/ui.py", "r") as f:
    for line in f:
        if "table" in line.lower():
            if "tableProj" not in line and "tableStim" not in line and "tableGroup" not in line:
                print(line.strip())
