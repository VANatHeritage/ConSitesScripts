# ---------------------------------------------------------------------------
# RunWorkflow_Delineate.py
# Version:  ArcGIS 10.3 / Python 2.7
# Creation Date: 2020-06-03
# Last Edit: 2020-06-22
# Creator:  Kirsten R. Hazler

# Summary:
# Workflow for all steps needed to delineate Conservation Sites using a script rather than the toolbox. This script is intended for statewide creation of Terrestrial Conservation Sites (TCS), Anthropogenic Habitat Zones (AHZ), and Stream Conservation Sites (SCS), but can also be used for subsets as desired. The user must update the script with user-specific file paths and options. 

# Data sources that are stored as online feature services must be downloaded to your local drive.
# Biotics data need to be extracted from within ArcMap, while on the COV network, using the ConSite Toolbox.
# ---------------------------------------------------------------------------

# Import function libraries and settings
import CreateConSites
from CreateConSites import *

# Use the main function below to run functions directly from Python IDE or command line with hard-coded variables.

def main():
   ### User-provided variables
   
   # Define your output workspaces (geodatabases) and other options
   # The geodatabases may or may not already exist
   out_GDB = r"F:\Working\SCS\TestOutputs_20200623.gdb" # GDB to store all processing outputs
   scratchGDB = r"F:\Working\SCS\scratch_20200623.gdb" # GDB to store scratch products. To maximize speed, set to "in_memory". If trouble-shooting, replace "in_memory" with path to a scratch geodatabase on your hard drive.
   siteType = "SCS" # Determines which site type to run. Choices are: TCS, AHZ, SCS, or COMBO (for all site types)
   ysnQC = "N" # Determines whether or not to run QC process after site delineation Choices are Y or N
   
   # Biotics Data - grab fresh download each time
   in_ProcFeats = r"F:\Working\EssentialConSites\Biotics\biotics_extract.gdb\ProcFeats_20191213_125326" # Input Procedural Features
   in_ConSites = r"F:\Working\EssentialConSites\Biotics\biotics_extract.gdb\ConSites_20191213_125326" # Input current Conservation Sites; needed for template
   
   # Ancillary Data for TCS and AHZ sites - grab fresh download each time 
   in_Roads = r"F:\Working\ConSites\ModFeatures\Roads.gdb\RCL_surfaces_20171206" # Road surfaces
   in_Rail = r"F:\Working\ConSites\ModFeatures\Rail.gdb\Rail_surfaces_20180108" # Rail surfaces
   in_Hydro = r"F:\Working\ConSites\ModFeatures\Hydro.gdb\Hydro_noZ" # Hydrographic features
   in_Exclude = r"F:\Working\ConSites\ModFeatures\Exclusions.gdb\ExclFeats_20171208" # Exclusion features
   
   # Ancillary Data for TCS and AHZ sites - set it and forget it until you are notified of an update
   in_nwi5 = r"F:\CurrentData\ConSite_Tools_Inputs.gdb\VA_Wetlands_Rule5" # Rule 5 wetlands 
   in_nwi67 = r"F:\CurrentData\ConSite_Tools_Inputs.gdb\VA_Wetlands_Rule67" # Rule 6/7 wetlands
   in_nwi9 = r"F:\CurrentData\ConSite_Tools_Inputs.gdb\VA_Wetlands_Rule9" # Rule 9 wetlands 
   in_Cores = r"F:\CurrentData\ConSite_Tools_Inputs.gdb\VaNLACoresRanks123" # Cores used to expand SBBs
   
   # Ancillary Data for SCS sites - set it and forget it until you are notified of an update
   in_hydroNet = r"F:\Working\SCU\VA_HydroNet.gdb\HydroNet\HydroNet_ND"
   in_Catch = r"E:\SpatialData\NHD_Plus_HR\Proc_NHDPlus_HR.gdb\NHDPlusCatchment_Merge_valam"
   in_FlowBuff = r"F:\CurrentData\ConSite_Tools_Inputs.gdb\FlowBuff250"
   
   ### End of user input
   
   ### Standard and derived variables
   # Procedural Features and ConSites from Biotics, parsed by type, used as process inputs
   pfTCS = out_GDB + os.sep + 'pfTerrestrial'
   pfSCS  = out_GDB + os.sep + 'pfStream'
   pfAHZ = out_GDB + os.sep + 'pfAnthro'
   csTCS = out_GDB + os.sep + 'csTerrestrial'
   csSCS = out_GDB + os.sep + 'csStream'
   csAHZ = out_GDB + os.sep + 'csAnthro'
   
   # Other input variables
   fld_SFID = "SFID" # Source Feature ID field
   fld_Rule = "RULE" # Source Feature Rule field
   fld_Buff = "BUFFER" # Source Feature Buffer field
   fld_SiteID = "SITEID" # Conservation Site ID
   ysn_Expand =  "false" # Expand SBB selection?
   in_TranSurf = "%s;%s" %(in_Roads, in_Rail)
   cutVal = 5 # a cutoff percentage that will be used to flag features that represent significant boundary growth or reduction
   
   # Outputs
   sbb1 = out_GDB + os.sep + "sbb1" # Site Building Blocks
   sbb2 = out_GDB + os.sep + "sbb2" # Expanded Site Building Blocks
   scsPts = out_GDB + os.sep + "scsPts" # Points along hydro network, derived from PFs
   scsLines = out_GDB + os.sep + "scsLines" # Lines equivalent to SCUs
   scsCatch = out_GDB + os.sep + "scsCatch" # Catchments containing scsLines
   
   out_TCS = out_GDB + os.sep + "ConSites_tcs" # Terrestrial Conservation Sites
   out_AHZ = out_GDB + os.sep + "ConSites_ahz" # Anthropogenic Habitat Zones
   out_SCS = out_GDB + os.sep + "ConSites_scs" # Stream Conservation Sites
   out_TCSqc = out_GDB + os.sep + "qcConSites_tcs" # Terrestrial Conservation Sites with QC info
   out_AHZqc = out_GDB + os.sep + "qcConSites_ahz" # Anthropogenic Habitat Zones with QC info
   out_SCSqc = out_GDB + os.sep + "qcConSites_scs" # Stream Conservation Sites with QC info

   ### Functions to run
   # Create output workspaces if they don't already exist
   createFGDB(out_GDB)
   
   if scratchGDB == "":
      pass
   elif scratchGDB == "in_memory":
      pass
   else:
      createFGDB(scratchGDB)
   
   DelinSite_scs(scsLines, in_Catch, in_hydroNet, out_SCS, in_FlowBuff, "true", scratchGDB)

if __name__ == "__main__":
   main()
