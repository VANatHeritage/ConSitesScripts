# ----------------------------------------------------------------------------------------
# CreateStandardWetlandSBB.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2013-01-23
# Last Edit: 2016-09-16
# Creator:  Kirsten R. Hazler
#
# Summary:
#     Creates Site Building Blocks (SBBs) from Rule 5, 6, 7, or 9 Procedural Features (PFs).
#     The procedures are the same for all rules, the only difference being the rule-specific 
#     inputs.
#     Carries out the following general procedures:
#     1.  Buffer the PF by 250-m.  This is the minimum buffer.
#     2.  Buffer the PF by 500-m.  This is the maximum buffer.
#     3.  Select any appropriate NWI wetland features within 15-m of the PF.
#     4.  Buffer the selected NWI feature(s), if applicable, by 100-m.
#     5.  Merge the minimum buffer with the buffered NWI feature(s).
#     6.  Clip the merged feature to the maximum buffer.
#
# Usage Tips:
#     *  This tool accepts a shapefile or geodatabase feature classes as vector inputs.
#     *  This tool does not test to determine if all of the input Procedural Features 
#        should be subject to a particular rule. The user must ensure that this is so.
#     *  It is recommended that the NWI feature class be stored on your local drive 
#        rather than a network drive, to optimize processing speed.
#     *  For this tool to function properly, the input NWI data must contain a subset of 
#        only those features applicable to the particular rule.  Adjacent NWI features 
#        should have boundaries dissolved.
#     *  This tool is designed to send all output to a feature class within a geodatabase. 
#        It has not been tested for output to shapefiles.
#     *  For best results, it is recommended that you close all other programs before 
#        running this tool, since it relies on having ample memory for processing.
#
# Syntax:
# CreateStandardWetlandSBB_consiteTools(Input_PF, Input_SFID, Input_NWI, Output_SBB)
# ----------------------------------------------------------------------------------------
ScriptDate = '2016-03-15' # Used for informative message down below

# Import required modules
import arcpy # provides access to all ArcGIS geoprocessing functions
import os # provides access to operating system funtionality 
import sys # provides access to Python system functions
import traceback # used for error handling
import csv # provides ability to write rows to a text file
import gc # garbage collection
from datetime import datetime as dt # for timestamping

# outScratch = arcpy.env.scratchGDB # Use this for trouble-shooting only
# arcpy.AddMessage('Scratch products will be stored in %s' % outScratch)
outScratch = "in_memory"

# Script arguments to be input by user...
Input_PF = arcpy.GetParameterAsText(0) 
   # An input feature class or feature layer representing Procedural Features
Input_SFID = arcpy.GetParameterAsText(1) 
   # The name of the field containing the unique source feature ID
Input_NWI = arcpy.GetParameterAsText(2) 
   # An input feature class or feature layer representing National Wetlands Inventory
   # This must be a subset containing rule-specific features only, with boundaries of 
   # adjacent polygons dissolved
Output_SBB = arcpy.GetParameterAsText(3) 
   # An output feature class representing Site Building Blocks

# Declare some additional parameters
# These can be tweaked as desired
nwiBuff = 100 # buffer to be used for NWI features (may or may not equal minBuff)
minBuff = 250 # minimum buffer to include in SBB
maxBuff = 500 # maximum buffer to include in SBB
searchDist = 15 # search distance for inclusion of NWI features

# Create an empty list to store IDs of features that fail to get processed
myFailList = []

# Declare path/name of output data and workspace
drive, path = os.path.splitdrive(Output_SBB) 
path, filename = os.path.split(path)
myWorkspace = drive + os.sep + path
myFolder = os.path.abspath(os.path.join(myWorkspace,".."))
Output_SBB_fname = filename
ts = dt.now().strftime("%Y%m%d_%H%M%S") # timestamp
myFailLog = myFolder + os.sep + 'FailLog_wetlands_%s' % ts 
   # text file storing features that fail to get processed

# Set environmental variables
arcpy.env.workspace = outScratch # Set the workspace for geoprocessing
arcpy.env.scratchWorkspace = outScratch # Set the scratch workspace for geoprocessing
arcpy.env.overwriteOutput = True # Existing data may be overwritten
arcpy.env.outputCoordinateSystem = "PROJCS['NAD_1983_Virginia_Lambert',GEOGCS['GCS_North_American_1983',DATUM['D_North_American_1983',SPHEROID['GRS_1980',6378137.0,298.257222101]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Lambert_Conformal_Conic'],PARAMETER['False_Easting',0.0],PARAMETER['False_Northing',0.0],PARAMETER['Central_Meridian',-79.5],PARAMETER['Standard_Parallel_1',37.0],PARAMETER['Standard_Parallel_2',39.5],PARAMETER['Latitude_Of_Origin',36.0],UNIT['Meter',1.0],AUTHORITY['EPSG',3968]]"

