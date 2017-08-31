# ----------------------------------------------------------------------------------------
# libScuFx.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2017-08-29
# Last Edit: 2017-08-31
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
def delinFlowDistBuff(in_Feats, fld_ID, in_FlowDir, out_Feats, maxDist, out_Scratch = 'in_memory'):
   """Delineates buffers based on flow distance down to features (rather than straight distance)"""
   # Get cell size and output spatial reference from in_FlowDir
   cellSize = (arcpy.GetRasterProperties_management(in_FlowDir, "CELLSIZEX")).getOutput(0)
   srRast = arcpy.Describe(in_FlowDir).spatialReference
   linUnit = srRast.linearUnitName
   printMsg('Cell size of flow direction raster is %s %ss' %(cellSize, linUnit))
   printMsg('Flow modeling is strongly dependent on cell size.')

   # Set environment setting and other variables
   arcpy.env.snapRaster = in_FlowDir
   procDist = 2*maxDist

   # Check if input features and input flow direction have same spatial reference.
   # If so, just make a copy. If not, reproject features to match raster.
   srFeats = arcpy.Describe(in_Feats).spatialReference
   if srFeats.Name == srRast.Name:
      printMsg('Coordinate systems for features and raster are the same. Copying...')
      arcpy.CopyFeatures_management (in_Feats, out_Feats)
   else:
      printMsg('Reprojecting features to match raster...')
      # Check if geographic transformation is needed, and handle accordingly.
      if srFeats.GCS.Name == srRast.GCS.Name:
         geoTrans = ""
         printMsg('No geographic transformation needed...')
      else:
         transList = arcpy.ListTransformations(srFeats,srRast)
         geoTrans = transList[0]
      arcpy.Project_management (in_Feats, out_Feats, srRast, geoTrans)

   # Create an empty list to store IDs of features that fail to get processed
   myFailList = []

   # Set up processing cursor and loop
   flags = [] # Initialize empty list to keep track of suspects
   cursor = arcpy.da.UpdateCursor(out_Feats, [fld_ID, "SHAPE@"])
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
         arcpy.Select_analysis (out_Feats, tmpFeat, selQry)

         # Convert feature to raster
         printMsg('Converting feature to raster...')
         srcRast = out_Scratch + os.sep + 'srcRast'
         arcpy.PolygonToRaster_conversion (tmpFeat, fld_ID, srcRast, "MAXIMUM_COMBINED_AREA", fld_ID, cellSize)
         
         # Clip flow direction raster to processing buffer
         procBuff = out_Scratch + os.sep + 'procBuff'
         printMsg('Buffering feature to set maximum processing distance')
         arcpy.Buffer_analysis (tmpFeat, procBuff, procDist, "", "", "ALL", "")
         myExtent = str(arcpy.Describe(procBuff).extent).replace(" NaN", "")
         printMsg('Extent: %s' %myExtent)
         clp_FlowDir = out_Scratch + os.sep + 'clp_FlowDir'
         printMsg('Clipping flow direction raster to processing buffer')
         arcpy.Clip_management (in_FlowDir, myExtent, clp_FlowDir, procBuff, "", "ClippingGeometry")
         arcpy.env.extent = clp_FlowDir

         # Burn SCU feature into flow direction raster as sink
         printMsg('Creating sink from feature...')
         snk_FlowDir = Con(IsNull(srcRast),clp_FlowDir)
         snk_FlowDir.save(out_Scratch + os.sep + 'snk_FlowDir')
         
         # Calculate flow distance down to sink
         printMsg('Calculating flow distance to feature...')
         FlowDist = FlowLength (snk_FlowDir, "DOWNSTREAM")
         FlowDist.save(out_Scratch + os.sep + 'FlowDist')
         
         # Clip flow distance raster to the maximum distance buffer
         clipBuff = out_Scratch + os.sep + 'clipBuff'
         arcpy.Buffer_analysis (tmpFeat, clipBuff, maxDist, "", "", "ALL", "")
         myExtent = str(arcpy.Describe(clipBuff).extent).replace(" NaN", "")
         printMsg('Extent: %s' %myExtent)
         clp_FlowDist = out_Scratch + os.sep + 'clp_FlowDist'
         printMsg('Clipping flow distance raster to maximum distance buffer')
         arcpy.Clip_management (FlowDist, myExtent, clp_FlowDist, clipBuff, "", "ClippingGeometry")
         arcpy.env.extent = clp_FlowDist
         
         # Make a binary raster based on flow distance
         printMsg('Creating binary raster from flow distance...')
         binRast = Con((IsNull(clp_FlowDist) == 1),
                  (Con((IsNull(srcRast)== 0),1,0)),
                  (Con((Raster(clp_FlowDist) <= maxDist),1,0)))
         binRast.save(out_Scratch + os.sep + 'binRast')
         printMsg('Boundary cleaning...')
         cleanRast = BoundaryClean (binRast, 'NO_SORT', 'TWO_WAY')
         cleanRast.save(out_Scratch + os.sep + 'cleanRast')
         printMsg('Setting zeros to nulls...')
         prePoly = SetNull (cleanRast, 1, 'Value = 0')
         prePoly.save(out_Scratch + os.sep + 'prePoly')

         # Convert raster to polygon
         printMsg('Converting flow distance raster to polygon...')
         finPoly = out_Scratch + os.sep + 'finPoly'
         arcpy.RasterToPolygon_conversion (prePoly, finPoly, "NO_SIMPLIFY")

         # # Eliminate parts because some features will make you cry/scream if you don't
         # printMsg('Eliminating trivial parts of catchment polygon...')
         # elimCatch = out_Scratch + os.sep + 'elimCatch'
         # arcpy.EliminatePolygonPart_management (clipCatch, elimCatch, "PERCENT", "", 10, "ANY")

         # Shrinkwrap to assure final shape is a nice smooth feature with no holes
         printMsg('Smoothing shape...')
         dist = float(cellSize)
         dilDist = "%s %ss" % (str(dist), linUnit)
         shrinkPoly = out_Scratch + os.sep + 'shrinkPoly'
         ShrinkWrap(finPoly, dilDist, shrinkPoly, out_Scratch)
         
         # Check the number of features at this point. 
         # It should be just one. If more, the output is likely bad and should be flagged.
         count = countFeatures(shrinkPoly)
         if count > 1:
            printWrng('Output is suspect for feature %s' % str(myID))
            flags.append(myID)
         
         # Use the flow distance buffer geometry as the final shape
         myFinalShape = arcpy.SearchCursor(shrinkPoly).next().Shape

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
   return out_Feats

