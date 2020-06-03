### SLATED FOR DELETION - Not needed b/c we have Biotics query layers for this.
# -------------------------------------------------------------------------------------------------------
# CreateProcFeats.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2012-09-05
# Last Edit: 2017-12-06
# Creator:  Kirsten R. Hazler
#
# Summary:
#     Creates Procedural Features (PFs) from Source Features (SFs) by buffering as needed.
#
# Usage Notes:
#-  This script accepts a shapefile or geodatabase feature class as input.
#-  To function properly, the input data must have the fields indicating the type and distance of locational uncertainty, which together determine the buffer distance (or lack of buffer).
#-  Note that this script creates and deletes temporary files within the workspace, and will overwrite any existing data of the same name.
#-  The feature class output by this script can be used as input for generating Site Building Blocks (SBBs) from Procedural Features.
#
# -------------------------------------------------------------------------------------------------------

# Import function libraries and settings
import libConSiteFx
from libConSiteFx import *

def CreatePFs(inSF, outPF, fld_luType = 'luType', fld_luDist = 'luDist', ):
   """Creates Procedural Features (PFs) from Source Features (SFs) by buffering as needed.
      inSF: Input Source Features
      outPF: Output Procedural Features
      fld_luType: Field containing Locational Uncertainty type
      fld_luDist: Field containing Locational Uncertainty distance"""
      
   # Set up some variables
   tmpWorkspace = createTmpWorkspace()
   sr = arcpy.Describe(in_PF).spatialReference
   printMsg("Additional critical temporary products will be stored here: %s" % tmpWorkspace)

   try:   
      # Print helpful messages to geoprocessing window
      printMsg("\nYour input feature class is " + inSF)
      printMsg("\nYour output feature class is " + outPF)
      printMsg("\nYour temporary workspace is " + tmpWorkspace)

      # Process:  Describe (determine geometry type of source features)
      myGeometry = arcpy.Describe(inSF).shapeType
      printMsg("\nThe input geometry type is " + myGeometry)
      
      if myGeometry == "Polygon":
         # Select and process features where buffer is needed)
         printMsg("\nSelecting features to buffer...")
         arcpy.MakeFeatureLayer_management(inSF, "mySF2Buff", "\"LOC_UNCERT\" = 'Estimated'")
         myBufferedFeatures = tmpWorkspace + os.sep + "BufferedFeatures"
         if arcpy.Exists(myBufferedFeatures):
            printMsg("\nDeleting pre-existing buffers...")
            arcpy.Delete_management(myBufferedFeatures) # Delete pre-existing output data
         arcpy.Buffer_analysis ("mySF2Buff", myBufferedFeatures, "LOC_UNCE_1", "FULL", "ROUND", "NONE", "")
         printMsg("\nBuffering features...")

         # Select features where buffer is not needed
         printMsg("\nSelecting features that will remain unbuffered...")
         arcpy.MakeFeatureLayer_management(inSF, "myUnbufferedFeatures", "\"LOC_UNCERT\" <> 'Estimated'")
         
         # Process: Merge buffered and unbuffered features into single output feature class
         printMsg("\nMerging buffered and unbuffered features...")
         arcpy.Merge_management([myBufferedFeatures,"myUnbufferedFeatures"], outPF)

      else: #if input is points or lines
         # Select and process features with estimated uncertainty
         printMsg("\nSelecting features to buffer...")
         arcpy.MakeFeatureLayer_management(inSF, "myEstBuff", "\"LOC_UNCERT\" = 'Estimated'")
         myEstBuffFeatures = tmpWorkspace + os.sep + "EstBuffFeats"
         if arcpy.Exists(myEstBuffFeatures):
            printMsg("\nDeleting pre-existing buffers...")
            arcpy.Delete_management(myEstBuffFeatures) # Delete pre-existing output data
         arcpy.Buffer_analysis ("myEstBuff", myEstBuffFeatures, "LOC_UNCE_1", "FULL", "ROUND", "NONE", "")
         printMsg("\nBuffering features...")

         # Select and process features with negligible or linear uncertainty
         printMsg("\nSelecting features to buffer...")
         arcpy.MakeFeatureLayer_management(inSF, "myNegBuff", "\"LOC_UNCERT\" <> 'Estimated'")
         myNegBuffFeatures = tmpWorkspace + os.sep + "NegBuffFeats"
         if arcpy.Exists(myNegBuffFeatures):
            printMsg("\nDeleting pre-existing buffers...")
            arcpy.Delete_management(myNegBuffFeatures) # Delete pre-existing output data
         arcpy.Buffer_analysis ("myNegBuff", myNegBuffFeatures, "4.5 METERS", "FULL", "ROUND", "NONE", "")
         printMsg("\nBuffering features...")

         # Process: Merge (combine buffered features into single output feature class)
         printMsg("\nMerging features...")
         arcpy.Merge_management([myEstBuffFeatures, myNegBuffFeatures], outPF)
         

         
   # Error handling swiped from "A Python Primer for ArcGIS"
   except:
      tb = sys.exc_info()[2]
      tbinfo = traceback.format_tb(tb)[0]
      pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n "
      msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

      arcpy.AddError(msgs)
      arcpy.AddError(pymsg)
      printMsg(arcpy.GetMessages(1))

   # Additional code to run regardless of whether the script succeeds or not




