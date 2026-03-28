with open("src/lib/ui.py", "r") as f:
    content = f.read()

old_mode = """        mode = getattr(uistate, "experiment_type", "time")
        if mode == "PP" and not has_exactly_two_stims:
            mode = "time" if has_sweep_hz else "sweep"
        elif mode in ["train", "io"] and not has_stims:
            mode = "time" if has_sweep_hz else "sweep"
        elif mode == "time" and not has_sweep_hz:"""

new_mode = """        mode = getattr(uistate, "experiment_type", "time")
        if mode in ["train", "io", "PP"] and not has_stims:
            mode = "time" if has_sweep_hz else "sweep"
        elif mode == "time" and not has_sweep_hz:"""

if old_mode in content:
    content = content.replace(old_mode, new_mode)
    with open("src/lib/ui.py", "w") as f:
        f.write(content)
    print("Success")
else:
    print("Not found")

