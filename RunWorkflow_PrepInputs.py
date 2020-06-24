# ----------------------------------------------------------------------------------------
# PrepInputs.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2020-06-22
# Last Edit: 2020-06-22
# Creator:  Kirsten R. Hazler

# Summary:
# Suite of functions for preparing data needed for site delineation and/or prioritization
# ----------------------------------------------------------------------------------------

# Import function libraries and settings
import CreateConSites
from CreateConSites import *

# Use the main function below to run functions directly from Python IDE or command line with hard-coded variables.

def main():
   ### User-provided variables
   in_FlowDist = r"E:\SpatialData\flowlengover_HU8_VA.gdb\flowlengover_HU8_VA"
   truncDist = 250
   out_FlowBuff = r"F:\CurrentData\ConSite_Tools_Inputs.gdb\FlowBuff250"
   snapRast = r"H:\Backups\GIS_Data_VA\SnapRasters\Snap_VaLam30.tif\Snap_VaLam30.tif"
   
   ### Function(s) to run
   prepFlowBuff(in_FlowDist, truncDist, out_FlowBuff, snapRast)
   
if __name__ == "__main__":
   main()
