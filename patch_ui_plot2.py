with open("src/lib/ui_plot.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "zorder = 0 if width > 1 else 1" in line:
        # inside plot_line
        new_lines.append(line)
        new_lines.append("        if axid in [\"ax1\", \"ax2\"] and getattr(self.uistate, \"experiment_type\", \"time\") == \"PP\":\n")
        new_lines.append("            # Phase 0 display guard\n")
        new_lines.append("            if not hasattr(self, '_pp_skip_cache'): self._pp_skip_cache = {}\n")
        new_lines.append("            if rec_ID not in self._pp_skip_cache:\n")
        new_lines.append("                try:\n")
        new_lines.append("                    df_p = self.uistate.ui.get_df_project()\n")
        new_lines.append("                    rec = df_p.loc[rec_ID, \"recording_name\"]\n")
        new_lines.append("                    dft = self.uistate.ui.dict_ts.get(rec)\n")
        new_lines.append("                    self._pp_skip_cache[rec_ID] = dft is None or len(dft) != 2\n")
        new_lines.append("                except:\n")
        new_lines.append("                    self._pp_skip_cache[rec_ID] = False\n")
        new_lines.append("            if self._pp_skip_cache.get(rec_ID, False):\n")
        new_lines.append("                return\n")
    elif "line.set_visible(False)" in line and "plot_hline" in "".join(lines[max(0, len(new_lines)-20):]):
        # plot_hline doesn't have width
        # actually, plot_hline definition:
        # def plot_hline(self, label, axid, y, color, rec_ID, aspect=None, stim=None, x_mode=None):
        new_lines.append(line)
    else:
        new_lines.append(line)
