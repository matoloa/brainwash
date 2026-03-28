with open("src/lib/ui_plot.py", "r") as f:
    lines = f.readlines()
start = -1
for i, line in enumerate(lines):
    if "def addRow(" in line:
        start = i
        break
for i in range(start+100, min(start+200, len(lines))):
    print(lines[i], end="")
