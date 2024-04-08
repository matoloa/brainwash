# Functions that are not in use anymore, but might be useful again in the future
def setGraphGroups(self, ax1, ax2, list_color): # TODO: deprecate
    print(f"setGraphGroups: {self.dict_groups['list_ID']}")
    df_p = self.get_df_project()
    for i_color, group in enumerate(self.dict_groups['list_ID']):
        dfgroup = df_p[df_p['groups'].str.split(',').apply(lambda x: group in x)]
        if uistate.group_show[group] == False:
            if verbose:
                print(f"Checkbox for group {group} is not checked")
            continue
        if dfgroup.empty:
            if verbose:
                print(f"No data in group {group}")
            continue

        # abort if any recording in group is a str
        if dfgroup['sweeps'].apply(lambda x: isinstance(x, str)).any():
            if verbose:
                print(f"Analyse all recordings in {group} to show group output.")
            continue
        self.plotGroup(ax1, ax2, group, list_color[i_color])

def plotGroup(self, ax1, ax2, group, groupcolor, alpha=0.3): # TODO: deprecate
    dfgroup_mean = self.get_dfgroupmean(key_group=group)
        # Errorbars, EPSP_amp_SEM and EPSP_slope_SEM are already a column in df
        # print(f'dfgroup_mean.columns: {dfgroup_mean.columns}')
    if dfgroup_mean['EPSP_amp_mean'].notna().any() & uistate.checkBox['EPSP_amp']:
        _ = sns.lineplot(data=dfgroup_mean, y="EPSP_amp_mean", x="sweep", ax=ax1, color=groupcolor, linestyle='--', alpha=alpha)
        ax1.fill_between(dfgroup_mean.sweep, dfgroup_mean.EPSP_amp_mean + dfgroup_mean.EPSP_amp_SEM, dfgroup_mean.EPSP_amp_mean - dfgroup_mean.EPSP_amp_SEM, alpha=0.3, color=groupcolor)
        ax1.axhline(y=0, linestyle='--', color=groupcolor, alpha = 0.4)
    if dfgroup_mean['EPSP_slope_mean'].notna().any() & uistate.checkBox['EPSP_slope']:
        _ = sns.scatterplot(data=dfgroup_mean, y="EPSP_slope_mean", x="sweep", ax=ax2, color=groupcolor, s=5, alpha=alpha)
        ax2.fill_between(dfgroup_mean.sweep, dfgroup_mean.EPSP_slope_mean + dfgroup_mean.EPSP_slope_SEM, dfgroup_mean.EPSP_slope_mean - dfgroup_mean.EPSP_slope_SEM, alpha=0.3, color=groupcolor)
        ax2.axhline(y=0, linestyle=':', color=groupcolor, alpha = 0.4)

#uisub.setGraphSelected(df_analyzed=df_analyzed, ax1=ax1, ax2=ax2)
    # if just one selected, plot its group's mean
    # if len(df_analyzed) == 1:
    #     list_group = df_analyzed['groups'].iloc[0].split(',')
    #     for group in list_group:
    #         if group != " ":
    #             df_groupmean = self.get_dfgroupmean(key_group=group)
    #             if not df_groupmean.empty and uistate.group_show[group]:
    #                 group_index = self.dict_groups['list_ID'].index(group)
    #                 color = self.dict_groups['list_group_colors'][group_index]
    #                 self.plotGroup(ax1, ax2, group, color, alpha=0.05)
    # else: # if none of the selected are analyzed, plot groups instead
    #    if self.dict_groups['list_ID']:
    #        self.setGraphGroups(ax1, ax2, self.dict_groups['list_group_colors'])




    '''         
    @QtCore.pyqtSlot(list)
    def slotPrintPaths(self, mypaths):
        if verbose:
            print(f"mystr: {mypaths}")
        strmystr = "\n".join(sorted(["/".join(i.split("/")[-2:]) for i in mypaths]))
        self.textBrowser.setText(strmystr)
        list_display_names = ["/".join(i.split("/")[-2:]) for i in mypaths]
        dftable = pd.DataFrame({"path_source": mypaths, "recording_name": list_display_names})
    '''