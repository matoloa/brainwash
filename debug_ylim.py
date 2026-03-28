with open("src/lib/ui.py", "r") as f:
    content = f.read()

old_ylim = """            finite = ydata[mask]
            if finite.size == 0:
                continue
            if finite.size == 1 and "marker" in line.get_label():  # skip physical point markers on axe/axm
                continue
            all_y.append(finite)"""

new_ylim = """            finite = ydata[mask]
            if finite.size == 0:
                continue
            if finite.size == 1 and "marker" in line.get_label():  # skip physical point markers on axe/axm
                continue
            if "PPR" in line.get_label():
                print(f"DEBUG YLIM PPR: {line.get_label()} size={finite.size} val={finite} mask={mask} x={xdata} y={ydata}")
            all_y.append(finite)"""

if old_ylim in content:
    content = content.replace(old_ylim, new_ylim)
    with open("src/lib/ui.py", "w") as f:
        f.write(content)
    print("Patched debug into _ylim_from_artists")
else:
    print("Failed")
