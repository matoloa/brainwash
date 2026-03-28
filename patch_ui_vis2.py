with open("src/lib/ui.py", "r") as f:
    content = f.read()

old_update_show = """        selected_ids = set(uistate.df_recs2plot["ID"])
        selected_stims = {stim + 1 for stim in uistate.list_idx_select_stims}  # stim_select is 0-based (indices) - convert to stims
        print(f"update_show, selected_ids: {selected_ids}, selected_stims: {selected_stims}")

        # rec lines
        new_rec_show = {}
        for k, v in uistate.dict_rec_labels.items():
            visible = self._is_rec_visible(v, selected_ids, selected_stims)
            v["line"].set_visible(visible)"""

new_update_show = """        selected_ids = set(uistate.df_recs2plot["ID"])
        selected_stims = {stim + 1 for stim in uistate.list_idx_select_stims}  # stim_select is 0-based (indices) - convert to stims
        print(f"update_show, selected_ids: {selected_ids}, selected_stims: {selected_stims}")

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

if old_update_show in content:
    content = content.replace(old_update_show, new_update_show)
    with open("src/lib/ui.py", "w") as f:
        f.write(content)
    print("Success")
else:
    print("Not found")

