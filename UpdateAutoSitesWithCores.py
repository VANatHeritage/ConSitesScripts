# ---------------------------------------------------------------------------
# UpdateAutoSitesWithCores.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016-11-18
# Last Edit: 2017-01-04
# Creator:  Kirsten R. Hazler

# Summary:
# Expands automated sites based on corresponding Procedural Features' presence in core habitats.
#
# Notes:  
# Eventually, once all procedures are finalized, this algorithm should probably be incorporated into the CreateConSites tool.
#
# Dependencies:
#     CleanClip_consiteTools
#     CleanErase_consiteTools
#     Coalesce_consiteTools
#     ShrinkWrap_consiteTools

# Usage:

# Syntax:  
# FinalizeConSites_consiteTools(inPF, inCS, inCores, inHydro, inExclude, outCS, scratchGDB)
# ---------------------------------------------------------------------------

# Import modules
import arcpy, os, sys, traceback

# Get path to toolbox, then import it
# Scenario 1:  script is in separate folder within folder holding toolbox
tbx1 = os.path.abspath(os.path.join(sys.argv[0],"../..", "consiteTools.tbx"))
# Scenario 2:  script is embedded in tool
tbx2 = os.path.abspath(os.path.join(sys.argv[0],"..", "consiteTools.tbx"))
if os.path.isfile(tbx1):
   arcpy.ImportToolbox(tbx1)
   arcpy.AddMessage("Toolbox location is %s" % tbx1)
elif os.path.isfile(tbx2):
   arcpy.ImportToolbox(tbx2)
   arcpy.AddMessage("Toolbox location is %s" % tbx2)
else:
   arcpy.AddError('Required toolbox not found.  Check script for errors.')

# Script arguments input by user:
inPF = arcpy.GetParameterAsText(0) # Input Procedural Features
inCS = arcpy.GetParameterAsText(1) # Input automated ConSites
inCores = arcpy.GetParameterAsText(2) # Input Cores
inROW = arcpy.GetParameterAsText(3) # Input road right-of-way features
inHydro = arcpy.GetParameterAsText(4) # Input open water features
inExclude = arcpy.GetParameterAsText(5) # Input delineated exclusion features
outCS = arcpy.GetParameterAsText(6) # Output updated ConSites
scratchGDB = arcpy.GetParameterAsText(7) # Workspace for temporary data

# Additional variables:
tmpWorkspace = arcpy.env.scratchGDB # Use for temp products too risky to store in memory
arcpy.AddMessage("Some scratch outputs will be stored here: %s" % tmpWorkspace)
BuffDist = "1000 Meters"
DilDist = 500
coalDist = 50 # Distance used to coalesce features.  Updated from 25 to 50 per Ludwig's request to coalesce features within 100m of each other
simpDist = 25 # Distance used to simplify features (remove insignificant parts)
tmpCS = tmpWorkspace + os.sep + 'tmpCS'
partArea = 10000 # 1 hectare
hydroQry = "Hydro = 1"
hydroPerCov = 25
hydroElimDist = 10
rowQry = "DCR_ROW_TYPE = 'IS' OR DCR_ROW_TYPE = 'PR'"
rowPerCov = 50
rowElimDist = 10

if not scratchGDB:
   scratchGDB = "in_memory"
   # Use "in_memory" as default, but if script is failing, use scratchGDB on disk.
   
if scratchGDB != "in_memory":
   arcpy.AddMessage("Most scratch outputs will be stored here: %s" % scratchGDB)
   scratchParm = scratchGDB
else:
   arcpy.AddMessage("Most scratch products are being stored in memory and will not persist. If processing fails inexplicably, or if you want to be able to inspect scratch products, try running this with a specified scratchGDB on disk.")
   scratchParm = ""

# Set overwrite option so that existing data may be overwritten
arcpy.env.overwriteOutput = True 

