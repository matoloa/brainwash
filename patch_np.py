with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

old_np = """                        import warnings
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            ppr = (v2 / v1) * 100
                            # replace inf and -inf with nan
                            ppr[~np.isfinite(ppr)] = np.nan

                        import numpy as np"""

new_np = """                        import numpy as np
                        import warnings
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            ppr = (v2 / v1) * 100
                            # replace inf and -inf with nan
                            ppr[~np.isfinite(ppr)] = np.nan"""

if old_np in content:
    content = content.replace(old_np, new_np)
    with open("src/lib/ui_plot.py", "w") as f:
        f.write(content)
    print("Success: Fixed numpy import ordering")
else:
    print("Failed to find numpy block")
