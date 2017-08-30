# ----------------------------------------------------------------------------------------
# scu-FX.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2017-08-29
# Last Edit: 2017-08-30
# Creator(s):  Kirsten R. Hazler

# Summary:
# A library of functions for prioritizing Stream Conservation Units (SCUs) for conservation.

# Usage Tips:
# 

# Dependencies:
# 

# Syntax:  
# 
# ----------------------------------------------------------------------------------------

# Import modules
import arcpy
from arcpy.sa import *
arcpy.CheckOutExtension("Spatial")
import libConSiteFx
from libConSiteFx import *
import os, sys, datetime, traceback

# Set overwrite option so that existing data may be overwritten
arcpy.env.overwriteOutput = True

# Define functions used to create toolbox tools
def delineatePolyCatchments(in_Feats, fld_ID, in_FlowDir, out_Catch, maxDist = '500 METERS', out_Scratch = 'in_memory'):
   """Delineates catchments individually for each polygon in feature class or layer, out to a maximum distance"""
   # Get cell size and output spatial reference from in_FlowDir
   cellSize = (arcpy.GetRasterProperties_management(in_FlowDir, "CELLSIZEX")).getOutput(0)
   srRast = arcpy.Describe(in_FlowDir).spatialReference
   linUnit = srRast.linearUnitName
   printMsg('Cell size of flow direction raster is %s %ss' %(cellSize, linUnit))
   printMsg('Catchment delineation is strongly dependent on cell size.')

   # Set environment setting and other variables
   arcpy.env.snapRaster = in_FlowDir
   dist, units, procDist = multiMeasure(maxDist, 3)

   # Check if input features and input flow direction have same spatial reference.
   # If so, just make a copy. If not, reproject features to match raster.
   srFeats = arcpy.Describe(in_Feats).spatialReference
   if srFeats.Name == srRast.Name:
      printMsg('Coordinate systems for features and raster are the same. Copying...')
      arcpy.CopyFeatures_management (in_Feats, out_Catch)
   else:
      printMsg('Reprojecting features to match raster...')
      # Check if geographic transformation is needed, and handle accordingly.
      if srFeats.GCS.Name == srRast.GCS.Name:
         geoTrans = ""
         printMsg('No geographic transformation needed...')
      else:
         transList = arcpy.ListTransformations(srFeats,srRast)
         geoTrans = transList[0]
      arcpy.Project_management (in_Feats, out_Catch, srRast, geoTrans)

   # Create an empty list to store IDs of features that fail to get processed
   myFailList = []

   # Set up processing cursor and loop
   flags = [] # Initialize empty list to keep track of suspects
   cursor = arcpy.da.UpdateCursor(out_Catch, [fld_ID, "SHAPE@"])
   for row in cursor:
      try:
         # Extract the unique ID and geometry object
         myID = row[0]
         myShape = row[1]

         printMsg('Working on feature %s' %str(myID))

         # Process:  Select (Analysis)
         # Create a temporary feature class including only the current feature
         selQry = "%s = %s" % (fld_ID, str(myID))
         tmpFeat = out_Scratch + os.sep + 'tmpFeat'
         arcpy.Select_analysis (out_Catch, tmpFeat, selQry)

         # Convert feature to raster
         printMsg('Converting feature to raster...')
         srcRast = out_Scratch + os.sep + 'srcRast'
         arcpy.PolygonToRaster_conversion (tmpFeat, fld_ID, srcRast, "MAXIMUM_COMBINED_AREA", fld_ID, cellSize)

         # Restrict processing area to avoid ridiculous processing time
         procBuff = out_Scratch + os.sep + 'procBuff'
         printMsg('Buffering feature to set maximum processing distance')
         arcpy.Buffer_analysis (tmpFeat, procBuff, procDist, "", "", "ALL", "")
         myExtent = str(arcpy.Describe(procBuff).extent).replace(" NaN", "")
         printMsg('Extent: %s' %myExtent)
         clp_FlowDir = out_Scratch + os.sep + 'clp_FlowDir'
         printMsg('Clipping flow direction raster to processing buffer')
         arcpy.Clip_management (in_FlowDir, myExtent, clp_FlowDir, procBuff, "", "ClippingGeometry")
         arcpy.env.extent = clp_FlowDir

         # Create catchment
         # NOTE: May want to replace this procedure with an implementation of flow distance 
         printMsg('Delineating catchment...')
         catchRast = Watershed (clp_FlowDir, srcRast)
         catchRast.save(out_Scratch + os.sep + 'catchRast')

         # Convert catchment to polygon
         printMsg('Converting catchment to polygon...')
         catchPoly = out_Scratch + os.sep + 'catchPoly'
         arcpy.RasterToPolygon_conversion (catchRast, catchPoly, "NO_SIMPLIFY")

         # Clip the catchment to the maximum distance buffer
         clipBuff = out_Scratch + os.sep + 'clipBuff'
         printMsg('Clipping catchment to maximum distance...')
         arcpy.Buffer_analysis (tmpFeat, clipBuff, maxDist, "", "", "ALL", "")
         clipCatch = out_Scratch + os.sep + 'clipCatch'
         arcpy.Clip_analysis (catchPoly, clipBuff, clipCatch)
         
         # Eliminate parts because some features will make you cry/scream if you don't
         printMsg('Eliminating trivial parts of catchment polygon...')
         elimCatch = out_Scratch + os.sep + 'elimCatch'
         arcpy.EliminatePolygonPart_management (clipCatch, elimCatch, "PERCENT", "", 10, "ANY")

         # Coalesce to assure final catchment is a nice smooth feature
         printMsg('Smoothing catchment...')
         dist = float(cellSize)
         dilDist = "%s %ss" % (str(dist), linUnit)
         coalCatch = out_Scratch + os.sep + 'coalCatch'
         Coalesce(elimCatch, dilDist, coalCatch, out_Scratch)
         
         # Check the number of features at this point. 
         # It should be just one. If more, the output is likely bad and should be flagged.
         count = countFeatures(coalCatch)
         if count > 1:
            printWrng('Output is suspect for feature %s' % str(myID))
            flags.append(myID)
         
         # Use the catchment geometry as the final shape
         myFinalShape = arcpy.SearchCursor(elimCatch).next().Shape

         # Update the feature with its final shape
         row[1] = myFinalShape
         cursor.updateRow(row)

         printMsg('Finished processing feature %s' %str(myID))
         
         # Reset extent, because Arc is stupid.
         arcpy.env.extent = "MAXOF"

      except:
         # Add failure message and append failed feature ID to list
         printMsg("\nFailed to fully process feature " + str(myID))
         myFailList.append(myID)

         # Error handling code swiped from "A Python Primer for ArcGIS"
         tb = sys.exc_info()[2]
         tbinfo = traceback.format_tb(tb)[0]
         pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
         msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

         printWrng(msgs)
         printWrng(pymsg)
         printMsg(arcpy.GetMessages(1))

         # Add status message
         printMsg("\nMoving on to the next feature.  Note that the output will be incomplete.")
   
   if len(flags) > 0:
      printWrng('These features may be incorrect: %s' % str(flags))
   return out_Catch