# Status messages
arcpy.AddMessage("Buffer distance: %s" %BuffDist)
arcpy.AddMessage("Dilation distance: %s" %str(DilDist))

# Declare path/name of output data and workspace
drive, path = os.path.splitdrive(outCS) 
path, filename = os.path.split(path)
myWorkspace = drive + path
out_fname = filename

# Define some sub-routines
def GetEraseFeats (inFeats, selQry, elimDist, outEraseFeats):
   # Creates exclusion features from input hydro or ROW features
   # Process: Make Feature Layer (subset of selected features)
   arcpy.MakeFeatureLayer_management(inFeats, "Selected_lyr", selQry)

   # Process: Dissolve
   DissEraseFeats = scratchGDB + os.sep + 'DissEraseFeats'
   arcpy.Dissolve_management("Selected_lyr", DissEraseFeats, "", "", "SINGLE_PART")

   # Process: Coalesce
   CoalEraseFeats = scratchGDB + os.sep + 'CoalEraseFeats'
   arcpy.Coalesce_consiteTools(DissEraseFeats, -(elimDist), CoalEraseFeats, scratchParm)

   # Process: Clean Features
   arcpy.CleanFeatures_consiteTools(CoalEraseFeats, outEraseFeats)

def CullEraseFeats (inEraseFeats, inBnd, inPF, SFID, PerCov, outEraseFeats):
   # Culls exclusion features containing a significant percentage of any 
   # Procedural Features' area
   
   # Process:  Add Field (Erase ID) and Calculate
   arcpy.AddField_management (inEraseFeats, "eFID", "LONG")
   arcpy.CalculateField_management (inEraseFeats, "eFID", "!OBJECTID!", "PYTHON")
   
   # Process: Tabulate Intersection
   # This tabulates the percentage of each PF that is contained within each erase feature
   TabIntersect = scratchGDB + os.sep + "TabInter"
   arcpy.TabulateIntersection_analysis(inPF, SFID, inEraseFeats, TabIntersect, "eFID", "", "", "HECTARES")
   
   # Process: Summary Statistics
   # This tabulates the maximum percentage of ANY PF within each erase feature
   TabMax = scratchGDB + os.sep + "TabMax"
   arcpy.Statistics_analysis(TabIntersect, TabMax, "PERCENTAGE MAX", "eFID")
   
   # Process: Join Field
   # This joins the max percentage value back to the original erase features
   arcpy.JoinField_management(inEraseFeats, "eFID", TabMax, "eFID", "MAX_PERCENTAGE")
   
   # Process: Select
   # Any erase features containing a large enough percentage of a PF are discarded
   WhereClause = "MAX_PERCENTAGE < %s OR MAX_PERCENTAGE IS null" % PerCov
   selEraseFeats = scratchGDB + os.sep + 'selEraseFeats'
   arcpy.Select_analysis(inEraseFeats, selEraseFeats, WhereClause)
   
   # Process:  Clean Erase (Use inPF to chop out areas of remaining exclusion features)
   arcpy.CleanErase_consiteTools (selEraseFeats, inPF, outEraseFeats, scratchParm) 
   
def CullFrags (inFrags, inPF, searchDist, outFrags):
   # Culls SBB or ConSite fragments farther than specified search distance from 
   # Procedural Features
   
   # Process: Near
   arcpy.Near_analysis(inFrags, inPF, searchDist, "NO_LOCATION", "NO_ANGLE", "PLANAR")

   # Process: Make Feature Layer
   WhereClause = '"NEAR_FID" <> -1'
   arcpy.MakeFeatureLayer_management(inFrags, "Frags_lyr", WhereClause)

   # Process: Clean Features
   arcpy.CleanFeatures_consiteTools("Frags_lyr", outFrags)

# Process:  Create Feature Class (to store outputs)
arcpy.AddMessage("Creating feature class to store output features...")
arcpy.CreateFeatureclass_management (myWorkspace, out_fname, "POLYGON", inCS, "", "", inCS) 
arcpy.CreateFeatureclass_management (tmpWorkspace, "tmpCS", "POLYGON", inCS, "", "", inCS) 

