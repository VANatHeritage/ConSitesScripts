# ----------------------------------------------------------------------------------------
# ExpandSBBselection.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016-02-24 (Adapted from ModelBuilder models)
# Last Edit: 2016-02-25
# Creator:  Kirsten R. Hazler
#
# Summary: 
# Given an initial selection of Site Building Blocks (SBB) features, selects additional 
# SBB features in the vicinity that should be included in any Conservation Site update. 
# Also selects the Procedural Features (PF) corresponding to selected SBBs. Outputs the 
# selected SBBs and PFs to new feature classes.
#
# Syntax: ExpandSBBselection_consiteTools(inSBB, inPF, SFID, inConSites, SearchDist, outSBB, outPF)
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

# Script arguments
inSBB = arcpy.GetParameterAsText(0) 
   # Input layer representing Site Building Blocks (SBB)
   # (with desired features selected in ArcMap)
inPF = arcpy.GetParameterAsText(1)
   # Input feature class representing Procedural Features (PF)
SFID = arcpy.GetParameterAsText(2)
   # The source feature ID field used to join SBBs and PFs
inConSites = arcpy.GetParameterAsText(3) 
   # Input feature class current Conservation Sites
SearchDist = arcpy.GetParameterAsText(4)
   # Maximum distance used to select additional SBBs
   # in the vicinity of the current SBB selection
outSBB = arcpy.GetParameterAsText(5)
   # Output feature class storing the SBB subset
outPF = arcpy.GetParameterAsText(6)
   # Output feature class storing the PF subset

# Process: If applicable, clear any selections on the PFs and ConSites inputs
typePF = (arcpy.Describe(inPF)).dataType
typeCS = (arcpy.Describe(inConSites)).dataType
if typePF == 'FeatureLayer':
   arcpy.SelectLayerByAttribute_management (inPF, "CLEAR_SELECTION")
if typeCS == 'FeatureLayer':
   arcpy.SelectLayerByAttribute_management (inConSites, "CLEAR_SELECTION")
   
# Process: Make Feature Layers from PFs and ConSites
arcpy.MakeFeatureLayer_management(inPF, "PF_lyr")   
arcpy.MakeFeatureLayer_management(inConSites, "Sites_lyr")
   
# Process: Select subset of terrestrial ConSites
# WhereClause = "TYPE = 'Conservation Site'" 
arcpy.SelectLayerByAttribute_management ("Sites_lyr", "NEW_SELECTION", '')

# Initialize row count variables
initRowCnt = 0
finRowCnt = 1

while initRowCnt < finRowCnt:
# Keep adding to the SBB selection as long as the counts of selected records keep changing
   # Process:  Get Count of records in initial SBB selection
   initRowCnt = int(arcpy.GetCount_management(inSBB).getOutput(0))
   
   # Process: Select Layer By Location (SBBs within distance of current selection)
   arcpy.SelectLayerByLocation_management(inSBB, "WITHIN_A_DISTANCE", inSBB, SearchDist, "ADD_TO_SELECTION", "NOT_INVERT")
   
   # Process: Select Layer By Location (ConSites intersecting current SBB selection)
   arcpy.SelectLayerByLocation_management("Sites_lyr", "INTERSECT", inSBB, "", "NEW_SELECTION", "NOT_INVERT")
   
   # Process: Select Layer By Location (SBBs within current selection of ConSites)
   arcpy.SelectLayerByLocation_management(inSBB, "INTERSECT", "Sites_lyr", "", "ADD_TO_SELECTION", "NOT_INVERT")
   
   # Process: Select Layer By Location (Final selection)
   arcpy.SelectLayerByLocation_management(inSBB, "WITHIN_A_DISTANCE", inSBB, SearchDist, "ADD_TO_SELECTION", "NOT_INVERT")
   
   # Process: Get Count of records in final SBB selection
   finRowCnt = int(arcpy.GetCount_management(inSBB).getOutput(0))
   
# Process:  Save subset of SBBs and corresponding PFs to output feature classes
arcpy.SubsetSBBandPF_consiteTools(inSBB, inPF, "PF", SFID, outSBB, outPF)





