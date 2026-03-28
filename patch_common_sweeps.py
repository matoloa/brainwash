with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

old_common = """                        for variant in ["raw", "norm"]:
                            self.plot_line(
                                f"{label} PPR {aspect} {variant}",
                                axid,
                                common_sweeps,
                                ppr,
                                color,
                                rec_ID,"""

new_common = """                        import numpy as np
                        for variant in ["raw", "norm"]:
                            self.plot_line(
                                f"{label} PPR {aspect} {variant}",
                                axid,
                                np.ones(len(common_sweeps)),
                                ppr,
                                color,
                                rec_ID,"""

if old_common in content:
    content = content.replace(old_common, new_common)
    with open("src/lib/ui_plot.py", "w") as f:
        f.write(content)
    print("Patched common_sweeps to be np.ones")
else:
    print("Failed")