# Make feature layers
arcpy.MakeFeatureLayer_management(inCores, "Cores_lyr") 
arcpy.MakeFeatureLayer_management(inPF, "PF_lyr") 
arcpy.MakeFeatureLayer_management(inCS, "Sites_lyr") 

# Process: Select Layer By Location (Get Cores intersecting PFs)
arcpy.SelectLayerByLocation_management("Cores_lyr", "INTERSECT", "PF_lyr", "", "NEW_SELECTION", "NOT_INVERT")

# Process:  Copy the selected Cores features to scratch feature class
selCores = tmpWorkspace + os.sep + 'selCores'
arcpy.CopyFeatures_management ("Cores_lyr", selCores) 

# Process:  Repair Geometry
arcpy.RepairGeometry_management (selCores, "DELETE_NULL")

# Process:  Buffer (around the Cores)
arcpy.AddMessage('Buffering cores...')
tmpBuff = scratchGDB + os.sep + 'tmpBuff'
arcpy.Buffer_analysis (selCores, tmpBuff, 2*hydroElimDist , "", "", "", "")  

# Process:  Generalize Features
# This should prevent random processing failures on features with many vertices, and also speed processing in general
arcpy.AddMessage("Simplifying features...")
arcpy.Generalize_edit(tmpBuff, "0.1 Meters")

# Process:  Clip (exclusion features to buffer)
arcpy.AddMessage('Clipping ROW features to buffer...')
rowClp = scratchGDB + os.sep + 'rowClp'
arcpy.CleanClip_consiteTools (inROW, tmpBuff, rowClp, scratchParm)
arcpy.AddMessage('Clipping hydro features to buffer...')
hydroClp = scratchGDB + os.sep + 'hydroClp'
arcpy.CleanClip_consiteTools (inHydro, tmpBuff, hydroClp, scratchParm)
arcpy.AddMessage('Clipping Exclusion Features to buffer...')
efClp = scratchGDB + os.sep + 'efClp'
arcpy.CleanClip_consiteTools (inExclude, tmpBuff, efClp, scratchParm)

# Process:  Get ROW Erase Features
rowErase = scratchGDB + os.sep + 'rowErase'
GetEraseFeats (rowClp, rowQry, rowElimDist, rowErase)

# Process:  Cull Erase Features (from rowErase)
arcpy.AddMessage('Culling ROW erase features...')
rowRtn = scratchGDB + os.sep + 'rowRtn'
CullEraseFeats (rowErase, tmpBuff, inPF, 'SFID', rowPerCov, rowRtn)

# Process:  Get Hydro Erase Features
hydroErase = scratchGDB + os.sep + 'hydroErase'
GetEraseFeats (hydroClp, hydroQry, hydroElimDist, hydroErase)

# Process:  Cull Erase Features (from hydroErase)
arcpy.AddMessage('Culling hydro erase features...')
hydroRtn = scratchGDB + os.sep + 'hydroRtn'
CullEraseFeats (hydroErase, tmpBuff, inPF, 'SFID', hydroPerCov, hydroRtn)

# Process:  Merge (efClp, rowRtn, and hydroRtn)
arcpy.AddMessage('Merging erase features...')
tmpErase = scratchGDB + os.sep + 'tmpErase'
arcpy.Merge_management ([efClp, rowRtn, hydroRtn], tmpErase) 

# Process:  Clean Erase (Use tmpErase to chop out areas of cores)
arcpy.AddMessage('Erasing portions of cores...')
coreFrags = scratchGDB + os.sep + 'coreFrags'
arcpy.CleanErase_consiteTools (selCores, tmpErase, coreFrags, scratchParm) 

