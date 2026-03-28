with open("src/lib/ui.py", "r") as f:
    content = f.read()

old_vis = """        aspect = v.get("aspect")
        axis = v.get("axis")
        if aspect and not uistate.checkBox.get(aspect, True):
            if axis == "axe" or not is_io:
                return False"""

new_vis = """        aspect = v.get("aspect")
        axis = v.get("axis")
        if aspect and not uistate.checkBox.get(aspect, True):
            if axis == "axe" or not is_io:
                if "PPR" in v.get("line").get_label():
                    print(f"PPR HIDDEN BY aspect checkbox: {aspect} is unchecked")
                return False"""

if old_vis in content:
    content = content.replace(old_vis, new_vis)
    with open("src/lib/ui.py", "w") as f:
        f.write(content)
    print("Patched debug into _is_rec_visible aspect")
else:
    print("Failed to find aspect check")
