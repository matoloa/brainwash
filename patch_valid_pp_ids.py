with open("src/lib/ui.py", "r") as f:
    content = f.read()

old_valid_pp = """        is_pp = getattr(uistate, "experiment_type", "time") == "PP"
        valid_pp_ids = set()
        if is_pp:
            df_p = self.get_df_project()
            for rec_id in selected_ids:
                if rec_id in df_p.index:
                    rec_name = df_p.loc[rec_id, "recording_name"]
                    dft = self.dict_ts.get(rec_name)
                    if dft is not None and len(dft) == 2:
                        valid_pp_ids.add(rec_id)"""

new_valid_pp = """        is_pp = getattr(uistate, "experiment_type", "time") == "PP"
        valid_pp_ids = set()
        if is_pp:
            df_p = self.get_df_project()
            for rec_id in selected_ids:
                matches = df_p[df_p["ID"] == rec_id]
                if not matches.empty:
                    rec_name = matches.iloc[0]["recording_name"]
                    dft = self.dict_ts.get(rec_name)
                    if dft is not None and len(dft) == 2:
                        valid_pp_ids.add(rec_id)"""

if old_valid_pp in content:
    content = content.replace(old_valid_pp, new_valid_pp)
    with open("src/lib/ui.py", "w") as f:
        f.write(content)
    print("Success: Fixed valid_pp_ids logic")
else:
    print("Failed to find old_valid_pp block")
