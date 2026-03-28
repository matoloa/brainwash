with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

old_pp_labels = """        elif exp_type == "PP":
            ax1.set_ylabel("PPR (%)")
            ax2.set_ylabel("PPR (%)")"""

new_pp_labels = """        elif exp_type == "PP":
            ax1.set_ylabel("PPR Amp (%)")
            ax2.set_ylabel("PPR Slope (%)")"""

if old_pp_labels in content:
    content = content.replace(old_pp_labels, new_pp_labels)
    with open("src/lib/ui_plot.py", "w") as f:
        f.write(content)
    print("Success")
else:
    print("Failed")
