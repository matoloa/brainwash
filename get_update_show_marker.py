with open("src/lib/ui.py", "r") as f:
    for i, line in enumerate(f):
        if "marker" in line and "update_show" in line:
            print(f"Line {i}: {line.strip()}")