def prioritizeSCUs(in_SCU, in_Catch, fld_ID, fld_BRANK, lo_BRANK, in_Integrity, in_ConsPriority, in_Vulnerability, out_SCU, out_Scratch = 'in_memory'):
   '''Prioritizes Stream Conservation Units (SCUs) for conservation, based on biodiversity rank (BRANK), watershed integrity and conservation priority (from ConservationVision Watershed Model), and vulnerability (from ConservationVision Development Vulnerability Model)'''
   # Step 1: First cut based on BRANK: Create subset of SCUs ranked lo_BRANK or better
   selQry = "%s <= '%s'" % (fld_BRANK, lo_BRANK)
   arcpy.Select_analysis (in_SCU, out_SCU, selQry)
   
   # Step 2: For each SCU catchment corresponding to SCUs in subset, get zonal stats of Watershed Integrity, Conservation Priority and Vulnerability. Do this in loop in case of catchment overlap.
   # Process: Add fields (WtrshdInteg, ConsPrior, and Vuln)
   
   # Set up cursor for loop
   #for s in SCUs:
      # Process: Select (catchment)
      # Process: Zonal statistics by table (Watershed Integrity)
      # Get mean value and update ConsPrior field
      # Process: Zonal statistics by table (Conservation Priority)
      # Get mean value and update ConsPrior field
      # Process: Zonal statistics by table (Vulnerability)
      # Get mean value and update Vuln field

   # Step 3: Score catchments based on BRANK, Watershed Integrity, Conservation Priority, and Vulnerability, then rank

# Use the main function below to run the catchment function directly from Python IDE with hard-coded variables
def main():
   in_Feats = r'C:\Users\xch43889\Documents\Working\SCU_prioritization\SCUs20170724.shp\dk_1500912213976.shp'
   fld_ID = 'lngID'
   in_FlowDir = r'H:\Backups\DCR_Work_DellD\GIS_Data_VA_proc\Finalized\NHDPlus_Virginia.gdb\fdir_VA'
   out_Catch = r'C:\Users\xch43889\Documents\Working\SCU_prioritization\SCU_work.gdb\scuCatch'
   maxDist = '1000 METERS'
   out_Scratch = 'in_memory'
   # End of user input

   delineatePolyCatchments(in_Feats, fld_ID, in_FlowDir, out_Catch, maxDist, out_Scratch)

if __name__ == '__main__':
   main()