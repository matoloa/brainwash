import sys
with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

new_common = """                        import numpy as np
                        print(f"DEBUG PP: aspect={aspect}, len(common_sweeps)={len(common_sweeps)}, v1={v1}, v2={v2}, ppr={ppr}")
                        for variant in ["raw", "norm"]:
                            self.plot_line(
                                f"{label} PPR {aspect} {variant}",
                                axid,
                                np.ones(len(common_sweeps)),"""

old_common = """                        import numpy as np
                        for variant in ["raw", "norm"]:
                            self.plot_line(
                                f"{label} PPR {aspect} {variant}",
                                axid,
                                np.ones(len(common_sweeps)),"""

if old_common in content:
    content = content.replace(old_common, new_common)
    with open("src/lib/ui_plot.py", "w") as f:
        f.write(content)
    print("Patched debug prints into ui_plot.py")
else:
    print("Failed to find old_common")
