### SLATED FOR DELETION AFTER TRIALS COMPLETED

# ----------------------------------------------------------------------------------------
# RunTrialsSCS.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2018-11-05
# Last Edit: 2020-06-25
# Creator(s):  Kirsten R. Hazler

# Summary:
# Functions for running different variations of Stream Conservation Site delineation.
# ----------------------------------------------------------------------------------------

# Import modules
import CreateConSites
from CreateConSites import *


# Use the main function below to run functions directly from Python IDE or command line with hard-coded variables
def main():
   ### Set up basic input variables
   in_hydroNet = r"F:\Working\SCU\VA_HydroNet.gdb\HydroNet\HydroNet_ND"
   in_Catch = r"E:\SpatialData\NHD_Plus_HR\Proc_NHDPlus_HR.gdb\NHDPlusCatchment_Merge_valam"
   in_PF = r"F:\Working\EssentialConSites\ECS_Inputs_December2019.gdb\ProcFeats_20191213_scu"
   in_FlowBuff = r"F:\CurrentData\ConSite_Tools_Inputs.gdb\FlowBuff250_albers"
   out_GDB = r"F:\Working\SCS\TestOutputs_20200625.gdb"

   ### Set up trial variables
   # Trial 1
   upDist1 = 2000
   downDist1 = 1000
   buffDist1 = 250
   trial_1 = ["Trial_1", upDist1, downDist1, buffDist1]
   
   # Trial 2
   upDist2 = 2000
   downDist2 = 500
   buffDist2 = 250
   trial_2 = ["Trial_2", upDist2, downDist2, buffDist2]
   
   # Trial 3
   upDist3 = 3000
   downDist3 = 1000
   buffDist3 = 250
   trial_3 = ["Trial_3", upDist3, downDist3, buffDist3]
   
   # Trial 4
   upDist4 = 3000
   downDist4 = 500
   buffDist4 = 250
   trial_4 = ["Trial_4", upDist4, downDist4, buffDist4]
   
   ### End of user input

   ### Function(s) to run
   
   createFGDB(out_GDB)
   
   # Create points on network - these are used for all trials
   printMsg("Starting MakeNetworkPts_scs function.")
   tStart = datetime.now()
   scsPts = out_GDB + os.sep + "scsPts"
   MakeNetworkPts_scs(in_hydroNet, in_Catch, in_PF, scsPts)
   tEnd = datetime.now()
   ds = GetElapsedTime (tStart, tEnd)
   printMsg("Time elapsed: %s" % ds)
   
   for t in [trial_1, trial_2, trial_3, trial_4]:
      # timestamp
      tStart = datetime.now()
      
      printMsg("Working on %s" %t[0])
      
      nameTag = t[0]
      upDist = t[1]
      downDist = t[2]
      buffDist = t[3]

      scsLines = out_GDB + os.sep + "scsLines_%s" %nameTag
      scsFinal = out_GDB + os.sep + "scsFinal_%s" %nameTag
      
      printMsg("Starting MakeServiceLayers_scs function.")
      (lyrDownTrace, lyrUpTrace) = MakeServiceLayers_scs(in_hydroNet, upDist, downDist)
      
      printMsg("Starting CreateLines_scs function.")
      CreateLines_scs(scsLines, in_PF, scsPts, lyrDownTrace, lyrUpTrace)
      
      printMsg("Starting DelinSite_scs function.")
      DelinSite_scs(scsLines, in_Catch, in_hydroNet, scsFinal, in_FlowBuff, "true", buffDist)

      printMsg("Finished with %s." %t[0])
      
      # timestamp
      tEnd = datetime.now()
      ds = GetElapsedTime (tStart, tEnd)
      printMsg("Time elapsed: %s" % ds)
   
if __name__ == "__main__":
   main()
