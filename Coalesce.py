# ----------------------------------------------------------------------------------------
# Coalesce.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016-02-24 (Adapted from a ModelBuilder model)
# Last Edit: 2016-12-20
# Creator:  Kirsten R. Hazler

# Summary:
# If a positive number is entered for the dilation distance, features are expanded outward 
# by the specified distance, then shrunk back in by the same distance. This causes nearby 
# features to coalesce.
#
# If a negative number is entered for the dilation distance, features are first shrunk, 
# then expanded.  This eliminates narrow portions of existing features, thereby 
# simplifying them.  It can also break narrow "bridges" between features that were 
# formerly coalesced.

# Dependencies:
#     CleanFeatures_consiteTools

# Syntax:  
# Coalesce_consiteTools(inFeats, PosDist, outFeats, [scratchGDB])
# ----------------------------------------------------------------------------------------

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
inFeats = arcpy.GetParameterAsText(0) # Input features to be processed
PosDist = arcpy.GetParameter(1) # Dilation distance
outFeats = arcpy.GetParameter(2) # Output features
scratchGDB = arcpy.GetParameterAsText(3) # Workspace for temporary data

if not scratchGDB:
   scratchGDB = "in_memory"
   # Use "in_memory" as default, but if script is failing, use scratchGDB on disk.
   
if scratchGDB != "in_memory":
   arcpy.AddMessage("Scratch outputs will be stored here: %s" % scratchGDB)
else:
   arcpy.AddMessage("Scratch products are being stored in memory and will not persist. If processing fails inexplicably, or if you want to be able to inspect scratch products, try running this with a specified scratchGDB on disk.")

# Additional variables:
NegDist = -PosDist

# Set overwrite option so that existing data may be overwritten
arcpy.env.overwriteOutput = True 

# Process: Buffer (Positive)
PosBuff = scratchGDB + os.sep + "PosBuff"
arcpy.Buffer_analysis(inFeats, PosBuff, PosDist, "FULL", "ROUND", "ALL", "", "PLANAR")

# Process: Clean Features
Clean_PosBuff = scratchGDB + os.sep + "CleanPosBuff"
arcpy.CleanFeatures_consiteTools(PosBuff, Clean_PosBuff)

# Process:  Generalize Features
# This should prevent random processing failures on features with many vertices, and also speed processing in general
arcpy.Generalize_edit(Clean_PosBuff, "0.1 Meters")

# Process: Buffer (Negative)
NegBuff = scratchGDB + os.sep + "NegativeBuffer"
arcpy.Buffer_analysis(Clean_PosBuff, NegBuff, NegDist, "FULL", "ROUND", "NONE", "", "PLANAR")

# Process: Clean Features to get final dilated features
arcpy.CleanFeatures_consiteTools(NegBuff, outFeats)

# Clear memory
if scratchGDB == "in_memory":
   del scratchGDB




