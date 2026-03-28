with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

target = """        if getattr(uistate, "experiment_type", "time") == "PP":
            uistate.ax1.set_xlim(0.5, 1.5)
            uistate.ax2.set_xlim(0.5, 1.5)
            uistate.ax1.set_xticks([1])
            uistate.ax2.set_xticks([1])
            uistate.ax1.plot([1], [100], marker="o", color="white", markersize=10, zorder=100)
            uistate.ax2.plot([1], [100], marker="o", color="white", markersize=10, zorder=100)

        for axid in ["axm", "axe"]:
            axis = getattr(uistate, axid)"""

replacement = """        for axid in ["axm", "axe"]:
            axis = getattr(uistate, axid)"""

if target in content:
    content = content.replace(target, replacement)
    with open("src/lib/ui_plot.py", "w") as f:
        f.write(content)
    print("Success: Removed dummy blob")
else:
    print("Failed to remove dummy blob")
