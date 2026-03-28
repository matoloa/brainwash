with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

old_ax1 = """        ax1.set_ylim(uistate.zoom["output_ax1_ylim"])
        ax2.set_ylim(uistate.zoom["output_ax2_ylim"])
        ax1.set_xlim(uistate.zoom["output_xlim"])
        ax2.set_xlim(uistate.zoom["output_xlim"])"""

new_ax1 = """        ax1.set_ylim(uistate.zoom["output_ax1_ylim"])
        ax2.set_ylim(uistate.zoom["output_ax2_ylim"])
        ax1.set_xlim(uistate.zoom["output_xlim"])
        ax2.set_xlim(uistate.zoom["output_xlim"])
        if exp_type == "PP":
            ax1.set_xticks([1])
            ax2.set_xticks([1])"""

if old_ax1 in content:
    content = content.replace(old_ax1, new_ax1)
    with open("src/lib/ui_plot.py", "w") as f:
        f.write(content)
    print("Patched ticks in graphRefresh")
else:
    print("Failed")
