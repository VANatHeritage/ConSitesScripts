# ----------------------------------------------------------------------------------------
# ShrinkWrap.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016-02-24 (Adapted from a ModelBuilder model)
# Last Edit: 2017-07-07
# Creator:  Kirsten R. Hazler

# Summary:
# Coalesces features into a "shrink-wrapped" shape, depending on proximity. 

# Dependencies:
#     Coalesce_consiteTools 

# Syntax:
# ShrinkWrap_consiteTools(inFeats, DilDist, outFeats, [scratchGDB])
# ----------------------------------------------------------------------------------------

# Import modules
import arcpy, os, sys, traceback
from time import time as t

# Get time stamp
ts = int(t())

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
inFeats = arcpy.GetParameterAsText(0) # Input features to be shrink-wrapped
DilDist = arcpy.GetParameter(1) # Dilation distance, a positive number
   # This is the buffer distance used to make nearby features coalesce
   # To create proto-ConSites from SBBs, 250-m is recommended.  Features with under 500-m between them will coalesce.
outFeats = arcpy.GetParameterAsText(2) # Output shrink-wrapped features
scratchGDB = arcpy.GetParameterAsText(3) # Workspace for temporary data

# Create new file geodatabase to store temporary products too risky to store in memory
gdbPath = arcpy.env.scratchFolder
gdbName = 'tmp_%s.gdb' %ts
tmpWorkspace = gdbPath + os.sep + gdbName 
arcpy.CreateFileGDB_management(gdbPath, gdbName)

# Parameter check
if DilDist <= 0:
   arcpy.AddError("You need to enter a positive, non-zero value for the dilation distance")
   raise arcpy.ExecuteError   

if not scratchGDB:
   scratchGDB = "in_memory"
   # Use "in_memory" as default, but if script is failing, use scratchGDB on disk.
   
if scratchGDB != "in_memory":
   arcpy.AddMessage("Scratch outputs will be stored here: %s" % scratchGDB)
   scratchParm = scratchGDB
else:
   arcpy.AddMessage("Scratch products are being stored in memory and will not persist. If processing fails inexplicably, or if you want to be able to inspect scratch products, try running this with a specified scratchGDB on disk.")
   scratchParm = ""

arcpy.AddMessage("Additional critical temporary products will be stored here: %s" % tmpWorkspace)

arcpy.AddMessage("Script running under %s" % sys.version)
   
# Set overwrite option so that existing data may be overwritten
arcpy.env.overwriteOutput = True 

# Declare path/name of output data and workspace
drive, path = os.path.splitdrive(outFeats) 
path, filename = os.path.split(path)
myWorkspace = drive + path
Output_fname = filename

# Process:  Create Feature Class (to store output)
arcpy.AddMessage("Creating feature class to store output features...")
arcpy.CreateFeatureclass_management (myWorkspace, Output_fname, "POLYGON", "", "", "", inFeats) 

# Process:  Clean Features
arcpy.AddMessage("Cleaning input features...")
cleanFeats = tmpWorkspace + os.sep + "cleanFeats"
arcpy.CleanFeatures_consiteTools(inFeats, cleanFeats)

# Process:  Dissolve Features
arcpy.AddMessage("Dissolving adjacent features...")
dissFeats = tmpWorkspace + os.sep + "dissFeats"
# Writing to disk in hopes of stopping geoprocessing failure
arcpy.AddMessage("This feature class is stored here: %s" % dissFeats)
arcpy.Dissolve_management (cleanFeats, dissFeats, "", "", "SINGLE_PART", "")

# Process:  Generalize Features
# This should prevent random processing failures on features with many vertices, and also speed processing in general
arcpy.AddMessage("Simplifying features...")
arcpy.Generalize_edit(dissFeats, "0.1 Meters")

# Process:  Buffer Features
arcpy.AddMessage("Buffering features...")
buffFeats = tmpWorkspace + os.sep + "buffFeats"
arcpy.Buffer_analysis (dissFeats, buffFeats, DilDist, "", "", "ALL")

# Process:  Explode Multiparts
arcpy.AddMessage("Exploding multipart features...")
explFeats = tmpWorkspace + os.sep + "explFeats"
# Writing to disk in hopes of stopping geoprocessing failure
arcpy.AddMessage("This feature class is stored here: %s" % explFeats)
arcpy.MultipartToSinglepart_management (buffFeats, explFeats)

# Process:  Get Count
numWraps = (arcpy.GetCount_management(explFeats)).getOutput(0)
arcpy.AddMessage('There are %s features after consolidation' %numWraps)

# Loop through the exploded buffer features
myFeats = arcpy.da.SearchCursor(explFeats, ["SHAPE@"])
counter = 1
for Feat in myFeats:
   arcpy.AddMessage('Working on feature %s' % str(counter))
   featSHP = Feat[0]
   tmpFeat = scratchGDB + os.sep + "tmpFeat"
   arcpy.CopyFeatures_management (featSHP, tmpFeat)
   
   # Process:  Repair Geometry
   arcpy.RepairGeometry_management (tmpFeat, "DELETE_NULL")
   
   # Process:  Make Feature Layer
   arcpy.MakeFeatureLayer_management (dissFeats, "dissFeatsLyr", "", "", "")

   # Process: Select Layer by Location (Get dissolved features within each exploded buffer feature)
   arcpy.SelectLayerByLocation_management ("dissFeatsLyr", "INTERSECT", tmpFeat, "", "NEW_SELECTION")
   
   # Process:  Coalesce features (expand)
   coalFeats = scratchGDB + os.sep + 'coalFeats'
   arcpy.Coalesce_consiteTools("dissFeatsLyr", 8*DilDist, coalFeats, scratchParm)
   # Increasing the dilation distance improves smoothing and reduces the "dumbbell" effect.
   
   # Process:  Union coalesced features (to remove gaps)
   # This is only necessary b/c we are now applying this tool to the Cores layer, which has gaps
   unionFeats = scratchGDB + os.sep + "unionFeats"
   arcpy.Union_analysis ([coalFeats], unionFeats, "ONLY_FID", "", "NO_GAPS") 
   
   # Process:  Dissolve again 
   dissunionFeats = scratchGDB + os.sep + "dissunionFeats"
   arcpy.Dissolve_management (unionFeats, dissunionFeats, "", "", "SINGLE_PART", "")
   
   # Process:  Append the final geometry to the ShrinkWrap feature class
   arcpy.AddMessage("Appending feature...")
   arcpy.Append_management(dissunionFeats, outFeats, "NO_TEST", "", "")
   
   counter +=1
   
del tmpWorkspace