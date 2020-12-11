# ---------------------------------------------------------------------------
# RunWorkflow_Prioritize.py
# Version:  ArcGIS 10.3 / Python 2.7
# Creation Date: 2020-09-15
# Last Edit: 2020-12-11
# Creator:  Kirsten R. Hazler

# Summary:
# Workflow for all steps needed to prioritize Conservation Sites using a script rather than the ConSite Toolbox. This script is intended for prioritization of Terrestrial Conservation Sites (TCS), Stream Conservation Sites (SCS), and Karst Conservation Sites (KCS).  

# Usage:
# Prior to running this script, the following preliminary steps must be carried out:
# - Create a new working directory to contain the run inputs and outputs, named to include a date tag, i.e., "ECS_Run_[MonthYear]"
# - Within the new working directory, create a sub-directory to hold spreadsheets, i.e., "Spreadsheets_[MonthYear]"
# - Open the existing map document set up for the previous ECS run (i.e., ECS_Working_yyyymmdd.mxd), and save it as a new document with the correct date tags, within the new working directory.
# - Within the working directory, create an input geodatabase named ECS_Inputs_[MonthYear].gdb. 
# - Within the working directory, create an output geodatabase named ECS_Outputs_[MonthYear].gdb. 
# - Import required inputs into the INPUT geodatabase:
#   -- ElementExclusions table (get annually from biologists)
#   -- ConsLands feature class (get quarterly from Dave Boyd)
#   -- EcoRegions feature class (fairly static data; keep using the same until specified otherwise)
# - Run the "Extract Biotics data" tool, with output going to the INPUT geodatabase
# - Run the "Parse site types" tool, with output going to the INPUT geodatabase. 
# - Run the "Flatten Conservation Lands" tool, with output going to the INPUT geodatabase.
# - Remove any newly created layers in the map; retain only the pre-existing ones.
# - In the main function below, update the input variables by specifying the correct file paths and cutoff years as needed. (It is safest if you copy/paste full paths from the catalog window, to avoid typos that would crash the script.)
# - Close ArcMap and run this script from the Python environment. This takes approx. 45 minutes.
# - Once the script has finished running, open the map document again, and update the sources for all the layers. Save and close the map.
# - Zip the entire working directory, naming it ECS_Run_[MonthYear].zip, and save the zip file here: I:\DATA_MGT\Quarterly Updates. If there are more than 4 such files, delete the oldest one(s) so that only the most recent 4 remain.

# NOTE: You no longer need to be on COV network to be able to extract Biotics data.   
# ---------------------------------------------------------------------------

# Import function libraries and settings
import PrioritizeConSites
from PrioritizeConSites import *

