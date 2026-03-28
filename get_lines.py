with open("src/lib/ui_plot.py", "r") as f:
    for i, line in enumerate(f):
        if "Stim-mode aggregate lines" in line:
            print(f"Line {i}: {line.strip()}")
