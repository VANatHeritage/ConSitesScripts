# ---------------------------------------------------------------------------
# CleanClip.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016-11-21 (Adapted from a ModelBuilder model)
# Last Edit: 2016-11-21
# Creator:  Kirsten R. Hazler

# Summary:
# Clips the Input Features with the Clip Features.  The resulting features are then subjected to geometry repair and exploded (eliminating multipart polygons).

# Syntax:
# CleanClip_consiteTools(inFeats, clipFeats, outFeats) 

# Dependencies:
#     CleanFeatures_consiteTools

# Syntax:
# CleanClip_consiteTools(inFeats, clipFeats, outFeats, [scratchGDB])
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
inFeats = arcpy.GetParameterAsText(0)
clipFeats = arcpy.GetParameterAsText(1)
outFeats = arcpy.GetParameterAsText(2)
scratchGDB = arcpy.GetParameterAsText(3) # Workspace for temporary data

if not scratchGDB:
   scratchGDB = "in_memory"
   # Use "in_memory" as default, but if script is failing, use scratchGDB on disk.
   
if scratchGDB != "in_memory":
   arcpy.AddMessage("Scratch outputs will be stored here: %s" % scratchGDB)
else:
   arcpy.AddMessage("Scratch products are being stored in memory and will not persist. If processing fails inexplicably, or if you want to be able to inspect scratch products, try running this with a specified scratchGDB on disk.")

# Set overwrite option so that existing data may be overwritten
arcpy.env.overwriteOutput = True 

# Process: Clip
tmpClip = scratchGDB + os.sep + "tmpClip"
arcpy.Clip_analysis(inFeats, clipFeats, tmpClip)

# Process: Clean Features
arcpy.CleanFeatures_consiteTools(tmpClip, outFeats)