# Use the main function below to run desired function(s) directly from Python IDE or command line with hard-coded variables
def main():
   ### Set up input variables ###
   # Paths to input and output geodatabases and directories - change these every time
   in_GDB = r'N:\EssentialConSites\ECS_Run_Dec2020\ECS_Inputs_Dec2020.gdb'
   out_GDB = r'N:\EssentialConSites\ECS_Run_Dec2020\ECS_Outputs_Dec2020.gdb'
   out_DIR = r'N:\EssentialConSites\ECS_Run_Dec2020\Spreadsheets_Dec2020' 
   
   # Input Procedural Features by site type
   # No need to change these as long as your in_GDB above is valid
   in_pf_tcs = in_GDB + os.sep + 'pfTerrestrial'
   in_pf_scu = in_GDB + os.sep + 'pfStream'
   in_pf_kcs = in_GDB + os.sep + 'pfKarst'
   
   # Input Conservation Sites by type
   # No need to change these as long as your in_GDB above is valid
   in_cs_tcs = in_GDB + os.sep + 'csTerrestrial'
   in_cs_scu = in_GDB + os.sep + 'csStream'
   in_cs_kcs = in_GDB + os.sep + 'csKarst'
   
   # Input other standard variables
   in_elExclude = in_GDB + os.sep + 'ElementExclusions'
   in_consLands = in_GDB + os.sep + 'conslands_lam'
   in_consLands_flat = in_GDB + os.sep + 'conslands_lam_flat'
   in_ecoReg = in_GDB + os.sep + 'tncEcoRegions_lam'
   fld_RegCode = 'GEN_REG'
   
   # Input cutoff years
   cutYear = 1995 # yyyy - 25 for TCS and SCU
   flagYear = 2000 # yyyy - 20 for TCS and SCU
   cutYear_kcs = 1980 # yyyy - 40 for KCS
   flagYear_kcs = 1985 # yyyy - 35 for KCS

   # Set up outputs by type - no need to change these as long as your out_GDB and out_DIR above are valid
   attribEOs_tcs = out_GDB + os.sep + 'attribEOs_tcs'
   sumTab_tcs = out_GDB + os.sep + 'sumTab_tcs'
   scoredEOs_tcs = out_GDB + os.sep + 'scoredEOs_tcs'
   priorEOs_tcs = out_GDB + os.sep + 'priorEOs_tcs'
   sumTab_upd_tcs = out_GDB + os.sep + 'sumTab_upd_tcs'
   priorConSites_tcs = out_GDB + os.sep + 'priorConSites_tcs'
   priorConSites_tcs_XLS = out_DIR + os.sep + 'priorConSites_tcs.xls'
   elementList_tcs = out_GDB + os.sep + 'elementList_tcs'
   elementList_tcs_XLS = out_DIR + os.sep + 'elementList_tcs.xls'
   qcList_tcs_EOs = out_DIR + os.sep + 'qcList_tcs_EOs.xls'
   qcList_tcs_sites  = out_DIR + os.sep + 'qcList_tcs_sites.xls'
   
   attribEOs_scu = out_GDB + os.sep + 'attribEOs_scu'
   sumTab_scu = out_GDB + os.sep + 'sumTab_scu'
   scoredEOs_scu = out_GDB + os.sep + 'scoredEOs_scu'
   priorEOs_scu = out_GDB + os.sep + 'priorEOs_scu'
   sumTab_upd_scu = out_GDB + os.sep + 'sumTab_upd_scu'
   priorConSites_scu = out_GDB + os.sep + 'priorConSites_scu'
   priorConSites_scu_XLS = out_DIR + os.sep + 'priorConSites_scu.xls'
   elementList_scu = out_GDB + os.sep + 'elementList_scu'
   elementList_scu_XLS = out_DIR + os.sep + 'elementList_scu.xls'   
   qcList_scu_EOs = out_DIR + os.sep + 'qcList_scu_EOs.xls'
   qcList_scu_sites  = out_DIR + os.sep + 'qcList_scu_sites.xls'
      
   attribEOs_kcs = out_GDB + os.sep + 'attribEOs_kcs'
   sumTab_kcs = out_GDB + os.sep + 'sumTab_kcs'
   scoredEOs_kcs = out_GDB + os.sep + 'scoredEOs_kcs'
   priorEOs_kcs = out_GDB + os.sep + 'priorEOs_kcs'
   sumTab_upd_kcs = out_GDB + os.sep + 'sumTab_upd_kcs'
   priorConSites_kcs = out_GDB + os.sep + 'priorConSites_kcs'
   priorConSites_kcs_XLS = out_DIR + os.sep + 'priorConSites_kcs.xls'
   elementList_kcs = out_GDB + os.sep + 'elementList_kcs'
   elementList_kcs_XLS = out_DIR + os.sep + 'elementList_kcs.xls'
   qcList_kcs_EOs = out_DIR + os.sep + 'qcList_kcs_EOs.xls'
   qcList_kcs_sites  = out_DIR + os.sep + 'qcList_kcs_sites.xls'
   
   
   ### Specify functions to run - no need to change these as long as all your input/output variables above are valid ###
   
   # Get timestamp
   tStart = datetime.now()
   printMsg("Processing started at %s on %s" %(tStart.strftime("%H:%M:%S"), tStart.strftime("%Y-%m-%d")))
   
   # # Attribute EOs
   # printMsg("Attributing terrestrial EOs...")
   # AttributeEOs(in_pf_tcs, in_elExclude, in_consLands, in_consLands_flat, in_ecoReg, fld_RegCode, cutYear, flagYear, attribEOs_tcs, sumTab_tcs)
   
   # printMsg("Attributing stream EOs...")
   # AttributeEOs(in_pf_scu, in_elExclude, in_consLands, in_consLands_flat, in_ecoReg, fld_RegCode, cutYear, flagYear, attribEOs_scu, sumTab_scu)
   
   # printMsg("Attributing karst EOs...")
   # AttributeEOs(in_pf_kcs, in_elExclude, in_consLands, in_consLands_flat, in_ecoReg, fld_RegCode, cutYear_kcs, flagYear_kcs, attribEOs_kcs, sumTab_kcs)
   
   # tNow = datetime.now()
   # printMsg("EO attribution ended at %s" %tNow.strftime("%H:%M:%S"))
   
   # # Score EOs
   # printMsg("Scoring terrestrial EOs...")
   # ScoreEOs(attribEOs_tcs, sumTab_tcs, scoredEOs_tcs, ysnMil = "false", ysnYear = "true")
   
   # printMsg("Scoring stream EOs...")
   # ScoreEOs(attribEOs_scu, sumTab_scu, scoredEOs_scu, ysnMil = "false", ysnYear = "true")
   
   # printMsg("Scoring karst EOs...")
   # ScoreEOs(attribEOs_kcs, sumTab_kcs, scoredEOs_kcs, ysnMil = "false", ysnYear = "true")
   
   # tNow = datetime.now()
   # printMsg("EO scoring ended at %s" %tNow.strftime("%H:%M:%S"))
   
   # # Build Portfolio
   # printMsg("Building terrestrial portfolio...")
   # BuildPortfolio(scoredEOs_tcs, priorEOs_tcs, sumTab_tcs, sumTab_upd_tcs, in_cs_tcs, priorConSites_tcs, priorConSites_tcs_XLS, in_consLands_flat, build = 'NEW')
   
   # printMsg("Building stream portfolio...")
   # BuildPortfolio(scoredEOs_scu, priorEOs_scu, sumTab_scu, sumTab_upd_scu, in_cs_scu, priorConSites_scu, priorConSites_scu_XLS, in_consLands_flat, build = 'NEW')
   
   printMsg("Building karst portfolio...")
   BuildPortfolio(scoredEOs_kcs, priorEOs_kcs, sumTab_kcs, sumTab_upd_kcs, in_cs_kcs, priorConSites_kcs, priorConSites_kcs_XLS, in_consLands_flat, build = 'NEW')
   
   # tNow = datetime.now()
   # printMsg("Portolio building ended at %s" %tNow.strftime("%H:%M:%S"))
   
   # # Build Elements List
   # printMsg("Building terrestrial elements list...")
   # BuildElementLists(in_cs_tcs, 'SITENAME', priorEOs_tcs, sumTab_upd_tcs, elementList_tcs, elementList_tcs_XLS)
   
   # printMsg("Building stream elements list...")
   # BuildElementLists(in_cs_scu, 'SITENAME', priorEOs_scu, sumTab_upd_scu, elementList_scu, elementList_scu_XLS)
   
   printMsg("Building karst elements list...")
   BuildElementLists(in_cs_kcs, 'SITENAME', priorEOs_kcs, sumTab_upd_kcs, elementList_kcs, elementList_kcs_XLS)
   
   # # QC
   # printMsg("QC'ing terrestrial sites and EOs")
   # qcSitesVsEOs(priorConSites_tcs, priorEOs_tcs, qcList_tcs_sites, qcList_tcs_EOs)
   
   # printMsg("QC'ing stream sites and EOs")
   # qcSitesVsEOs(priorConSites_scu, priorEOs_scu, qcList_scu_sites, qcList_scu_EOs)
   
   # printMsg("QC'ing karst sites and EOs")
   # qcSitesVsEOs(priorConSites_kcs, priorEOs_kcs, qcList_kcs_sites, qcList_kcs_EOs)
   
   # Get timestamp and elapsed time
   tEnd = datetime.now()
   printMsg("Processing ended at %s" %tEnd.strftime("%H:%M:%S"))
   deltaString = GetElapsedTime (tStart, tEnd)
   printMsg("Mission complete. Elapsed time: %s" %deltaString)
   
if __name__ == '__main__':
   main()