# Check to make sure input data have spatial reference defined and matching; if not then
# exit gracefully.
# Part of this has been commented out for now, so it does NOT enforce projection match.
arcpy.AddMessage("Checking spatial references...")
mySR_PF = arcpy.Describe(Input_PF).spatialReference.name
mySR_NWI = arcpy.Describe(Input_NWI).spatialReference.name

if mySR_PF == "Unknown":
   arcpy.AddError("Your Procedural Features feature class has no defined spatial reference.")
   arcpy.AddError("Please define the spatial reference of your data or select a different feature class.")
   arcpy.AddError("Then try this tool again.")

elif mySR_NWI == "Unknown":
   arcpy.AddError("Your NWI feature class has no defined spatial reference.")
   arcpy.AddError("Please define the spatial reference of your data or select a different feature class.")
   arcpy.AddError("Then try this tool again.")
   
# elif mySR_PF != mySR_NWI:
   # arcpy.AddError("The spatial references of your input data do not match.")
   # arcpy.AddError("Please select input data with exactly matching spatial references.")
   # arcpy.AddError("Then try this tool again.")

# Assuming input data have spatial references defined and matching, proceed...
else:
   try:   
      # Print helpful messages to geoprocessing window
      arcpy.AddMessage("Your input feature class is " + Input_PF)
      arcpy.AddMessage("Your wetlands data feature class is " + Input_NWI)
      arcpy.AddMessage("Your output feature class is " + Output_SBB)
      arcpy.AddMessage("The running script was last edited %s" % ScriptDate)

      # Process:  Create Feature Class (Data Management)
      # Create a feature class to store SBBs
      arcpy.AddMessage("Creating Site Building Blocks feature class for Rule 7 or 9, depending on inputs...")
      arcpy.CreateFeatureclass_management (myWorkspace, Output_SBB_fname, "POLYGON", Input_PF, "", "", Input_PF)
      
      # Process:  Make Feature Layer (Data Management)
      # Create a feature layer of NWI polygons
      arcpy.AddMessage("Making an NWI feature layer...")
      arcpy.MakeFeatureLayer_management (Input_NWI, "NWI_lyr", "", "", "")

      # Loop through the individual Procedural Features
      myProcFeats = arcpy.da.SearchCursor(Input_PF, [Input_SFID]) # Get the set of features
      myIndex = 1 # Set a counter index

      for myPF in myProcFeats: 
      # for each Procedural Feature in the set, do the following...
         try: # Even if one feature fails, script can proceed to next feature

            # Extract the unique Source Feature ID
            myID = myPF[0]

            # Add a progress message
            arcpy.AddMessage("\nWorking on feature " + str(myIndex))
            arcpy.AddMessage("Selecting Procedural Feature where Source Feature ID = " + str(int(myID)) + "...")
            
            # Process:  Select (Analysis)
            # Create a temporary feature class including only the current PF
            myCurrentPF = outScratch + os.sep + "tmpProceduralFeature"
            myWhereClause_PF = Input_SFID + " = '" + myID + "'"
            arcpy.Select_analysis (Input_PF, myCurrentPF, myWhereClause_PF)

            # Process:  Remove Spatial Index (Data Management)
            # Remove the spatial index to avoid potential conflicts when updating feature.
            # This step is necessary because ArcGIS is stupid.
            # This is put in a TRY block b/c not applicable to all file types.
            try:
               arcpy.RemoveSpatialIndex_management(myCurrentPF)
               arcpy.AddMessage("Removing spatial index from Procedural Feature data")
            except:
               pass

            # Process:  Buffer (Analysis)
            # Step 1: Create a minimum buffer around the Procedural Feature
            arcpy.AddMessage("Creating minimum buffer")
            myMinBuffer = outScratch + os.sep + "minBuff"
            arcpy.Buffer_analysis (myCurrentPF, myMinBuffer, minBuff, "", "", "", "")  
            feats2merge = [myMinBuffer]          
               
            # Process:  Buffer (Analysis)
            # Step 2: Create a maximum buffer around the Procedural Feature
            myMaxBuffer = outScratch + os.sep + "maxBuff"
            arcpy.AddMessage("Creating maximum buffer")
            arcpy.Buffer_analysis (myCurrentPF, myMaxBuffer, maxBuff, "", "", "", "")

            # Process:  Remove Spatial Index (Data Management)
            # Remove the spatial index to avoid potential conflicts when updating feature.
            # This step is necessary because ArcGIS is stupid.
            # This is put in a TRY block b/c not applicable to all file types.
            try:
               arcpy.RemoveSpatialIndex_management(myCurrentPF)
               arcpy.AddMessage("Removing spatial index from Procedural Feature data")
            except:
               pass
            
            # Process: Select Layer by Location (Data Management)
            # Step 3: Select NWI features within range
            arcpy.AddMessage("Selecting nearby NWI features")
            arcpy.SelectLayerByLocation_management ("NWI_lyr", "WITHIN_A_DISTANCE", myCurrentPF, searchDist, "NEW_SELECTION", "")
            
            # Determine how many NWI features were selected
            selFeats = int(arcpy.GetCount_management("NWI_lyr")[0])

            # If NWI features are in range, then process
            if selFeats > 0:
               # Process:  Clip (Analysis)
               # Clip the NWI to the maximum buffer
               myClipNWI = outScratch + os.sep + "tmpClipNWI"
               arcpy.AddMessage("Clipping NWI features to maximum buffer...")
               arcpy.Clip_analysis("NWI_lyr", myMaxBuffer, myClipNWI, "")
               
               # Process:  Buffer (Analysis)
               # Step 4: Create a buffer around the NWI feature(s)
               arcpy.AddMessage("Buffering selected NWI features...")
               myNWIBuffer = outScratch + os.sep + "nwiBuff"
               arcpy.Buffer_analysis (myClipNWI, myNWIBuffer, nwiBuff, "", "", "", "") 
               feats2merge = [myMinBuffer, myNWIBuffer]
               
               # Process: Merge (Data Management)
               # Step 5: Merge the minimum buffer with the NWI buffer
               arcpy.AddMessage("Merging buffered PF with buffered NWI feature(s)...")
               myMergedFeats = outScratch + os.sep + "tmpMergedFeatures"
               arcpy.Merge_management(feats2merge, myMergedFeats)
               
               # Process:  Dissolve (Data Management)
               # Dissolve features into a single polygon
               arcpy.AddMessage("Dissolving buffered PF and NWI features into a single feature...")
               myDissFeats = outScratch + os.sep + "tmpDissolvedFeatures"
               arcpy.Dissolve_management (myMergedFeats, myDissFeats, "", "", "", "")   

               # Process:  Clip (Analysis)
               # Step 6: Clip the dissolved feature to the maximum buffer
               arcpy.AddMessage("Clipping dissolved feature to maximum buffer...")  
               myClip = outScratch + os.sep + "tmpClip"
               arcpy.Clip_analysis (myDissFeats, myMaxBuffer, myClip, "")               

               # Use the clipped, combined feature geometry as the final shape
               myFinalShape = arcpy.SearchCursor(myClip).next().Shape 
            else:
               # Use the simple minimum buffer as the final shape
               arcpy.AddMessage("No NWI features found within specified search distance")  
               myFinalShape = arcpy.SearchCursor(myMinBuffer).next().Shape 

            # Update the PF shape
            myCurrentPF_rows = arcpy.UpdateCursor(myCurrentPF, "", "", "Shape", "")
            myPF_row = myCurrentPF_rows.next()
            myPF_row.Shape = myFinalShape
            myCurrentPF_rows.updateRow(myPF_row) 

            # Process:  Remove Spatial Index (Data Management)
            try:
               arcpy.RemoveSpatialIndex_management(myCurrentPF)
               arcpy.AddMessage("Removing spatial index")
            except:
               pass
           
            # Process:  Append
            # Append the final geometry to the SBB feature class.
            arcpy.AddMessage("Appending final shape to SBB feature class...")
            arcpy.Append_management(myCurrentPF, Output_SBB, "NO_TEST", "", "")

            # Add final progress message
            arcpy.AddMessage("Finished processing feature " + str(myIndex))

         except:
            # Add failure message and append failed feature ID to list
            arcpy.AddMessage("\nFailed to fully process feature " + str(myIndex))
            myFailList.append(int(myID))

            # Error handling code swiped from "A Python Primer for ArcGIS"
            tb = sys.exc_info()[2]
            tbinfo = traceback.format_tb(tb)[0]
            pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
            msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

            arcpy.AddWarning(msgs)
            arcpy.AddWarning(pymsg)
            arcpy.AddMessage(arcpy.GetMessages(1))

            # Add status message
            arcpy.AddMessage("\nMoving on to the next feature.  Note that the SBB output will be incomplete.")            

         finally:                     
           # Increment the index by one and clear memory before returning to beginning of the loop
            myIndex += 1 
            try:
               arcpy.Delete_management(outScratch)
            except:
               pass
            if myPF:
               del myPF
            GarbageObjects = gc.collect()

      # Once the script as a whole has succeeded, let the user know if any individual 
      # features failed
      if len(myFailList) == 0:
         arcpy.AddMessage("All features successfully processed")
      else:
         arcpy.AddWarning("Processing failed for the following features: " + str(myFailList))
         arcpy.AddWarning("See the log file " + myFailLog)
         with open(myFailLog, 'wb') as csvfile:
            myCSV = csv.writer(csvfile)
            for value in myFailList:
               myCSV.writerow([value])
            
   # This code block determines what happens if the "try" code block fails
   except:
      # Error handling code swiped from "A Python Primer for ArcGIS"
      tb = sys.exc_info()[2]
      tbinfo = traceback.format_tb(tb)[0]
      pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n "
      msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

      arcpy.AddError(msgs)
      arcpy.AddError(pymsg)
      arcpy.AddMessage(arcpy.GetMessages(1))

   finally:
      arcpy.AddMessage("Done processing Rule 7 or 9 features")











