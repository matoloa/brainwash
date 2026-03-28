import re
with open("src/lib/ui.py", "r") as f:
    for line in f:
        if "set_ylabel" in line:
            print(line.strip())
with open("src/lib/ui_plot.py", "r") as f:
    for line in f:
        if "set_ylabel" in line:
            print(line.strip())