def prioritizeSCUs(in_Feats, fld_ID, fld_BRANK, lo_BRANK, in_Integrity, lo_Integrity, in_ConsPriority, in_Vulnerability, out_Feats, out_Scratch = 'in_memory'):
   '''Prioritizes Stream Conservation Units (SCUs) for conservation, based on biodiversity rank (BRANK), watershed integrity and conservation priority (from ConservationVision Watershed Model), and vulnerability (from ConservationVision Development Vulnerability Model)'''
   # Step 1: First cut: Create subset of buffered SCUs ranked lo_BRANK or better
   selQry = "%s <= '%s'" % (fld_BRANK, lo_BRANK)
   arcpy.Select_analysis (in_Feats, out_Feats, selQry)
   
   # Step 2: For each buffered SCU in subset, get zonal stats for Watershed Integrity, Conservation Priority and Vulnerability. Do this in loop in case of buffer overlap.
      
   # Process: Add fields to hold the stats
   for f in ['INTEG', 'CPRIOR', 'VULN']:
      arcpy.AddField_management (out_Feats, f, 'FLOAT')
      
   # Set up some variables used in loop
   tmpFeat = out_Scratch + os.sep + 'tmpFeat' # temp feature class 
   tmpTab = out_Scratch + os.sep + 'tmpTab' # temp table 
   flags = [] # empty list to keep track of suspects
   
   # Set up processing cursor and loop
   cursor = arcpy.da.UpdateCursor(out_Feats, [fld_ID, 'INTEG', 'CPRIOR', 'VULN'])
   for row in cursor:
      try:
         myID = row[0]
         
         # Make temporary feature class
         selQry = "%s <= %s" % (fld_ID, str(myID))
         arcpy.Select_analysis (out_Feats, tmpFeat, selQry)
         
         # Run zonal stats, extract values, and update fields
         outTab = ZonalStatisticsAsTable (tmpFeat, fld_ID, in_Integrity, tmpTab, 'DATA', 'MEAN')
         val = arcpy.SearchCursor(tmpTab).next().MEAN
         row[1] = val
         
         outTab = ZonalStatisticsAsTable (tmpFeat, fld_ID, in_ConsPriority, tmpTab, 'DATA', 'MEAN')
         val = arcpy.SearchCursor(tmpTab).next().MEAN
         row[2] = val
         
         outTab = ZonalStatisticsAsTable (tmpFeat, fld_ID, in_Vulnerability, tmpTab, 'DATA', 'MEAN')
         val = arcpy.SearchCursor(tmpTab).next().MEAN
         row[3] = val
         
         cursor.updateRow(row)
         
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

   # Step 3: Score catchments based on BRANK, Watershed Integrity, Conservation Priority, and Vulnerability, then rank
   codeblock = '''def score(brank, integ, crprior, vuln):
      if brank'''

# Use the main function below to run the flow distance buffer function directly from Python IDE with hard-coded variables
def main():
   in_Feats = r'C:\Users\xch43889\Documents\Working\SCU_prioritization\SCUs20170724.shp\dk_1500912213976.shp'
   fld_ID = 'lngID'
   in_FlowDir = r'H:\Backups\DCR_Work_DellD\GIS_Data_VA_proc\Finalized\NHDPlus_Virginia.gdb\fdir_VA'
   out_Feats = r'C:\Users\xch43889\Documents\Working\SCU_prioritization\SCU_work.gdb\scuFlowBuffs500'
   maxDist = 250
   out_Scratch = r'C:\Users\xch43889\Documents\Working\SCU_prioritization\scratch-20170831.gdb'
   # End of user input

   delinFlowDistBuff(in_Feats, fld_ID, in_FlowDir, out_Feats, maxDist, out_Scratch)

if __name__ == '__main__':
   main()
