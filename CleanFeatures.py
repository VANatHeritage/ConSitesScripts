# ---------------------------------------------------------------------------
# CleanFeatures.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016-11-21 (Adapted from a ModelBuilder model)
# Last Edit: 2016-11-22
# Creator:  Kirsten R. Hazler

# Summary: 
# Repairs geometry, then explodes multipart polygons to prepare features for geoprocessing.

# Syntax: 
# CleanFeatures_consiteTools(inFeats, outFeats) 
# ---------------------------------------------------------------------------

# Import modules
import arcpy, os, sys, traceback

# Script arguments input by user:
inFeats = arcpy.GetParameterAsText(0)
outFeats = arcpy.GetParameterAsText(1)

# Set overwrite option so that existing data may be overwritten
arcpy.env.overwriteOutput = True 

# Process: Repair Geometry
arcpy.RepairGeometry_management(inFeats, "DELETE_NULL")

# Have to add the while/try/except below b/c polygon explosion sometimes fails inexplicably.
# This gives it 10 tries to overcome the problem with repeated geometry repairs, then gives up.
counter = 1
while counter <= 10:
   try:
      # Process: Multipart To Singlepart
      arcpy.MultipartToSinglepart_management(inFeats, outFeats)
      
      counter = 11
      
   except:
      arcpy.AddMessage("Polygon explosion failed.")
      # Process: Repair Geometry
      arcpy.AddMessage("Trying to repair geometry (try # %s)" %str(counter))
      arcpy.RepairGeometry_management(inFeats, "DELETE_NULL")
      
      counter +=1
      
      if counter == 11:
         arcpy.AddMessage("Polygon explosion problem could not be resolved.  Copying features.")
         arcpy.CopyFeatures_management (inFeats, outFeats)