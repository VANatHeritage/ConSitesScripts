### SLATED FOR DELETION AFTER TRIALS COMPLETED

# ----------------------------------------------------------------------------------------
# RunTrialsSCS.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2018-11-05
# Last Edit: 2020-09-25
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
   OvrlndFlowLength = r"E:\SpatialData\flowlengover_HU8_VA.gdb\flowlengover_HU8_VA"
   FlowBuff250 = r"F:\CurrentData\ConSite_Tools_Inputs.gdb\FlowBuff250_albers"
   FlowBuff100 = r"F:\CurrentData\ConSite_Tools_Inputs.gdb\FlowBuff100_albers"
   FlowBuff150 = r"F:\CurrentData\ConSite_Tools_Inputs.gdb\FlowBuff150_albers"
   ImpactQuantiles = r"E:\SpatialData\HealthyWatersWork\hwProducts_20200724.gdb\ImpactScore_baseQ10"
   scsPts = r"F:\Working\SCS\TestOutputs_20200625.gdb\scsPts"
   # out_GDB = r"F:\Working\SCS\TestOutputs_20200625.gdb" # Used for trials 1-4
   # out_GDB = r"F:\Working\SCS\TestOutputs_20200715.gdb" # Used for trials 3b, 4b
   out_GDB = r"F:\Working\SCS\TestOutputs_20200727.gdb" # Used for trials 3c, 4c
   InclusionZone = out_GDB + os.sep + "scsInclusionZone"

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
   
   # Trial 3b
   dict3b = dict()
   dict3b["nameTag"] = "Trial_3b"
   dict3b["upDist"] = 3000
   dict3b["downDist"] = 1000
   dict3b["buffDist"] = 100
   dict3b["scsLines"] = r"F:\Working\SCS\TestOutputs_20200625.gdb\scsLines_Trial_3" 
   dict3b["flowBuff"] = FlowBuff100
   
   # Trial 4b
   dict4b = dict()
   dict4b["nameTag"] = "Trial_4b"
   dict4b["upDist"] = 3000
   dict4b["downDist"] = 500
   dict4b["buffDist"] = 100
   dict4b["scsLines"] = r"F:\Working\SCS\TestOutputs_20200625.gdb\scsLines_Trial_4"
   dict4b["flowBuff"] = FlowBuff100
   
   # Trial 3c
   dict3c = dict()
   dict3c["nameTag"] = "Trial_3c"
   dict3c["upDist"] = 3000
   dict3c["downDist"] = 1000
   dict3c["buffDist"] = 250
   dict3c["scsLines"] = r"F:\Working\SCS\TestOutputs_20200625.gdb\scsLines_Trial_3" 
   dict3c["flowBuff"] = InclusionZone
   
   # Trial 4c
   dict4c = dict()
   dict4c["nameTag"] = "Trial_4c"
   dict4c["upDist"] = 3000
   dict4c["downDist"] = 500
   dict4c["buffDist"] = 250
   dict4c["scsLines"] = r"F:\Working\SCS\TestOutputs_20200625.gdb\scsLines_Trial_4"
   dict4c["flowBuff"] = InclusionZone
   
   # Trial 4d
   dict4d = dict()
   dict4d["nameTag"] = "Trial_4d"
   dict4d["upDist"] = 3000
   dict4d["downDist"] = 500
   dict4d["buffDist"] = 150
   dict4d["scsLines"] = r"F:\Working\SCS\TestOutputs_20200625.gdb\scsLines_Trial_4"
   dict4d["flowBuff"] = FlowBuff150
   
   ### End of user input

   ### Function(s) to run
   
   createFGDB(out_GDB)
   prepFlowBuff(OvrlndFlowLength, 150, FlowBuff150)
   # prepInclusionZone(FlowBuff100, FlowBuff250, ImpactQuantiles, InclusionZone, truncVal = 9)
   
   # # Create points on network - these are used for all trials
   # printMsg("Starting MakeNetworkPts_scs function.")
   # tStart = datetime.now()
   # scsPts = out_GDB + os.sep + "scsPts"
   # MakeNetworkPts_scs(in_hydroNet, in_Catch, in_PF, scsPts)
   # tEnd = datetime.now()
   # ds = GetElapsedTime (tStart, tEnd)
   # printMsg("Time elapsed: %s" % ds)
   
   # # for t in [trial_1, trial_2, trial_3, trial_4]:
      # # timestamp
      # tStart = datetime.now()
      
      # printMsg("Working on %s" %t[0])
      
      # nameTag = t[0]
      # upDist = t[1]
      # downDist = t[2]
      # buffDist = t[3]

      # scsLines = out_GDB + os.sep + "scsLines_%s" %nameTag
      # scsFinal = out_GDB + os.sep + "scsFinal_%s" %nameTag
      
      # printMsg("Starting MakeServiceLayers_scs function.")
      # (lyrDownTrace, lyrUpTrace) = MakeServiceLayers_scs(in_hydroNet, upDist, downDist)
      
      # printMsg("Starting CreateLines_scs function.")
      # CreateLines_scs(scsLines, in_PF, scsPts, lyrDownTrace, lyrUpTrace)
      
      # printMsg("Starting DelinSite_scs function.")
      # DelinSite_scs(scsLines, in_Catch, in_hydroNet, scsFinal, in_FlowBuff, "true", buffDist)

      # printMsg("Finished with %s." %t[0])
      
      # # timestamp
      # tEnd = datetime.now()
      # ds = GetElapsedTime (tStart, tEnd)
      # printMsg("Time elapsed: %s" % ds)
      
   #for d in [dict3b, dict4b]:
   #for d in [dict3c, dict4c]:
   for d in [dict4d]:
      # timestamp
      tStart = datetime.now()
      
      printMsg("Working on %s" %d["nameTag"])
      
      nameTag = d["nameTag"]
      upDist = d["upDist"]
      downDist = d["downDist"]
      buffDist = d["buffDist"]
      scsLines = d["scsLines"]
      flowBuff = d["flowBuff"]
      scsFinal = out_GDB + os.sep + "scsFinal_%s" %nameTag
      
      printMsg("Starting DelinSite_scs function.")
      DelinSite_scs(scsLines, in_Catch, in_hydroNet, scsFinal, flowBuff, "true", buffDist, "in_memory")

      printMsg("Finished with %s." %nameTag)
      
      # timestamp
      tEnd = datetime.now()
      ds = GetElapsedTime (tStart, tEnd)
      printMsg("Time elapsed: %s" % ds)
   
if __name__ == "__main__":
   main()
