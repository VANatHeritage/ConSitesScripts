# ----------------------------------------------------------------------------------------
# Helper.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2017-08-08
# Last Edit: 2020-06-22
# Creator:  Kirsten R. Hazler

# Summary:
# A library of generally useful helper functions 

# ----------------------------------------------------------------------------------------

# Import modules
import os, sys, traceback, numpy
try:
   arcpy
   print "Arcpy is already loaded"
except:
   print "Initiating arcpy, which takes longer than it should..."
   import arcpy   

from datetime import datetime as datetime   
   
# Set overwrite option so that existing data may be overwritten
arcpy.env.overwriteOutput = True


def getScratchMsg(scratchGDB):
   '''Prints message informing user of where scratch output will be written'''
   if scratchGDB != "in_memory":
      msg = "Scratch outputs will be stored here: %s" % scratchGDB
   else:
      msg = "Scratch products are being stored in memory and will not persist. If processing fails inexplicably, or if you want to be able to inspect scratch products, try running this with a specified scratchGDB on disk."
   
   return msg
   
def printMsg(msg):
   arcpy.AddMessage(msg)
   print msg
   
def printWrng(msg):
   arcpy.AddWarning(msg)
   print 'Warning: ' + msg
   
def printErr(msg):
   arcpy.AddError(msg)
   print 'Error: ' + msg

def garbagePickup(trashList):
   '''Deletes Arc files in list, with error handling. Argument must be a list.'''
   for t in trashList:
      try:
         arcpy.Delete_management(t)
      except:
         pass
   return
   
def CleanFeatures(inFeats, outFeats):
   '''Repairs geometry, then explodes multipart polygons to prepare features for geoprocessing.'''
   
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
   
   return outFeats

def CleanClip(inFeats, clipFeats, outFeats, scratchGDB = "in_memory"):
   '''Clips the Input Features with the Clip Features.  The resulting features are then subjected to geometry repair and exploded (eliminating multipart polygons)'''
   # # Determine where temporary data are written
   # msg = getScratchMsg(scratchGDB)
   # arcpy.AddMessage(msg)
   
   # Process: Clip
   tmpClip = scratchGDB + os.sep + "tmpClip"
   arcpy.Clip_analysis(inFeats, clipFeats, tmpClip)

   # Process: Clean Features
   CleanFeatures(tmpClip, outFeats)
   
   # Cleanup
   if scratchGDB == "in_memory":
      garbagePickup([tmpClip])
   
   return outFeats
   
def CleanErase(inFeats, eraseFeats, outFeats, scratchGDB = "in_memory"):
   '''Uses Eraser Features to erase portions of the Input Features, then repairs geometry and explodes any multipart polygons.'''
   # # Determine where temporary data are written
   # msg = getScratchMsg(scratchGDB)
   # arcpy.AddMessage(msg)
   
   # Process: Erase
   tmpErased = scratchGDB + os.sep + "tmpErased"
   arcpy.Erase_analysis(inFeats, eraseFeats, tmpErased, "")

   # Process: Clean Features
   CleanFeatures(tmpErased, outFeats)
   
   # Cleanup
   if scratchGDB == "in_memory":
      garbagePickup([tmpErased])
   
   return outFeats
   
def countFeatures(features):
   '''Gets count of features'''
   count = int((arcpy.GetCount_management(features)).getOutput(0))
   return count
   
def countSelectedFeatures(featureLyr):
   '''Gets count of selected features in a feature layer'''
   desc = arcpy.Describe(featureLyr)
   count = len(desc.FIDSet)
   return count

