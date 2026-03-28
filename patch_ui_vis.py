import re

with open("src/lib/ui.py", "r") as f:
    content = f.read()

# Replace _is_rec_visible definition
old_vis = """    def _is_rec_visible(self, v: dict, selected_ids: set, selected_stims: set) -> bool:
        \"\"\"Predicate: should this rec-label entry be visible given current UI state.\"\"\"
        if v.get("is_zero_width"):
            return False
        if v["rec_ID"] not in selected_ids:
            return False
        if v["stim"] is not None and v["stim"] not in selected_stims:
            return False"""

new_vis = """    def _is_rec_visible(self, v: dict, selected_ids: set, selected_stims: set, valid_pp_ids: set | None = None) -> bool:
        \"\"\"Predicate: should this rec-label entry be visible given current UI state.\"\"\"
        if v.get("is_zero_width"):
            return False
        if v["rec_ID"] not in selected_ids:
            return False
        if v["stim"] is not None and v["stim"] not in selected_stims:
            return False
        
        # Phase 0 PP mode display guard
        axis = v.get("axis")
        is_pp = getattr(uistate, "experiment_type", "time") == "PP"
        if is_pp and axis in ("ax1", "ax2"):
            if valid_pp_ids is not None and v["rec_ID"] not in valid_pp_ids:
                return False"""

content = content.replace(old_vis, new_vis)

# Update update_show calls
old_update_show = """        selected_ids = set(uistate.df_recs2plot["ID"])
        selected_stims = {stim + 1 for stim in uistate.list_idx_select_stims}  # stim_select is 0-based (indices) - convert to stims

        # rec lines
        new_rec_show = {}
        for k, v in uistate.dict_rec_labels.items():
            visible = self._is_rec_visible(v, selected_ids, selected_stims)
            v["line"].set_visible(visible)"""

new_update_show = """        selected_ids = set(uistate.df_recs2plot["ID"])
        selected_stims = {stim + 1 for stim in uistate.list_idx_select_stims}  # stim_select is 0-based (indices) - convert to stims

        is_pp = getattr(uistate, "experiment_type", "time") == "PP"
        valid_pp_ids = set()
        if is_pp:
            df_p = self.get_df_project()
            for rec_id in selected_ids:
                if rec_id in df_p.index:
                    rec_name = df_p.loc[rec_id, "recording_name"]
                    dft = self.dict_ts.get(rec_name)
                    if dft is not None and len(dft) == 2:
                        valid_pp_ids.add(rec_id)

        # rec lines
        new_rec_show = {}
        for k, v in uistate.dict_rec_labels.items():
            visible = self._is_rec_visible(v, selected_ids, selected_stims, valid_pp_ids)
            v["line"].set_visible(visible)"""

content = content.replace(old_update_show, new_update_show)

with open("src/lib/ui.py", "w") as f:
    f.write(content)

