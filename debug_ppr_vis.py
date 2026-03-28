import sys
import pickle

with open("src/lib/ui.py", "r") as f:
    content = f.read()

new_update_show = """        # rec lines
        new_rec_show = {}
        for k, v in uistate.dict_rec_labels.items():
            visible = self._is_rec_visible(v, selected_ids, selected_stims, valid_pp_ids)
            v["line"].set_visible(visible)
            if "PPR" in k:
                print(f"DEBUG PPR LINE: {k} -> visible={visible}, selected_ids={selected_ids}, rec_id={v['rec_ID']}, dft_len={len(self.dict_ts.get(self.get_df_project().loc[v['rec_ID'], 'recording_name']) or [])}")
            if visible:
                new_rec_show[k] = v"""

old_update_show = """        # rec lines
        new_rec_show = {}
        for k, v in uistate.dict_rec_labels.items():
            visible = self._is_rec_visible(v, selected_ids, selected_stims, valid_pp_ids)
            v["line"].set_visible(visible)
            if visible:
                new_rec_show[k] = v"""

if old_update_show in content:
    content = content.replace(old_update_show, new_update_show)
    with open("src/lib/ui.py", "w") as f:
        f.write(content)
    print("Patched update_show with debug prints")