def SelectCopy(in_FeatLyr, selFeats, selDist, out_Feats):
   '''Selects features within specified distance of selection features, and copies to output.
   Input features to be selected must be a layer, not a feature class.
   NOTE: This does not seem to work with feature services. ESRI FAIL.'''
   # Select input features within distance of selection features
   arcpy.SelectLayerByLocation_management (in_FeatLyr, "WITHIN_A_DISTANCE", selFeats, selDist, "NEW_SELECTION", "NOT_INVERT")
   
   # Get the number of SELECTED features
   numSelected = countSelectedFeatures(in_FeatLyr)
   
   # Copy selected features to output
   if numSelected == 0:
      # Create an empty dataset
      fc = os.path.basename(out_Feats)
      gdb = os.path.dirname(out_Feats)
      geom = arcpy.Describe(in_Feats).shapeType
      CreateFeatureclass_management (gdb, fc, geom, in_Feats)
   else:
      arcpy.CopyFeatures_management (in_FeatLyr, out_Feats)
      
   return out_Feats

def unique_values(table, field):
   '''This function was obtained from:
   https://arcpy.wordpress.com/2012/02/01/create-a-list-of-unique-field-values/'''
   with arcpy.da.SearchCursor(table, [field]) as cursor:
      return sorted({row[0] for row in cursor})
   
def TabToDict(inTab, fldKey, fldValue):
   '''Converts two fields in a table to a dictionary'''
   codeDict = {}
   with arcpy.da.SearchCursor(inTab, [fldKey, fldValue]) as sc:
      for row in sc:
         key = sc[0]
         val = sc[1]
         codeDict[key] = val
   return codeDict 
   
def GetElapsedTime (t1, t2):
   """Gets the time elapsed between the start time (t1) and the finish time (t2)."""
   delta = t2 - t1
   (d, m, s) = (delta.days, delta.seconds/60, delta.seconds%60)
   (h, m) = (m/60, m%60)
   deltaString = '%s days, %s hours, %s minutes, %s seconds' % (str(d), str(h), str(m), str(s))
   return deltaString

def multiMeasure(meas, multi):
   '''Given a measurement string such as "100 METERS" and a multiplier, multiplies the number by the specified multiplier, and returns a new measurement string along with its individual components'''
   parseMeas = meas.split(" ") # parse number and units
   num = float(parseMeas[0]) # convert string to number
   units = parseMeas[1]
   num = num * multi
   newMeas = str(num) + " " + units
   measTuple = (num, units, newMeas)
   return measTuple
   
def createFGDB(FGDB):
   '''Checks to see if specified file geodatabase exists, and creates it if not.
   Parameters:
   - FGDB: full path to file geodatabase (e.g. r'C:\myDir\myGDB.gdb')
   '''
   gdbPath = os.path.dirname(FGDB)
   gdbName = os.path.basename(FGDB)
   
   if arcpy.Exists(FGDB):
      printMsg("%s already exists." %gdbName)
      pass
   else:
      printMsg("Creating new file geodatabase...")
      arcpy.CreateFileGDB_management(gdbPath, gdbName)
      printMsg("%s created." %gdbName)
   return FGDB

def createTmpWorkspace():
   '''Creates a new temporary geodatabase with a timestamp tag, within the current scratchFolder'''
   # Get time stamp
   ts = datetime.now().strftime("%Y%m%d_%H%M%S") # timestamp
   
   # Create new file geodatabase
   gdbPath = arcpy.env.scratchFolder
   gdbName = 'tmp_%s.gdb' %ts
   tmpWorkspace = gdbPath + os.sep + gdbName 
   arcpy.CreateFileGDB_management(gdbPath, gdbName)
   
   return tmpWorkspace

def tback():
   '''Standard error handling routing to add to bottom of scripts'''
   tb = sys.exc_info()[2]
   tbinfo = traceback.format_tb(tb)[0]
   pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
   msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"
   msgList = [pymsg, msgs]

   printErr(msgs)
   printErr(pymsg)
   printMsg(arcpy.GetMessages(1))
   
   return msgList
   
def clearSelection(fc):
   typeFC= (arcpy.Describe(fc)).dataType
   if typeFC == 'FeatureLayer':
      arcpy.SelectLayerByAttribute_management (fc, "CLEAR_SELECTION")
      
