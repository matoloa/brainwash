with open("src/lib/ui.py", "r") as f:
    content = f.read()

old_vis = """        # Phase 0 PP mode display guard
        axis = v.get("axis")
        is_pp = getattr(uistate, "experiment_type", "time") == "PP"
        if is_pp and axis in ("ax1", "ax2"):
            if valid_pp_ids is not None and v["rec_ID"] not in valid_pp_ids:
                return False"""

new_vis = """        # Phase 0 PP mode display guard
        axis = v.get("axis")
        is_pp = getattr(uistate, "experiment_type", "time") == "PP"
        if is_pp and axis in ("ax1", "ax2"):
            if valid_pp_ids is not None and v["rec_ID"] not in valid_pp_ids:
                if "PPR" in v.get("line").get_label():
                    print(f"PPR HIDDEN BY PP GUARD: {v['rec_ID']} not in {valid_pp_ids}")
                return False"""

if old_vis in content:
    content = content.replace(old_vis, new_vis)
    with open("src/lib/ui.py", "w") as f:
        f.write(content)
    print("Patched debug into _is_rec_visible")
