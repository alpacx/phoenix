"""Layout-1 reservation coordinates from Pulse W3006 issue 2137 pages 6–7, in mm."""
from math import ceil
# u=0 is the left edge of the dimensioned 11.60 mm ground opening; v=0 is the PCB edge.
# The radiating body sits over lands centered at u=1.65 (floating) and 10.75 (feed).
GROUND=((0,0),(12.10,0),(12.10,3.85),(11.60,3.85),(11.60,6.25),(0,6.25))
LAND_CENTERS={'1':(10.75,2.0),'2':(1.65,2.0)}
# Undimensioned transition on the adjacent/non-RF-layer drawing. The source is embedded raster,
# registered on the seven ground-via centers and the PCB edge. These points follow its boundary.
# Use a 0.12 mm outward margin in the keepout, clipped at the PCB edge.
SIGNAL=((-1.47,0),(13.30,0),(13.30,.61),(15.25,1.67),(16.14,2.25),(16.57,2.75),
        (16.32,4.05),(15.76,5.64),(14.92,7.04),(13.98,8.02),(13.29,8.66),
        (13.29,5.72),(12.67,5.40),(12.67,7.40),(-1.47,7.40))
# Nominal RF-face pour boundary includes the microstrip approach. The signal-layer
# envelope conservatively excludes unrelated face copper from that approach.
MARGIN=.12
LOW=-1.59
HIGH=16.70
def xy_nm(side,off,mir,u,vv,bounds):
    left,top,right,bottom=bounds
    # With v pointing into the PCB, handedness alternates by edge. For each selected
    # physical face the transform includes a reflection only when its artwork is mirrored.
    flip=mir ^ (side in ('top','right'))
    along=(HIGH-u if flip else u-LOW)+off
    x,y={'bottom':(left+along,bottom-vv),'top':(left+along,top+vv),'left':(left+vv,top+along),'right':(right-vv,top+along)}[side]
    return (round(x*1e6),round(y*1e6))
def document():
    return dict(source='https://productfinder.pulseeng.com/doc_type/WEB301/doc_num/W3006/doc_part/W3006.pdf',issue=2137,pages=[6,7],units='mm',ground_polygon=GROUND,signal_polygon=SIGNAL,signal_readout_guard_mm=MARGIN,land_centers=LAND_CENTERS,mechanical_fit_width_mm=HIGH-LOW)