def Coalesce(inFeats, dilDist, outFeats, scratchGDB = "in_memory"):
   '''If a positive number is entered for the dilation distance, features are expanded outward by the specified distance, then shrunk back in by the same distance. This causes nearby features to coalesce. If a negative number is entered for the dilation distance, features are first shrunk, then expanded. This eliminates narrow portions of existing features, thereby simplifying them. It can also break narrow "bridges" between features that were formerly coalesced.'''
   
   # If it's a string, parse dilation distance and get the negative
   if type(dilDist) == str:
      origDist, units, meas = multiMeasure(dilDist, 1)
      negDist, units, negMeas = multiMeasure(dilDist, -1)
   else:
      origDist = dilDist
      meas = dilDist
      negDist = -1*origDist
      negMeas = negDist

   # Parameter check
   if origDist == 0:
      arcpy.AddError("You need to enter a non-zero value for the dilation distance")
      raise arcpy.ExecuteError   

   # Set parameters. Dissolve parameter depends on dilation distance.
   if origDist > 0:
      dissolve1 = "ALL"
      dissolve2 = "NONE"
   else:
      dissolve1 = "NONE"
      dissolve2 = "ALL"

   # Process: Buffer
   Buff1 = scratchGDB + os.sep + "Buff1"
   arcpy.Buffer_analysis(inFeats, Buff1, meas, "FULL", "ROUND", dissolve1, "", "GEODESIC")

   # Process: Clean Features
   Clean_Buff1 = scratchGDB + os.sep + "CleanBuff1"
   CleanFeatures(Buff1, Clean_Buff1)

   # Process:  Generalize Features
   # This should prevent random processing failures on features with many vertices, and also speed processing in general
   #arcpy.Generalize_edit(Clean_Buff1, "0.1 Meters")
   
   # Eliminate gaps
   # Added step due to weird behavior on some buffers
   Clean_Buff1_ng = scratchGDB + os.sep + "Clean_Buff1_ng"
   arcpy.EliminatePolygonPart_management (Clean_Buff1, Clean_Buff1_ng, "AREA", "900 SQUAREMETERS", "", "CONTAINED_ONLY")

   # Process: Buffer
   Buff2 = scratchGDB + os.sep + "NegativeBuffer"
   arcpy.Buffer_analysis(Clean_Buff1_ng, Buff2, negMeas, "FULL", "ROUND", dissolve2, "", "GEODESIC")

   # Process: Clean Features to get final dilated features
   CleanFeatures(Buff2, outFeats)
      
   # Cleanup
   if scratchGDB == "in_memory":
      garbagePickup([Buff1, Clean_Buff1, Buff2])
      
   return outFeats
   
