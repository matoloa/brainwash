with open("src/lib/ui.py", "r") as f:
    lines = f.readlines()
start = -1
for i, line in enumerate(lines):
    if "def eventDragReleased(" in line:
        start = i
        break
for i in range(start, min(start+40, len(lines))):
    print(lines[i], end="")
