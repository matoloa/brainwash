import pandas as pd
import pickle

class UIstate:
    def __init__(self):
        self.reset()

    def reset(self): # (re)set all persisted states
        print("UIstate: reset")
        self.version = "0.0.0"
        self.colors = ['#808080', '#00BFFF', '#008000', '#FF8080', '#006666', '#9ACD32', '#D2691E', '#FFD700', '#0000FF']
        self.splitter = {
            'h_splitterMaster': [0.105, 0.04, 0.795, 0.09],
            'v_splitterGraphs': [0.2, 0.5, 0.3],
        }
        self.viewTools = { # these are cycled by uisub.connectUIstate; framename: [title, visible]
            'frameToolStim': ["Stim detection", True],
            'frameToolAspect': ["Aspect toggles", True],
            'frameToolScaling': ["Output Scaling", True],
            'frameToolPairedStim': ["Paired stims", False],
            'frameToolExport': ["Image Export", False],
        }
        self.checkBox = { # these are cycled by uisub.connectUIstate; maintain format!
            'EPSP_amp': True,
            'EPSP_slope': True,
            'volley_amp': False,
            'volley_slope': False,
            'force1stim': False, # prevent splitting of channels when multiple stims are detected
            'show_all_events': False, # show ghosts of non-selected events in eventgraph output graph
            'timepoints_per_stim': False, # allow setting (non-uniform) timepoints per stim
            'output_per_stim': False, # output per stim (for binned trains) instead of per sweep (for consecutive sweeps)
            'output_ymin0': True, # set output y-axis minimum to 0
            # break these out to separate mod-class?
            'norm_EPSP': False, # show normalized EPSPs (they're always calculated)
            'paired_stims': False, # Recs are paired: output per pair is Intervention / Control
        }
        self.lineEdit = { # storage of user input; used to update df_t
            'norm_EPSP_from': 0,
            'norm_EPSP_to': 0,
            'EPSP_amp_halfwidth_ms':   0,   # in ms here (visible to user). NB: in s in df_t!
            'volley_amp_halfwidth_ms': 0, # in ms here (visible to user). NB: in s in df_t!
        }
        self.settings = {
            'event_start': -0.005, # in relation to current t_stim
            'event_end': 0.05,
            'precision': 4, # TODO: fix hardcoded precision
            # colors and alpha
            'rgb_EPSP_amp': (0.2, 0.2, 1),
            'rgb_EPSP_slope': (0.5, 0.5, 1),
            'rgb_volley_amp': (1, 0.2, 1),
            'rgb_volley_slope': (1, 0.5, 1),
            'alpha_mark': 0.4,
            'alpha_line': 1,
        }
        self.zoom = {
            'mean_xlim': (0, 1),
            'mean_ylim': (-1, 1),
            'event_xlim': (self.settings['event_start']/2, self.settings['event_end']/2),
            'event_ylim': (-0.001, 0.0002),
            'output_xlim': (0, None),
            'output_ax1_ylim': (0, 1.2),
            'output_ax2_ylim': (0, 1.2),
        }
        self.default_dict_t = { # default values for df_t(imepoints)
            'stim': 0,
            't_stim': 0,
            't_stim_method': 0,
            't_stim_params': 0,
            't_volley_slope_width': 0.0003,
            't_volley_slope_halfwidth': 0.0001,
            't_volley_slope_start': 0,
            't_volley_slope_end': 0,
            't_volley_slope_method': 'auto detect',
            't_volley_slope_params': 'NA',
            'volley_slope_mean': 0,
            't_volley_amp': 0,
            't_volley_amp_halfwidth': 0,
            't_volley_amp_method': 'auto detect',
            't_volley_amp_params': 'NA',
            'volley_amp_mean': 0,
            't_VEB': 0,
            't_VEB_method': 0,
            't_VEB_params': 0,
            't_EPSP_slope_width': 0.0007,
            't_EPSP_slope_halfwidth': 0.0003,
            't_EPSP_slope_start': 0,
            't_EPSP_slope_end': 0,
            't_EPSP_slope_method': 'auto detect',
            't_EPSP_slope_params': 'NA',
            't_EPSP_amp': 0,
            't_EPSP_amp_halfwidth': 0,
            't_EPSP_amp_method': 'auto detect',
            't_EPSP_amp_params': 'NA',
            'norm_output_from': 0,
            'norm_output_to': 0,
        }

    # Do NOT persist these
        self.pushButtons = { # these are cycled by uisub.connectUIstate; buttonname: methodname
            'pushButton_stim_detect': 'triggerStimDetect',
            'pushButton_EPSP_amp_width_set_all': 'trigger_set_EPSP_amp_width_all',
            'pushButton_volley_amp_width_set_all': 'trigger_set_volley_amp_width_all',
            'pushButton_norm_range_set_all': 'trigger_set_norm_range_all',
        }
        self.x_select = { # selected ranges on mean- and output graphs
            'mean_start': None,
            'mean_end': None,
            'output_start': None,
            'output_end': None,
        }

        #self.darkmode = False # set by global bw cfg
        self.axm = None # axis of mean graph (top)
        self.axe = None # axis of event graph (middle)
        self.ax1 = None # axis of output for amplitudes (bottom graph)
        self.ax2 = None # axis of output for slopes (bottom graph)
        self.frozen = False # True if ui is frozen
        self.rec_select = [] # list of selected indices in uisub.tableProj
        self.stim_select = [0] # list of selected indices in uisub.tableStim; default to first
        self.df_recs2plot = None # df_project copy, filtered to selected AND parsed recordings (or all parsed, if none are selected)
        self.dict_rec_labels = {} # dict of dicts of all plotted recordings. {key:label(str): {rec_ID: str, stim: int, aspect: str, axis: str, line: 2DlineObject}}
        self.dict_rec_show = {} # copy containing only visible recs
        self.dict_group_labels = {} # dict of dicts of all plotted groups: {key:label(str): {group_ID: int, stim: int, aspect: str, axis: str, line: 2DlineObject}, fill: 2DfillObject}
        self.new_indices = [] # list of indices in uisub.df_project for freshly parsed recordings; used by uisub.graphPreload()
        # TODO: deprecate these
        self.dfp_row_copy = None # copy of selected row in uisub.tableProj
        self.dft_copy = None # copy of dft for storing measure points until either saved or rejected

    # Mouseover variables
        # Eventgraph Mouseover variables
        self.mouseover_action = None # name of action to take if clicked at current mouseover: EPSP amp move, EPSP slope move/resize, volley amp move, volley slope move/resize
        self.mouseover_plot = None # plot of tentative EPSP slope
        self.mouseover_blob = None # scatterplot indicating mouseover of dragable point; move point or resize slope
        self.x_margin = None # for mouseover detection boundaries
        self.y_margin = None # for mouseover detection boundaries
        self.x_on_click = None # x-value closest to mousebutton down
        self.x_drag_last = None # last x-value within the same dragging event; prevents needless update when holding drag still
        self.x_drag = None # x-value of current dragging
        self.dragging = False # True if dragging; allows right-click to cancel drag
        self.mouseover_out = None # output of dragged aspect

        # Eventgraph Mouseover coordinates, for plotting. Set on row selection.
        self.EPSP_amp_xy = None # x,y
        self.EPSP_slope_start_xy = None # x,y
        self.EPSP_slope_end_xy = None # x,y
        self.volley_amp_xy = None # x,y
        self.volley_slope_start_xy = None # x,y
        self.volley_slope_end_xy = None # x,y

        # Eventgraph Mouseover clickzones: coordinates including margins. Set on row selection.
        self.EPSP_amp_move_zone = {} # dict: key=x,y, value=start,end. 
        self.EPSP_slope_move_zone = {} # dict: key=x,y, value=start,end.
        self.EPSP_slope_resize_zone = {} # dict: key=x,y, value=start,end.
        self.volley_amp_move_zone = {} # dict: key=x,y, value=start,end. 
        self.volley_slope_move_zone = {} # dict: key=x,y, value=start,end.
        self.volley_slope_resize_zone = {} # dict: key=x,y, value=start,end.

        # OutputGraph Mouseover variables
        self.last_out_x_idx = None
        self.ghost_sweep = None
        self.ghost_label = None

    def setMargins(self, axe, pixels=10): # set margins for mouseover detection
        self.x_margin = axe.transData.inverted().transform((pixels, 0))[0] - axe.transData.inverted().transform((0, 0))[0]
        self.y_margin = axe.transData.inverted().transform((0, pixels))[1] - axe.transData.inverted().transform((0, 0))[1]

    def updateDragZones(self, aspect=None, x=None, y=None):
        #print(f"*** updateDragZones: {aspect} {x} {y}")
        if aspect is None:
            aspect = self.mouseover_action
            x = self.mouseover_plot[0].get_xdata()
            y = self.mouseover_plot[0].get_ydata()
        else:
            self.mouseover_action = aspect

        if self.mouseover_action.startswith("EPSP slope"):
            self.updateSlopeZone('EPSP', x, y)
        elif self.mouseover_action.startswith("volley slope"):
            self.updateSlopeZone('volley', x, y)

        if aspect is None:
            aspect = self.mouseover_action
            x, y = self.mouseover_blob.get_offsets()[0].tolist()
        else:
            self.mouseover_action = aspect

        if aspect == "EPSP amp move":
            self.updateAmpZone('EPSP', x, y)
        elif aspect == "volley amp move":
            self.updateAmpZone('volley', x, y)

    def updatePointDragZone(self, aspect=None, x=None, y=None):
        #print(f"*** updatePointDragZone: {aspect} {x} {y}")
        if aspect is None:
            aspect = self.mouseoverAction
            x, y = self.mouseover_blob.get_offsets()[0].tolist()
        else:
            self.mouseoverAction = aspect

        if aspect == "EPSP amp move":
            self.updateAmpZone('EPSP', x, y)
        elif aspect == "volley amp move":
            self.updateAmpZone('volley', x, y)

    def updateSlopeZone(self, type, x, y):
        #print(f"*** - updateSlopeZone: {type} {x} {y}")
        slope_start = x[0], y[0]
        slope_end = x[-1], y[-1]
        x_window = min(x), max(x)
        y_window = min(y), max(y)

        setattr(self, f'{type}_slope_start_xy', slope_start)
        setattr(self, f'{type}_slope_end_xy', slope_end)
        getattr(self, f'{type}_slope_move_zone')['x'] = x_window[0]-self.x_margin, x_window[-1]+self.x_margin
        getattr(self, f'{type}_slope_move_zone')['y'] = y_window[0]-self.y_margin, y_window[-1]+self.y_margin
        getattr(self, f'{type}_slope_resize_zone')['x'] = x[-1]-self.x_margin, x[-1]+self.x_margin
        getattr(self, f'{type}_slope_resize_zone')['y'] = y[-1]-self.y_margin, y[-1]+self.y_margin

    def updateAmpZone(self, type, x, y):
        #print(f"*** - updateAmpZone: {type} {x} {y}")
        amp_xy = x, y
        amp_move_zone = x-self.x_margin, x+self.x_margin, y-self.y_margin, y+self.y_margin

        setattr(self, f'{type}_amp_xy', amp_xy)
        getattr(self, f'{type}_amp_move_zone')['x'] = amp_move_zone[0], amp_move_zone[1]
        getattr(self, f'{type}_amp_move_zone')['y'] = amp_move_zone[2], amp_move_zone[3]

    def get_recSet(self): # returns a set of all rec IDs that are currently plotted
        return set([value['rec_ID'] for value in self.dict_rec_labels.values()])

    def get_groupSet(self): # returns a set of all group IDs that are currently plotted
        return set([value['group_ID'] for value in self.dict_group_labels.values()])

    def get_state(self):
        try:
            return {
                'version': self.version,
                'colors': self.colors,
                'splitter': self.splitter,
                'viewTools': self.viewTools,
                'checkBox': self.checkBox,
                'lineEdit': self.lineEdit,
                'settings': self.settings,
                'zoom': self.zoom,
                'default_dict_t': self.default_dict_t,
            }
        except KeyError:
            self.reset()
    
    def set_state(self, state):
        self.version = state.get('version')
        self.colors = state.get('colors')
        self.splitter = state.get('splitter')
        self.viewTools = state.get('viewTools')
        self.checkBox = state.get('checkBox')
        self.lineEdit = state.get('lineEdit')
        self.settings = state.get('settings')
        self.zoom = state.get('zoom')
        self.default_dict_t = state.get('default_dict_t')

    def load_cfg(self, projectfolder, bw_version, force_reset=False): # load state from project config file
        path_pkl = projectfolder / "cfg.pkl"
        if path_pkl.exists() and not force_reset:
            with open(path_pkl, 'rb') as f:
                data = pickle.load(f)
            if data is not None:
                self.set_state(data)
            #check if version is compatible
            if bw_version != self.version:
                print(f"Warning: project_cfg.yaml is from {self.version} - current version is {bw_version}")
                cfg_v = self.version.split('.')
                bw_v = bw_version.split('.')
                if cfg_v[0] != bw_v[0]:
                    print("Major version mismatch: Project may not load correctly")
                elif cfg_v[1] != bw_v[1]:
                    print("Minor version mismatch: Some settings may not load correctly")
                elif cfg_v[2] != bw_v[2]:
                    print("Patch version mismatch: Minor changes may not load correctly")
        else:
            self.reset()
            self.save_cfg(projectfolder, bw_version)

    def save_cfg(self, projectfolder, bw_version=None): # save state to project config file
        path_pkl = projectfolder / "cfg.pkl"
        data = self.get_state()
        if bw_version is not None:
            data['version'] = bw_version
        if not path_pkl.parent.exists():
            path_pkl.parent.mkdir(parents=True, exist_ok=True)
        with open(path_pkl, 'wb') as f:
            pickle.dump(data, f)

    def ampView(self):
        show = self.checkBox
        return (show['EPSP_amp'])
    
    def slopeView(self):
        show = self.checkBox
        return (show['EPSP_slope'])
    
    def slopeOnly(self):
        show = self.checkBox
        return (show['EPSP_slope'] and not show['EPSP_amp'])
  
    def anyView(self):
        show = self.checkBox
        return any(show.values())
    


if __name__ == "__main__":
    # test instantiation
    uistate = UIstate()
    assert uistate.anyView() == True
    uistate.checkBox['EPSP_slope'] = False
    assert uistate.anyView() == False
    print("test passed")
