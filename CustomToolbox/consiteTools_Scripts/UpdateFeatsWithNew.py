# ----------------------------------------------------------------------------------------
# UpdateFeatsWithNew.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016-03-01 (Adapted from a ModelBuilder model)
# Last Edit: 2016-03-01
# Creator:  Kirsten R. Hazler
#
# Summary: 
# Updates existing feature class with newly created features.
#
# Syntax: 
# UpdateFeatsWithNew_consiteTools(inCurrentFeats, inNewFeats) 
# ----------------------------------------------------------------------------------------

# Import arcpy module
import arcpy, os

# Script arguments
inCurrentFeats = arcpy.GetParameterAsText(0)
inNewFeats = arcpy.GetParameterAsText(1)

# Additional variables:
scratchGDB = arcpy.env.scratchGDB 

# Process: If applicable, clear any selections on set of new features
typeCF = (arcpy.Describe(inCurrentFeats)).dataType
if typeCF == 'FeatureLayer':
   arcpy.SelectLayerByAttribute_management (inCurrentFeats, "CLEAR_SELECTION")

# Process:  Make Feature Layer
arcpy.MakeFeatureLayer_management(inCurrentFeats, "CF_lyr") 

# Process: Select Layer By Location
arcpy.SelectLayerByLocation_management("CF_lyr", "INTERSECT", inNewFeats, "", "NEW_SELECTION", "NOT_INVERT")

# Process:
bakFeats = scratchGDB + os.sep + 'BackupFeatures'
arcpy.AddMessage("Overwritten/deleted features will be stored here: %s" % bakFeats)
arcpy.CopyFeatures_management ("CF_lyr", bakFeats) 

# Process: Delete Features
arcpy.DeleteFeatures_management("CF_lyr")

# Process: Append
arcpy.Append_management(inNewFeats, inCurrentFeats, "NO_TEST", "", "")


