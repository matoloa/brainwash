with open("src/lib/ui_plot.py", "r") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "is_pp and not skip_output" in line:
        for j in range(i, i+40):
            print(lines[j], end="")
        break
