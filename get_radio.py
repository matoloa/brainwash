with open("src/lib/ui.py", "r") as f:
    lines = f.readlines()
start = -1
for i, line in enumerate(lines):
    if "def update_experiment_type_radio_buttons(" in line:
        start = i
        break
if start != -1:
    for i in range(start, min(start+50, len(lines))):
        print(lines[i], end="")
