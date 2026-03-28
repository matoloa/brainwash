with open("src/lib/ui_plot.py", "r") as f:
    for i, line in enumerate(f):
        if "settings = self.uistate.settings" in line:
            print(f"Line {i}: {line.strip()}")
