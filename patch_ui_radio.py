import re

with open("src/lib/ui.py", "r") as f:
    content = f.read()

# Replace variables block
old_block = """        has_stims = False
        has_sweep_hz = False
        if uistate.list_idx_select_recs:
            df_p = self.get_df_project()
            for idx in uistate.list_idx_select_recs:
                row = df_p.loc[idx]
                rec = row["recording_name"]
                dft = self.dict_ts.get(rec)
                if dft is not None and len(dft) >= 1:
                    has_stims = True
                if pd.notna(row.get("sweep_hz")):
                    has_sweep_hz = True"""

new_block = """        has_stims = False
        has_sweep_hz = False
        has_exactly_two_stims = True
        if uistate.list_idx_select_recs:
            df_p = self.get_df_project()
            for idx in uistate.list_idx_select_recs:
                row = df_p.loc[idx]
                rec = row["recording_name"]
                dft = self.dict_ts.get(rec)
                if dft is not None:
                    if len(dft) >= 1:
                        has_stims = True
                    if len(dft) != 2:
                        has_exactly_two_stims = False
                else:
                    has_exactly_two_stims = False
                if pd.notna(row.get("sweep_hz")):
                    has_sweep_hz = True
        else:
            has_exactly_two_stims = False"""

content = content.replace(old_block, new_block)

# Replace PP enable
old_pp_en = """        if hasattr(self, "radioButton_type_PP"):
            self.radioButton_type_PP.setEnabled(True)"""

new_pp_en = """        if hasattr(self, "radioButton_type_PP"):
            self.radioButton_type_PP.setEnabled(has_exactly_two_stims)"""

content = content.replace(old_pp_en, new_pp_en)

# Replace mode fallback
old_mode = """        mode = getattr(uistate, "experiment_type", "time")
        if mode in ["train", "io", "PP"] and not has_stims:
            mode = "time" if has_sweep_hz else "sweep"
        elif mode == "time" and not has_sweep_hz:"""

new_mode = """        mode = getattr(uistate, "experiment_type", "time")
        if mode == "PP" and not has_exactly_two_stims:
            mode = "time" if has_sweep_hz else "sweep"
        elif mode in ["train", "io"] and not has_stims:
            mode = "time" if has_sweep_hz else "sweep"
        elif mode == "time" and not has_sweep_hz:"""

content = content.replace(old_mode, new_mode)

with open("src/lib/ui.py", "w") as f:
    f.write(content)
