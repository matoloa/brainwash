with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

pp_block = """
        if is_pp and not skip_output:
            out_sweeps = dfoutput[dfoutput["sweep"].notna()]
            out1 = out_sweeps[out_sweeps["stim"] == 1].set_index("sweep")
            out2 = out_sweeps[out_sweeps["stim"] == 2].set_index("sweep")
            
            common_sweeps = out1.index.intersection(out2.index).dropna()
            if not common_sweeps.empty:
                o1 = out1.loc[common_sweeps]
                o2 = out2.loc[common_sweeps]
                
                configs = [
                    ("EPSP_amp", "ax1", settings.get("rgb_EPSP_amp", "blue")),
                    ("EPSP_slope", "ax2", settings.get("rgb_EPSP_slope", "red")),
                    ("volley_amp", "ax1", settings.get("rgb_volley_amp", "green")),
                    ("volley_slope", "ax2", settings.get("rgb_volley_slope", "orange")),
                ]
                
                for aspect, axid, color in configs:
                    if aspect in o1.columns and aspect in o2.columns:
                        v1 = o1[aspect].values.astype(float)
                        v2 = o2[aspect].values.astype(float)
                        
                        import warnings
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            ppr = (v2 / v1) * 100
                            # replace inf and -inf with nan
                            ppr[~np.isfinite(ppr)] = np.nan
                        
                        for variant in ["raw", "norm"]:
                            self.plot_line(
                                f"{label} PPR {aspect} {variant}",
                                axid,
                                common_sweeps,
                                ppr,
                                color,
                                rec_ID,
                                aspect=aspect,
                                stim=None,
                                variant=variant,
                                x_mode="sweep"
                            )

        # Stim-mode aggregate lines (always created when stim-mode rows exist;"""

old_target = """        # Stim-mode aggregate lines (always created when stim-mode rows exist;"""

if old_target in content:
    content = content.replace(old_target, pp_block)
    with open("src/lib/ui_plot.py", "w") as f:
        f.write(content)
    print("Success: added Phase 1/2 logic to addRow")
else:
    print("Failed")
