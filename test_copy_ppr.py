with open("src/lib/ui.py", "r") as f:
    content = f.read()

old_copy = """    def copy_output(self):
        if len(uistate.list_idx_select_recs) < 1:
            print("copy_output: nothing selected.")
            return
        selected_outputs = pd.DataFrame()
        for rec in uistate.list_idx_select_recs:
            p_row = self.get_df_project().loc[rec]
            output = self.get_dfoutput(p_row).copy()
            output.insert(0, "recording_name", p_row["recording_name"])
            output.insert(1, "gain", p_row["gain"])
            selected_outputs = pd.concat([selected_outputs, output], ignore_index=True)
        selected_outputs.to_clipboard(index=False)"""

new_copy = """    def copy_output(self):
        if len(uistate.list_idx_select_recs) < 1:
            print("copy_output: nothing selected.")
            return
        selected_outputs = pd.DataFrame()
        is_pp = getattr(uistate, "experiment_type", "time") == "PP"
        
        for rec in uistate.list_idx_select_recs:
            p_row = self.get_df_project().loc[rec]
            output = self.get_dfoutput(p_row).copy()
            output.insert(0, "recording_name", p_row["recording_name"])
            output.insert(1, "gain", p_row["gain"])
            
            if is_pp:
                out_sweeps = output[output["sweep"].notna()]
                out1 = out_sweeps[out_sweeps["stim"] == 1].set_index("sweep")
                out2 = out_sweeps[out_sweeps["stim"] == 2].set_index("sweep")
                common_sweeps = out1.index.intersection(out2.index).dropna()
                
                if not common_sweeps.empty:
                    o1 = out1.loc[common_sweeps]
                    o2 = out2.loc[common_sweeps]
                    
                    pp_df = pd.DataFrame()
                    pp_df["recording_name"] = o1["recording_name"]
                    pp_df["gain"] = o1["gain"]
                    pp_df["sweep"] = common_sweeps
                    
                    aspects = ["EPSP_amp", "EPSP_slope", "volley_amp", "volley_slope"]
                    for aspect in aspects:
                        if aspect in o1.columns and aspect in o2.columns:
                            v1 = o1[aspect].values.astype(float)
                            v2 = o2[aspect].values.astype(float)
                            import numpy as np
                            import warnings
                            with warnings.catch_warnings():
                                warnings.simplefilter("ignore")
                                ppr = (v2 / v1) * 100
                                ppr[~np.isfinite(ppr)] = np.nan
                            pp_df[f"PPR_{aspect}"] = ppr
                            
                    selected_outputs = pd.concat([selected_outputs, pp_df], ignore_index=True)
            else:
                selected_outputs = pd.concat([selected_outputs, output], ignore_index=True)
                
        selected_outputs.to_clipboard(index=False)"""

if old_copy in content:
    content = content.replace(old_copy, new_copy)
    with open("src/lib/ui.py", "w") as f:
        f.write(content)
    print("Success: Patched copy_output for PP mode")
else:
    print("Failed to find copy_output")