# Cull Fragments (remove any core fragments not intersecting a PF)
arcpy.AddMessage('Culling core fragments...')
coreRtn = scratchGDB + os.sep + 'coreRtn'
CullFrags(coreFrags, inPF, 0, coreRtn)
arcpy.MakeFeatureLayer_management(coreRtn, "coreRtn_lyr")

# # Process: Shrinkwrap
# arcpy.AddMessage("Shrinkwrapping to consolidate cores...")
# shrinkCores = tmpWorkspace + os.sep + "shrinkCores"
# arcpy.ShrinkWrap_consiteTools(coreRtn, coalDist, shrinkCores, scratchParm)
shrinkCores = coreRtn
# Process:  Get Count
numCores = (arcpy.GetCount_management(shrinkCores)).getOutput(0)
arcpy.AddMessage('There are %s cores after consolidation' %numCores)

myFailList = []

###For use after failure
#shrinkCores = r'D:\Users\Kirsten\Documents\ArcGIS\scratch.gdb\shrinkCoresEast_20161203'

# Loop through the Cores
myCores = arcpy.da.SearchCursor(shrinkCores, ["SHAPE@", "OBJECTID"])
counter = 1
for myCore in myCores:
   try:
      arcpy.AddMessage('Working on core %s' % str(counter))
      coreSHP = myCore[0]
      coreID = myCore[1]
      tmpCore = scratchGDB + os.sep + "tmpCore" + str(counter)
      arcpy.CopyFeatures_management (coreSHP, tmpCore) 
      
      # Process: Select Layer By Location (Get PFs intersecting core)
      arcpy.SelectLayerByLocation_management("PF_lyr", "INTERSECT", tmpCore, "", "NEW_SELECTION", "NOT_INVERT")
      
      # Process: Select Layer By Location (Get Sites intersecting selected PFs)
      arcpy.SelectLayerByLocation_management("Sites_lyr", "INTERSECT", "PF_lyr", "", "NEW_SELECTION", "NOT_INVERT")

      # Process: Buffer
      arcpy.AddMessage("Buffering sites...")
      SiteBuff = scratchGDB + os.sep + "SiteBuff" + str(counter)
      arcpy.Buffer_analysis("Sites_lyr", SiteBuff, BuffDist, "FULL", "ROUND", "ALL", "", "PLANAR")
      
      # Process:  Generalize Features
      # This should prevent random processing failures on features with many vertices, and also speed processing in general
      arcpy.AddMessage("Simplifying features...")
      arcpy.Generalize_edit(SiteBuff, "0.1 Meters")

      # Process:  Multipart to Singlepart
      SiteBuff_exp = scratchGDB + os.sep + "SiteBuff_exp" + str(counter)
      arcpy.MultipartToSinglepart_management (SiteBuff, SiteBuff_exp)
      
      # Process: Shrinkwrap
      arcpy.AddMessage("Shrinkwrapping buffers...")
      ShrinkBuff = scratchGDB + os.sep + "ShrinkBuff" + str(counter)
      arcpy.ShrinkWrap_consiteTools(SiteBuff_exp, DilDist, ShrinkBuff, scratchParm)

      # Process: Clean Clip
      arcpy.AddMessage("Clipping core to shrinkwrapped buffer...")
      ClpCore = scratchGDB + os.sep + "ClpCore" + str(counter)
      arcpy.CleanClip_consiteTools(tmpCore, ShrinkBuff, ClpCore, scratchParm)
      
      # Process:  Coalesce (remove insignificant parts)
      coalCore = scratchGDB + os.sep + 'coalCore' + str(counter)
      arcpy.Coalesce_consiteTools(ClpCore, -(simpDist), coalCore, scratchParm)
      
      # Make feature layer
      arcpy.MakeFeatureLayer_management(coalCore, "ClpCore_lyr")
      
      # Process: Select Layer By Location (Get Cores fragments intersecting selected PFs)
      arcpy.SelectLayerByLocation_management("ClpCore_lyr", "INTERSECT", "PF_lyr", "", "NEW_SELECTION", "NOT_INVERT")
      
      # Merge (sites plus core features)
      arcpy.AddMessage("Merging clipped core features with site boundaries...")
      SiteMerge = scratchGDB + os.sep + "SiteMerge" + str(counter)
      arcpy.Merge_management (["ClpCore_lyr","Sites_lyr"], SiteMerge)
      
      # Process: Shrinkwrap
      arcpy.AddMessage("Shrinkwrapping to finalize shape...")
      ShrinkBuff2 = scratchGDB + os.sep + "ShrinkBuff2" + str(counter)
      arcpy.ShrinkWrap_consiteTools(SiteMerge, coalDist, ShrinkBuff2, scratchParm)
      
      outShp = ShrinkBuff2
         
      # Append the final geometry to a temporary feature class.
      arcpy.AddMessage("Appending final site feature...")
      arcpy.Append_management(outShp, tmpCS, "NO_TEST", "", "")

   except:
      # Error handling code swiped from "A Python Primer for ArcGIS"
      tb = sys.exc_info()[2]
      tbinfo = traceback.format_tb(tb)[0]
      pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
      msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

      arcpy.AddWarning(msgs)
      arcpy.AddWarning(pymsg)
      arcpy.AddMessage(arcpy.GetMessages(1))
      
      myFailList.append(coreID)
      arcpy.AddWarning("Processing failed for the following core: %s" %coreID)
      
   finally:
      counter +=1
      