def ShrinkWrap(inFeats, dilDist, outFeats, smthMulti = 8, scratchGDB = "in_memory"):
   # Parse dilation distance, and increase it to get smoothing distance
   smthMulti = float(smthMulti)
   origDist, units, meas = multiMeasure(dilDist, 1)
   smthDist, units, smthMeas = multiMeasure(dilDist, smthMulti)

   # Parameter check
   if origDist <= 0:
      arcpy.AddError("You need to enter a positive, non-zero value for the dilation distance")
      raise arcpy.ExecuteError   

   #tmpWorkspace = arcpy.env.scratchGDB
   #arcpy.AddMessage("Additional critical temporary products will be stored here: %s" % tmpWorkspace)
   
   # Set up empty trashList for later garbage collection
   trashList = []

   # Declare path/name of output data and workspace
   drive, path = os.path.splitdrive(outFeats) 
   path, filename = os.path.split(path)
   myWorkspace = drive + path
   Output_fname = filename

   # Process:  Create Feature Class (to store output)
   arcpy.CreateFeatureclass_management (myWorkspace, Output_fname, "POLYGON", "", "", "", inFeats) 

   # Process:  Clean Features
   #cleanFeats = tmpWorkspace + os.sep + "cleanFeats"
   cleanFeats = scratchGDB + os.sep + "cleanFeats"
   CleanFeatures(inFeats, cleanFeats)
   trashList.append(cleanFeats)

   # Process:  Dissolve Features
   #dissFeats = tmpWorkspace + os.sep + "dissFeats"
   # Writing to disk in hopes of stopping geoprocessing failure
   #arcpy.AddMessage("This feature class is stored here: %s" % dissFeats)
   dissFeats = scratchGDB + os.sep + "dissFeats"
   arcpy.Dissolve_management (cleanFeats, dissFeats, "", "", "SINGLE_PART", "")
   trashList.append(dissFeats)

   # Process:  Generalize Features
   # This should prevent random processing failures on features with many vertices, and also speed processing in general
   arcpy.Generalize_edit(dissFeats, "0.1 Meters")

   # Process:  Buffer Features
   #arcpy.AddMessage("Buffering features...")
   #buffFeats = tmpWorkspace + os.sep + "buffFeats"
   buffFeats = scratchGDB + os.sep + "buffFeats"
   arcpy.Buffer_analysis (dissFeats, buffFeats, meas, "", "", "ALL")
   trashList.append(buffFeats)

   # Process:  Explode Multiparts
   #explFeats = tmpWorkspace + os.sep + "explFeats"
   # Writing to disk in hopes of stopping geoprocessing failure
   #arcpy.AddMessage("This feature class is stored here: %s" % explFeats)
   explFeats = scratchGDB + os.sep + "explFeats"
   arcpy.MultipartToSinglepart_management (buffFeats, explFeats)
   trashList.append(explFeats)

   # Process:  Get Count
   numWraps = (arcpy.GetCount_management(explFeats)).getOutput(0)
   arcpy.AddMessage('Shrinkwrapping: There are %s features after consolidation' %numWraps)

   # Loop through the exploded buffer features
   counter = 1
   with arcpy.da.SearchCursor(explFeats, ["SHAPE@"]) as myFeats:
      for Feat in myFeats:
         arcpy.AddMessage('Working on shrink feature %s' % str(counter))
         featSHP = Feat[0]
         tmpFeat = scratchGDB + os.sep + "tmpFeat"
         arcpy.CopyFeatures_management (featSHP, tmpFeat)
         trashList.append(tmpFeat)
         
         # Process:  Repair Geometry
         arcpy.RepairGeometry_management (tmpFeat, "DELETE_NULL")
         
         # Process:  Make Feature Layer
         arcpy.MakeFeatureLayer_management (dissFeats, "dissFeatsLyr", "", "", "")
         trashList.append("dissFeatsLyr")

         # Process: Select Layer by Location (Get dissolved features within each exploded buffer feature)
         arcpy.SelectLayerByLocation_management ("dissFeatsLyr", "INTERSECT", tmpFeat, "", "NEW_SELECTION")
         
         # Process:  Coalesce features (expand)
         coalFeats = scratchGDB + os.sep + 'coalFeats'
         Coalesce("dissFeatsLyr", smthMeas, coalFeats, scratchGDB)
         # Increasing the dilation distance improves smoothing and reduces the "dumbbell" effect. However, it can also cause some wonkiness which needs to be corrected in the next steps.
         trashList.append(coalFeats)
         
         # Merge coalesced feature with original features, and coalesce again.
         mergeFeats = scratchGDB + os.sep + 'mergeFeats'
         arcpy.Merge_management([coalFeats, "dissFeatsLyr"], mergeFeats, "")
         Coalesce(mergeFeats, "5 METERS", coalFeats, scratchGDB)
         
         # Eliminate gaps
         noGapFeats = scratchGDB + os.sep + "noGapFeats"
         arcpy. EliminatePolygonPart_management (coalFeats, noGapFeats, "PERCENT", "", 99, "CONTAINED_ONLY")
         
         # Process:  Append the final geometry to the ShrinkWrap feature class
         arcpy.AddMessage("Appending feature...")
         arcpy.Append_management(noGapFeats, outFeats, "NO_TEST", "", "")
         
         counter +=1
         del Feat

   # Cleanup
   if scratchGDB == "in_memory":
      garbagePickup(trashList)
      
   return outFeats
   
