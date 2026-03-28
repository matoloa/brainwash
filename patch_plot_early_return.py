with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

def patch_func(func_name, content):
    old_def = f"    def {func_name}("
    # find where the definition ends
    idx = content.find(old_def)
    if idx == -1: return content
    colon_idx = content.find("):", idx) + 2
    # we want to insert early return right after the signature
    signature = content[idx:colon_idx]
    
    early_return = """
        is_pp = getattr(self.uistate, "experiment_type", "time") == "PP"
        if is_pp and axid in ("ax1", "ax2") and "PPR" not in label:
            return"""
    
    return content[:colon_idx] + early_return + content[colon_idx:]

content = patch_func("plot_line", content)
content = patch_func("plot_hline", content)

with open("src/lib/ui_plot.py", "w") as f:
    f.write(content)
print("Success: Patched plot_line and plot_hline")
