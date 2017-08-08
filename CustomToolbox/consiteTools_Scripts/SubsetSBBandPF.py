# ----------------------------------------------------------------------------------------
# SubsetSBBandPF.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016-02-25 (Adapted from ModelBuilder models)
# Last Edit: 2016-03-08
# Creator:  Kirsten R. Hazler
#
# Summary: 
# Given selected input Site Building Blocks (SBB) features, selects the corresponding 
# Procedural Features (PF). Or vice versa.  Outputs the selected SBBs and PFs to new 
# feature classes.
#
# Syntax:  
# SubsetSBBandPF_consiteTools(inSBB, inPF, selOption, joinFld, outSBB, outPF)
# ----------------------------------------------------------------------------------------

# Import modules
import arcpy, os, sys, traceback

# Script arguments
inSBB = arcpy.GetParameterAsText(0) 
   # Input layer representing Site Building Blocks (SBB)
inPF = arcpy.GetParameterAsText(1)
   # Input feature class representing Procedural Features (PF)
selOption = arcpy.GetParameterAsText(2)
   # Selection options:
   # "PF" :  Select PFs based on SBBs (default)
   # "SBB" : Select SBBs based on PFs
joinFld = arcpy.GetParameterAsText(3)
   # The source feature ID field used to join SBBs and PFs
outSBB = arcpy.GetParameterAsText(4)
   # Output feature class storing the SBB subset
outPF = arcpy.GetParameterAsText(5)
   # Output feature class storing the PF subset

if selOption == "PF":
   inSelector = inSBB
   inSelectee = inPF
   outSelector = outSBB
   outSelectee = outPF
elif selOption == "SBB":
   inSelector = inPF
   inSelectee = inSBB
   outSelector = outPF
   outSelectee = outSBB
else:
   arcpy.AddError('Invalid selection option')
  
# Process: If applicable, clear any selections on the Selectee input
typeSelectee = (arcpy.Describe(inSelectee)).dataType
if typeSelectee == 'FeatureLayer':
   arcpy.SelectLayerByAttribute_management (inSelectee, "CLEAR_SELECTION")
   
# Process:  Copy the selected Selector features to the output feature class
arcpy.CopyFeatures_management (inSelector, outSelector) 

# Process: Make Feature Layer from Selectee features
arcpy.MakeFeatureLayer_management(inSelectee, "Selectee_lyr") 

# Add join to get the Selectees associated with the Selectors, keeping only common records
arcpy.AddJoin_management ("Selectee_lyr", joinFld, outSelector, joinFld, "KEEP_COMMON")

# Select all Selectees that were joined
arcpy.SelectLayerByAttribute_management ("Selectee_lyr", "NEW_SELECTION")

# Remove the join
arcpy.RemoveJoin_management ("Selectee_lyr")

# Process:  Copy the selected Selectee features to the output feature class
arcpy.CopyFeatures_management ("Selectee_lyr", outSelectee)




