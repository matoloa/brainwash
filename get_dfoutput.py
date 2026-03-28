with open("src/lib/ui_plot.py", "r") as f:
    lines = f.readlines()
start = -1
for i, line in enumerate(lines):
    if "out_stim =" in line and "dfoutput" in line:
        start = i
        break
for i in range(start, min(start+20, len(lines))):
    print(lines[i], end="")
