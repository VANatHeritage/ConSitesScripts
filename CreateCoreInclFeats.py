# ---------------------------------------------------------------------------
# CreateCoreInclFeats.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016-11-10 (Adapted from ModelBuilder models)
# Last Edit: 2016-11-11
# Creator:  Kirsten R. Hazler

# Summary:
# Given a set of Site Building Blocks and habitat Core features, creates a set of Cores Inclusion Features which are to be used as inputs in Conservation Site automation.  
#
# Notes:  
# (1) This tool must be run in the foreground, for some reason, or it eventually crashes.
# (2) Eventually, we will probably want to call this tool from the CreateConSites_ParamCntrl tool, rather than running it separately.
#
# Syntax:
# CreateCoreInclFeats_consiteTools(inSBB, inCores, outInclFeats)
#
# Notes:
# This script is a piece of shit.
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
inSBB = arcpy.GetParameterAsText(1) # Input Site Building Blocks
inCores = arcpy.GetParameterAsText(2) # Input Cores
outInclFeats = arcpy.GetParameterAsText(3) # Output Cores Inclusion Features

# Additional variables:
scratchGDB = arcpy.env.scratchGDB
BuffDist = "1000 Meters"
DilDist = 2000
ShrinkDist = 1000

# Set overwrite option so that existing data may be overwritten
arcpy.env.overwriteOutput = True 

# Status messages
arcpy.AddMessage("Scratch outputs will be stored here: %s" % scratchGDB)
arcpy.AddMessage("Buffer distance: %s" %BuffDist)
arcpy.AddMessage("Dilation distance: %s" %str(DilDist))
arcpy.AddMessage("Shrink distance: %s" %str(ShrinkDist))

# Declare path/name of output data and workspace
drive, path = os.path.splitdrive(outInclFeats) 
path, filename = os.path.split(path)
myWorkspace = drive + os.sep + path
out_fname = filename

# Process:  Create Feature Class (to store output)
arcpy.AddMessage("Creating feature class to store output features...")
arcpy.CreateFeatureclass_management (myWorkspace, out_fname, "POLYGON", inCores, "", "", inCores) 

# Make feature layers
arcpy.MakeFeatureLayer_management(inCores, "Cores_lyr") 
arcpy.MakeFeatureLayer_management(inSBB, "SBB_lyr") 

# Process: Select Layer By Location (Get cores intersecting PFs)
arcpy.SelectLayerByLocation_management("Cores_lyr", "INTERSECT", inPF, "", "NEW_SELECTION", "NOT_INVERT")

# Process:  Copy the selected cores to selCores
selCores = scratchGDB + os.sep + 'selCores'
arcpy.CopyFeatures_management ("Cores_lyr", selCores)
arcpy.AddMessage('Selected cores copied.')

myFailList = []

# Loop through the cores
myCores = arcpy.da.SearchCursor(selCores, ["CoreID"])
for myCore in myCores:
   try:
      id = myCore[0]
      arcpy.AddMessage('Working on core %s' % str(int(id)))
      
      # Process: Select (Analysis)
      # Create a temporary feature class including only the current core
      tmpCore = scratchGDB + os.sep + "tmpCore"
      WhereClause = '"CoreID" = ' + str(int(id))
      arcpy.Select_analysis (selCores, tmpCore, WhereClause)
      
      # Process: Repair Geometry
      arcpy.AddMessage("Repairing core geometry...")
      arcpy.RepairGeometry_management (tmpCore, "DELETE_NULL")
      
      # Process: Explode Multiparts
      tmpCore2 = scratchGDB + os.sep + "tmpCore2"
      arcpy.MultipartToSinglepart_management (tmpCore, tmpCore2)
      
      # Process: Select Layer By Location (Get SBBs intersecting core)
      arcpy.SelectLayerByLocation_management("SBB_lyr", "INTERSECT", tmpCore2, "", "NEW_SELECTION", "NOT_INVERT")

      # Process: Buffer
      arcpy.AddMessage("Buffering SBBs...")
      BuffSBB = scratchGDB + os.sep + "BuffSBB"
      arcpy.Buffer_analysis("SBB_lyr", BuffSBB, BuffDist, "FULL", "ROUND", "ALL", "", "PLANAR")
      
      # Process: Shrinkwrap
      arcpy.AddMessage("Shrinkwrapping buffers...")
      ShrinkBuff = scratchGDB + os.sep + "ShrinkBuff"
      arcpy.ShrinkWrap_consiteTools(BuffSBB, DilDist, ShrinkDist, ShrinkBuff)

      # Process: Clean Clip
      arcpy.AddMessage("Clipping core to shrinkwrapped buffer...")
      ClpCore = scratchGDB + os.sep + "ClpCore"
      arcpy.CleanClip_consiteTools(tmpCore2, ShrinkBuff, ClpCore)
      
      # Append the final geometry to the output feature class.
      arcpy.AddMessage("Appending output core feature...")
      arcpy.Append_management(ClpCore, outInclFeats, "NO_TEST", "", "")

   except:
      # Error handling code swiped from "A Python Primer for ArcGIS"
      tb = sys.exc_info()[2]
      tbinfo = traceback.format_tb(tb)[0]
      pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
      msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

      arcpy.AddWarning(msgs)
      arcpy.AddWarning(pymsg)
      arcpy.AddMessage(arcpy.GetMessages(1))
      
      myFailList.append(id)
      arcpy.AddWarning("Processing failed for the following cores: %s" %myFailList)






