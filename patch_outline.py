import re

with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

# patch updateOutLineFromDf
old_outdf = """        if df_stim.empty or column not in df_stim.columns:
            print(f"updateOutLineFromDf: no data for stim={stim_num} col={column}, falling back to updateOutLine")
            self.updateOutLine(label)
            return
        linedict = self.uistate.dict_rec_labels[label]"""

new_outdf = """        if df_stim.empty or column not in df_stim.columns:
            print(f"updateOutLineFromDf: no data for stim={stim_num} col={column}, falling back to updateOutLine")
            self.updateOutLine(label)
            return
            
        if label not in self.uistate.dict_rec_labels:
            is_pp = getattr(self.uistate, "experiment_type", "time") == "PP"
            if is_pp:
                import numpy as np
                rec_label = label.split(" - stim ")[0]
                aspect = column.replace("_norm", "")
                out_sweeps = dfoutput[dfoutput["sweep"].notna()]
                out1 = out_sweeps[out_sweeps["stim"] == 1].set_index("sweep")
                out2 = out_sweeps[out_sweeps["stim"] == 2].set_index("sweep")
                common_sweeps = out1.index.intersection(out2.index).dropna()
                if not common_sweeps.empty:
                    o1 = out1.loc[common_sweeps]
                    o2 = out2.loc[common_sweeps]
                    if aspect in o1.columns and aspect in o2.columns:
                        v1 = o1[aspect].values.astype(float)
                        v2 = o2[aspect].values.astype(float)
                        import warnings
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            ppr = (v2 / v1) * 100
                            ppr[~np.isfinite(ppr)] = np.nan
                        
                        for variant in ["raw", "norm"]:
                            ppr_label = f"{rec_label} PPR {aspect} {variant}"
                            if ppr_label in self.uistate.dict_rec_labels:
                                linedict = self.uistate.dict_rec_labels[ppr_label]
                                line = linedict["line"]
                                line.set_xdata(common_sweeps)
                                line.set_ydata(ppr)
            return
            
        linedict = self.uistate.dict_rec_labels[label]"""

content = content.replace(old_outdf, new_outdf)

# patch updateOutLine
old_out = """    def updateOutLine(self, label):
        print(f"updateOutLine: {label}")
        mouseover_out = self.uistate.mouseover_out
        if mouseover_out is None:
            print(f"updateOutLine: mouseover_out is None, skipping update for '{label}'")
            return
        linedict = self.uistate.dict_rec_labels[label]"""

new_out = """    def updateOutLine(self, label):
        print(f"updateOutLine: {label}")
        mouseover_out = self.uistate.mouseover_out
        if mouseover_out is None:
            print(f"updateOutLine: mouseover_out is None, skipping update for '{label}'")
            return
        if label not in self.uistate.dict_rec_labels:
            return
        linedict = self.uistate.dict_rec_labels[label]"""

content = content.replace(old_out, new_out)

with open("src/lib/ui_plot.py", "w") as f:
    f.write(content)
print("Patched updateOutLineFromDf and updateOutLine")
