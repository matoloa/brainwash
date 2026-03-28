with open("src/lib/ui.py", "r") as f:
    content = f.read()

old_vis = """        is_io = getattr(uistate, "experiment_type", "time") == "io"
        if x_mode is not None and x_mode != uistate.x_axis:
            if not (x_mode == "sweep" and uistate.x_axis == "time"):
                return False"""

new_vis = """        is_io = getattr(uistate, "experiment_type", "time") == "io"
        if x_mode is not None and x_mode != uistate.x_axis:
            if not (x_mode == "sweep" and uistate.x_axis == "time"):
                if "PPR" in v.get("line").get_label():
                    print(f"PPR HIDDEN BY x_mode: {x_mode} != {uistate.x_axis}")
                return False"""

if old_vis in content:
    content = content.replace(old_vis, new_vis)
    with open("src/lib/ui.py", "w") as f:
        f.write(content)
    print("Patched debug into _is_rec_visible x_mode")
else:
    print("Failed to find x_mode check")
