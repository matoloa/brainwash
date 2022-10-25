Method extraction
1) Create an average sweep from all sweeps (720 per sample file, but we'll need to handle variations in length)
2) Find Stim: the steepest incline in the average - this should be the stimulation artefact.
3) Find Base: the average of an arbitrary timeframe before the stimulation artefact.
3) Find Low: the lowest point after the artefact.
3+) This is not 100% reliable; under certain circumstances, the volley will reach lower than the EPSP. The Volley is, however, a much quicker event. Check for center of biggest area under curve?
4) Find VE: (volley-EPSP-bump). Tracing backwards from Low: find the least negative part on the way up to Base
5) Find EPSP-slope: the lowest absolute of second order derivative between VE and Low. Traditionally, our lab works with 8 point EPSPs. The angle of this is the EPSP-slope.
5+) The length of the measurement could be determined by extending the measurement in either direction as far as can be done without bending it.
6) Find Volley: the steepest coherent (typically 4 points) decline between Stim and VE. Traditionally, our lab works with 4 point volleys. The angle of this is the volley-slope.
6+) see 5+

There is a competing method of measurement: Amplitude.
EPSP-Amp would be Low-Base, assuming there is no spike. This is the main argument against EPSP-Amp; with spikes present, there is no obvious correct point of measurement for EPSP. You sometimes see amplitude measurements from the bottom of a spike in low-impact publications. This is frowned upon.
Volley-Amp is problematic - especially when the VE doesn't reach positive values. It is also extremely sensitive to noise.

Now, all of the above are coordinates for where to look, in each individual sweep. These coordinates are applied to all 720 sweeps, and the measurements - Amplitude or Slope, or any combination thereof (e.g. Slope-EPSP compensated by Volley-Amplitude), such that two arrays of 720 integers are created. These are to be displayed for overview.

The tetanization in the sample data is after sweep 180. To insure that the measurements have been correctly performed, and the kinetics have not changed during the experiments, it is customary to present sample sweeps compiled from 10 sweeps: the beginning (1-10), before tetanization (171-180), after it(181-190), and then finally at the end of the recording(711-720.