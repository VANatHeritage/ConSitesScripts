# ----------------------------------------------------------------------------------------
# libConSiteFx.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2017-08-08 (Adapted from a ModelBuilder model)
# Last Edit: 2017-08-11
# Creator:  Kirsten R. Hazler

# Summary:
# A library of functions used to automatically delineate Natural Heritage Conservation Sites 
# ----------------------------------------------------------------------------------------

# Import modules
import arcpy, os, sys, traceback
from time import time as t

# Set overwrite option so that existing data may be overwritten
   arcpy.env.overwriteOutput = True
   
def createTmpWorkspace():
   '''Creates a new temporary geodatabase with a timestamp tag, within the current scratchFolder'''
   # Get time stamp
   ts = int(t())
   
   # Create new file geodatabase
   gdbPath = arcpy.env.scratchFolder
   gdbName = 'tmp_%s.gdb' %ts
   tmpWorkspace = gdbPath + os.sep + gdbName 
   arcpy.CreateFileGDB_management(gdbPath, gdbName)
   
   return tmpWorkspace

def getScratchMsg(scratchGDB):
   '''Prints message informing user of where scratch output will be written'''
   if scratchGDB != "in_memory":
      msg = "Scratch outputs will be stored here: %s" % scratchGDB
   else:
      msg = "Scratch products are being stored in memory and will not persist. If processing fails inexplicably, or if you want to be able to inspect scratch products, try running this with a specified scratchGDB on disk."
   
   return msg
   
def tback():
   '''Standard error handling routing to add to bottom of scripts'''
   tb = sys.exc_info()[2]
   tbinfo = traceback.format_tb(tb)[0]
   pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
   msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"
   msgList = [pymsg, msgs]

   arcpy.AddError(msgs)
   arcpy.AddError(pymsg)
   arcpy.AddMessage(arcpy.GetMessages(1))
   
   return msgList
   
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
   # Determine where temporary data are written
   msg = getScratchMsg(scratchGDB)
   arcpy.AddMessage(msg)
   
   # Process: Clip
   tmpClip = scratchGDB + os.sep + "tmpClip"
   arcpy.Clip_analysis(inFeats, clipFeats, tmpClip)

   # Process: Clean Features
   arcpy.CleanFeatures_consiteTools(tmpClip, outFeats)
   
   # Cleanup
   garbagePickup([tmpClip])
   
   return outFeats
   
def CleanErase(inFeats, eraseFeats, outFeats, scratchGDB = "in_memory"):
   '''Uses Eraser Features to erase portions of the Input Features, then repairs geometry and explodes any multipart polygons.'''
   # Determine where temporary data are written
   msg = getScratchMsg(scratchGDB)
   arcpy.AddMessage(msg)
   
   # Process: Erase
   tmpErased = scratchGDB + os.sep + "tmpErased"
   arcpy.Erase_analysis(inFeats, eraseFeats, tmpErased, "")

   # Process: Clean Features
   arcpy.CleanFeatures_consiteTools(tmpErased, outFeats)
   
   # Cleanup
   garbagePickup([tmpErased])
   
   return outFeats
   
def Coalesce(inFeats, dilDist, outFeats, scratchGDB = "in_memory"):
   '''If a positive number is entered for the dilation distance, features are expanded outward by the specified distance, then shrunk back in by the same distance. This causes nearby features to coalesce. If a negative number is entered for the dilation distance, features are first shrunk, then expanded. This eliminates narrow portions of existing features, thereby simplifying them. It can also break narrow "bridges" between features that were formerly coalesced.'''
   # Parameter check
   if dilDist == 0:
   arcpy.AddError("You need to enter a non-zero value for the dilation distance")
      raise arcpy.ExecuteError   
   
   # Determine where temporary data are written
   msg = getScratchMsg(scratchGDB)
   arcpy.AddMessage(msg)
   
   # Set parameters. Dissolve parameter depends on dilation distance.
   oppDist = -dilDist
   if dilDist > 0:
      dissolve1 = "ALL"
      dissolve2 = "NONE"
   else:
      dissolve1 = "NONE"
      dissolve2 = "ALL"

   # Process: Buffer
   Buff1 = scratchGDB + os.sep + "Buff1"
   arcpy.Buffer_analysis(inFeats, Buff1, dilDist, "FULL", "ROUND", dissolve1, "", "PLANAR")

   # Process: Clean Features
   Clean_Buff1 = scratchGDB + os.sep + "CleanBuff1"
   CleanFeatures(Buff1, Clean_Buff1)

   # Process:  Generalize Features
   # This should prevent random processing failures on features with many vertices, and also speed processing in general
   arcpy.Generalize_edit(Clean_Buff1, "0.1 Meters")

   # Process: Buffer
   Buff2 = scratchGDB + os.sep + "NegativeBuffer"
   arcpy.Buffer_analysis(Clean_Buff1, Buff2, oppDist, "FULL", "ROUND", dissolve2, "", "PLANAR")

   # Process: Clean Features to get final dilated features
   CleanFeatures(Buff2, outFeats)
      
   # Cleanup
   garbagePickup([Buff1, Clean_Buff1, Buff2])
   