###For use after failure
#tmpCS = r'E:\Testing_20161202.gdb\tmpCS'
      
# Finalize features
# Merge (sites plus core features)
arcpy.AddMessage("Merging features...")
SiteMerge2 = tmpWorkspace + os.sep + "SiteMerge2"
arcpy.Merge_management ([tmpCS,inCS], SiteMerge2)
      
# # Process: Dissolve Features
# arcpy.AddMessage("Dissolving adjacent features...")
# dissFeats = scratchGDB + os.sep + "dissFeats"
# arcpy.Dissolve_management (SiteMerge2, dissFeats, "", "", "SINGLE_PART", "")  

# # Process:  Union (to remove gaps)
# arcpy.AddMessage("Unioning to remove gaps...")
# unionFeats = tmpWorkspace + os.sep + "unionFeats"
# arcpy.Union_analysis ([dissFeats], unionFeats, "ONLY_FID", "", "NO_GAPS") 

# # Process: Dissolve Features
# arcpy.AddMessage("Dissolving again...")
# dissFeats2 = scratchGDB + os.sep + "dissFeats2"
# arcpy.Dissolve_management (unionFeats, dissFeats2, "", "", "SINGLE_PART", "")
      
# Process: Shrinkwrap
arcpy.AddMessage("Shrinkwrapping to consolidate nearby sites...")
shrinkSites = tmpWorkspace + os.sep + "shrinkSites"
arcpy.ShrinkWrap_consiteTools(SiteMerge2, (0.5*coalDist), shrinkSites, scratchParm) 
# Reducing coalDist back to match original value (25) here, so that it's less likely to join across core gaps.     
      
# Process:  Clean Erase (final removal of exclusion features)
arcpy.AddMessage('Excising manually delineated exclusion features...')
eraseFeats = tmpWorkspace + os. sep + 'erasedFeats'
arcpy.CleanErase_consiteTools (shrinkSites, inExclude, eraseFeats, scratchParm) 

# Process:  Remove holes smaller than a threshold
arcpy.AddMessage('Removing holes smaller than 1 hectare...')
arcpy.EliminatePolygonPart_management (eraseFeats, outCS, "AREA", partArea, "", "CONTAINED_ONLY")

if len(myFailList) > 0:
   arcpy.AddMessage("Processing failed for the following cores: %s" %myFailList)
   
# Clear memory
   if scratchGDB == "in_memory":
      del scratchGDB