def CompareSpatialRef(in_Data, in_Template):
   sr_In = arcpy.Describe(in_Data).spatialReference
   sr_Out = arcpy.Describe(in_Template).spatialReference
   srString_In = sr_In.exporttostring()
   srString_Out = sr_Out.exporttostring()
   gcsString_In = sr_In.GCS.exporttostring()
   gcsString_Out = sr_Out.GCS.exporttostring()
    
   if srString_In == srString_Out:
      reproject = 0
      transform = 0
      geoTrans = ""
   else:
      reproject = 1
      
   if reproject == 1:
      if gcsString_In == gcsString_Out:
         transform = 0
         geoTrans = ""
      else:
         transList = arcpy.ListTransformations(sr_In, sr_Out)
         if len(transList) == 0:
            transform = 0
            geoTrans = ""
         else:
            transform = 1
            geoTrans = transList[0]
         
   return (sr_In, sr_Out, reproject, transform, geoTrans)

def ProjectToMatch_vec(in_Data, in_Template, out_Data, copy = 1):
   '''Check if input features and template data have same spatial reference.
   If so, make a copy. If not, reproject features to match template.
   
   Parameters:
   in_Data: input features to be reprojected or copied
   in_Template: dataset used to determine desired spatial reference
   out_Data: output features resulting from copy or reprojection
   copy: indicates whether to make a copy (1) or not (0) for data that don't need to be reprojected
   '''
   
   # Compare the spatial references of input and template data
   (sr_In, sr_Out, reproject, transform, geoTrans) = CompareSpatialRef(in_Data, in_Template)
   
   if reproject == 0:
      printMsg('Coordinate systems for features and template data are the same.')
      if copy == 1: 
         printMsg('Copying...')
         arcpy.CopyFeatures_management (in_Data, out_Data)
      else:
         printMsg('Returning original data unchanged.')
         out_Data = in_Data
   else:
      printMsg('Reprojecting features to match template...')
      if transform == 0:
         printMsg('No geographic transformation needed...')
      else:
         printMsg('Applying an appropriate geographic transformation...')
      arcpy.Project_management (in_Data, out_Data, sr_Out, geoTrans)
   return out_Data
   
def ProjectToMatch_ras(in_Data, in_Template, out_Data, resampleType = "NEAREST"):
   '''Check if input raster and template raster have same spatial reference.
   If not, reproject input to match template.
   Parameters:
   in_Data = input raster to be reprojected
   in_Template = dataset used to determine desired spatial reference and cell alignment
   out_Data = output raster resulting from resampling
   resampleType = type of resampling to use (NEAREST, MAJORITY, BILINEAR, or CUBIC)
   '''
   
   # Compare the spatial references of input and template data
   (sr_In, sr_Out, reproject, transform, geoTrans) = CompareSpatialRef(in_Data, in_Template)
   
   if reproject == 0:
      printMsg('Coordinate systems for input and template data are the same. No need to reproject.')
      return in_Data
   else:
      printMsg('Reprojecting input raster to match template...')
      arcpy.env.snapRaster = in_Template
      if transform == 0:
         printMsg('No geographic transformation needed...')
      else:
         printMsg('Applying an appropriate geographic transformation...')
      arcpy.ProjectRaster_management (in_Data, out_Data, sr_Out, resampleType, "", geoTrans)
      return out_Data
      
def clipRasterToPoly(in_Rast, in_Poly, out_Rast):
   '''Clips a raster to a polygon feature class.
   
   Parameters:
   in_Rast: Input raster to be clipped
   in_Poly: Input polygon feature class or a geometry object to be used for clipping
   out_Rast: Output clipped raster
   '''
   try:
      # This should work if input is a feature class
      myExtent = str(arcpy.Describe(in_Poly).extent).replace(" NaN", "")
   except:
      # This should work if input is a geometry object
      myExtent = str(in_Poly.extent).replace(" NaN", "")
   arcpy.Clip_management (in_Rast, myExtent, out_Rast, in_Poly, "", "ClippingGeometry")
   
   return out_Rast