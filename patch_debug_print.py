with open("src/lib/ui.py", "r") as f:
    content = f.read()

old_debug = """        # rec lines
        new_rec_show = {}
        for k, v in uistate.dict_rec_labels.items():
            visible = self._is_rec_visible(v, selected_ids, selected_stims, valid_pp_ids)
            v["line"].set_visible(visible)
            if "PPR" in k:
                print(f"DEBUG PPR LINE: {k} -> visible={visible}, selected_ids={selected_ids}, rec_id={v['rec_ID']}, dft_len={len(self.dict_ts.get(self.get_df_project().loc[v['rec_ID'], 'recording_name']) or [])}")
            if visible:
                new_rec_show[k] = v"""

new_debug = """        # rec lines
        new_rec_show = {}
        for k, v in uistate.dict_rec_labels.items():
            visible = self._is_rec_visible(v, selected_ids, selected_stims, valid_pp_ids)
            v["line"].set_visible(visible)
            if visible:
                new_rec_show[k] = v"""

if old_debug in content:
    content = content.replace(old_debug, new_debug)
    with open("src/lib/ui.py", "w") as f:
        f.write(content)
    print("Reverted debug print")
else:
    print("Failed")
