with open("src/lib/ui_plot.py", "r") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "f\"{label} PPR {aspect} {variant}\"" in line:
        for j in range(max(0, i-5), min(len(lines), i+15)):
            print(f"{j}: {lines[j]}", end="")