def ShrinkWrap(inFeats, dilDist, outFeats, scratchGDB = "in_memory"):
   # Parameter check
   if dilDist <= 0:
      arcpy.AddError("You need to enter a positive, non-zero value for the dilation distance")
      raise arcpy.ExecuteError   

   # Determine where temporary data are written
   msg = getScratchMsg(scratchGDB)
   arcpy.AddMessage(msg)

   tmpWorkspace = createTmpWorkspace()
   arcpy.AddMessage("Additional critical temporary products will be stored here: %s" % tmpWorkspace)
   
   # Set up empty trashList for later garbage collection
   trashList = []

   # Declare path/name of output data and workspace
   drive, path = os.path.splitdrive(outFeats) 
   path, filename = os.path.split(path)
   myWorkspace = drive + path
   Output_fname = filename

   # Process:  Create Feature Class (to store output)
   arcpy.AddMessage("Creating feature class to store output features...")
   arcpy.CreateFeatureclass_management (myWorkspace, Output_fname, "POLYGON", "", "", "", inFeats) 

   # Process:  Clean Features
   arcpy.AddMessage("Cleaning input features...")
   cleanFeats = tmpWorkspace + os.sep + "cleanFeats"
   CleanFeatures(inFeats, cleanFeats)
   trashList.append(cleanFeats)

   # Process:  Dissolve Features
   arcpy.AddMessage("Dissolving adjacent features...")
   dissFeats = tmpWorkspace + os.sep + "dissFeats"
   # Writing to disk in hopes of stopping geoprocessing failure
   arcpy.AddMessage("This feature class is stored here: %s" % dissFeats)
   arcpy.Dissolve_management (cleanFeats, dissFeats, "", "", "SINGLE_PART", "")
   trashList.append(dissFeats)

   # Process:  Generalize Features
   # This should prevent random processing failures on features with many vertices, and also speed processing in general
   arcpy.AddMessage("Simplifying features...")
   arcpy.Generalize_edit(dissFeats, "0.1 Meters")

   # Process:  Buffer Features
   arcpy.AddMessage("Buffering features...")
   buffFeats = tmpWorkspace + os.sep + "buffFeats"
   arcpy.Buffer_analysis (dissFeats, buffFeats, dilDist, "", "", "ALL")
   trashList.append(buffFeats)

   # Process:  Explode Multiparts
   arcpy.AddMessage("Exploding multipart features...")
   explFeats = tmpWorkspace + os.sep + "explFeats"
   # Writing to disk in hopes of stopping geoprocessing failure
   arcpy.AddMessage("This feature class is stored here: %s" % explFeats)
   arcpy.MultipartToSinglepart_management (buffFeats, explFeats)
   trashList.append(explFeats)

   # Process:  Get Count
   numWraps = (arcpy.GetCount_management(explFeats)).getOutput(0)
   arcpy.AddMessage('There are %s features after consolidation' %numWraps)

   # Loop through the exploded buffer features
   myFeats = arcpy.da.SearchCursor(explFeats, ["SHAPE@"])
   counter = 1
   for Feat in myFeats:
      arcpy.AddMessage('Working on feature %s' % str(counter))
      featSHP = Feat[0]
      tmpFeat = scratchGDB + os.sep + "tmpFeat"
      arcpy.CopyFeatures_management (featSHP, tmpFeat)
      trashList.append.(tmpFeat)
      
      # Process:  Repair Geometry
      arcpy.RepairGeometry_management (tmpFeat, "DELETE_NULL")
      
      # Process:  Make Feature Layer
      arcpy.MakeFeatureLayer_management (dissFeats, "dissFeatsLyr", "", "", "")
      trashList.append(dissFeatsLyr)

      # Process: Select Layer by Location (Get dissolved features within each exploded buffer feature)
      arcpy.SelectLayerByLocation_management ("dissFeatsLyr", "INTERSECT", tmpFeat, "", "NEW_SELECTION")
      
      # Process:  Coalesce features (expand)
      coalFeats = scratchGDB + os.sep + 'coalFeats'
      Coalesce("dissFeatsLyr", 8*dilDist, coalFeats, scratchParm)
      # Increasing the dilation distance improves smoothing and reduces the "dumbbell" effect.
      trashList.append(coalFeats)
      
      # Process:  Union coalesced features (to remove gaps)
      # This is only necessary b/c we are now applying this tool to the Cores layer, which has gaps
      unionFeats = scratchGDB + os.sep + "unionFeats"
      arcpy.Union_analysis ([coalFeats], unionFeats, "ONLY_FID", "", "NO_GAPS") 
      trashList.append(unionFeats)
      
      # Process:  Dissolve again 
      dissunionFeats = scratchGDB + os.sep + "dissunionFeats"
      arcpy.Dissolve_management (unionFeats, dissunionFeats, "", "", "SINGLE_PART", "")
      trashList.append(dissunionFeats)
      
      # Process:  Append the final geometry to the ShrinkWrap feature class
      arcpy.AddMessage("Appending feature...")
      arcpy.Append_management(dissunionFeats, outFeats, "NO_TEST", "", "")
      
      counter +=1

   # Cleanup
   garbagePickup([tmpWorkspace])
   garbagePickup(trashList)
   
   