# ----------------------------------------------------------------------------------------
# CreateStandardWetlandSBB.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2013-01-23
# Last Edit: 2017-09-06
# Creator:  Kirsten R. Hazler
#
# Summary:
#     Creates Site Building Blocks (SBBs) from Rule 5, 6, 7, or 9 Procedural Features (PFs).
#     The procedures are the same for all rules, the only difference being the rule-specific
#     inputs.
#     Carries out the following general procedures:
#     1.  Buffer the PF by 250-m.  This is the minimum buffer.
#     2.  Buffer the PF by 500-m.  This is the maximum buffer.
#     3.  Clip any NWI wetland features to the maximum buffer, then shrinkwrap features.
#     4.  Select clipped NWI features within 15-m of the PF.
#     5.  Buffer the selected NWI feature(s), if applicable, by 100-m.
#     6.  Merge the minimum buffer with the buffered NWI feature(s).
#     7.  Clip the merged feature to the maximum buffer.
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
# ----------------------------------------------------------------------------------------

# Import function libraries and settings
import libConSiteFx
from libConSiteFx import *

def CreateWetlandSBB(in_PF, fld_SFID, selQry, in_NWI, out_SBB, tmpWorkspace = "in_memory", scratchGDB = "in_memory"):
   '''Creates standard wetland SBBs'''
   # Process: Select PFs
   sub_PF = tmpWorkspace + os.sep + 'sub_PF'
   arcpy.Select_analysis (in_PF, sub_PF, selQry)
   
   # Count records and proceed accordingly
   count = countFeatures(sub_PF)
   if count > 0:
      # Declare some additional parameters
      # These can be tweaked as desired
      nwiBuff = "100 METERS"# buffer to be used for NWI features (may or may not equal minBuff)
      minBuff = "250 METERS" # minimum buffer to include in SBB
      maxBuff = "500 METERS" # maximum buffer to include in SBB
      searchDist = "15 METERS" # search distance for inclusion of NWI features

      # Set workspace and some additional variables
      arcpy.env.workspace = scratchGDB
      num, units, newMeas = multiMeasure(searchDist, 0.5)

      # Create an empty list to store IDs of features that fail to get processed
      myFailList = []

      # Set up cursor and counter
      myProcFeats = arcpy.da.SearchCursor(sub_PF, [fld_SFID, "SHAPE@"]) # Get the set of features
      myIndex = 1 # Set a counter index

      # Loop through the individual Procedural Features
      for myPF in myProcFeats:
      # for each Procedural Feature in the set, do the following...
         try: # Even if one feature fails, script can proceed to next feature

            # Extract the unique Source Feature ID and geometry object
            myID = myPF[0]
            myShape = myPF[1]

            # Add a progress message
            printMsg("\nWorking on feature %s, with SFID = %s" %(str(myIndex), myID))

            # Process:  Select (Analysis)
            # Create a temporary feature class including only the current PF
            selQry = fld_SFID + " = '%s'" % myID
            arcpy.Select_analysis (in_PF, "tmpPF", selQry)

            # Step 1: Create a minimum buffer around the Procedural Feature
            printMsg("Creating minimum buffer")
            arcpy.Buffer_analysis ("tmpPF", "myMinBuffer", minBuff)

            # Step 2: Create a maximum buffer around the Procedural Feature
            printMsg("Creating maximum buffer")
            arcpy.Buffer_analysis ("tmpPF", "myMaxBuffer", maxBuff)
            
            # Step 3: Clip the NWI to the maximum buffer, and shrinkwrap
            printMsg("Clipping NWI features to maximum buffer and shrinkwrapping...")
            arcpy.Clip_analysis(in_NWI, "myMaxBuffer", "tmpClipNWI")
            shrinkNWI = scratchGDB + os.sep + "shrinkNWI"
            ShrinkWrap("tmpClipNWI", newMeas, shrinkNWI, "in_memory")

            # Step 4: Select shrinkwrapped NWI features within range
            printMsg("Selecting nearby NWI features")
            arcpy.MakeFeatureLayer_management ("shrinkNWI", "NWI_lyr", "", "", "")
            arcpy.SelectLayerByLocation_management ("NWI_lyr", "WITHIN_A_DISTANCE", "tmpPF", searchDist, "NEW_SELECTION")

            # Determine how many NWI features were selected
            selFeats = int(arcpy.GetCount_management("NWI_lyr")[0])

            # If NWI features are in range, then process
            if selFeats > 0:
               # Step 5: Create a buffer around the NWI feature(s)
               printMsg("Buffering selected NWI features...")
               arcpy.Buffer_analysis ("NWI_lyr", "nwiBuff", nwiBuff)

               # Step 6: Merge the minimum buffer with the NWI buffer
               printMsg("Merging buffered PF with buffered NWI feature(s)...")
               feats2merge = ["myMinBuffer", "nwiBuff"]
               print str(feats2merge)
               arcpy.Merge_management(feats2merge, "tmpMerged")

               # Dissolve features into a single polygon
               printMsg("Dissolving buffered PF and NWI features into a single feature...")
               arcpy.Dissolve_management ("tmpMerged", "tmpDissolved", "", "", "", "")

               # Step 7: Clip the dissolved feature to the maximum buffer
               printMsg("Clipping dissolved feature to maximum buffer...")
               arcpy.Clip_analysis ("tmpDissolved", "myMaxBuffer", "tmpClip", "")

               # Use the clipped, combined feature geometry as the final shape
               myFinalShape = arcpy.SearchCursor("tmpClip").next().Shape
            else:
               # Use the simple minimum buffer as the final shape
               printMsg("No NWI features found within specified search distance")
               myFinalShape = arcpy.SearchCursor("myMinBuffer").next().Shape

            # Update the PF shape
            myCurrentPF_rows = arcpy.UpdateCursor("tmpPF", "", "", "Shape", "")
            myPF_row = myCurrentPF_rows.next()
            myPF_row.Shape = myFinalShape
            myCurrentPF_rows.updateRow(myPF_row)

            # Process:  Append
            # Append the final geometry to the SBB feature class.
            printMsg("Appending final shape to SBB feature class...")
            arcpy.Append_management("tmpPF", out_SBB, "NO_TEST", "", "")

            # Add final progress message
            printMsg("Finished processing feature " + str(myIndex))
            
         except:
            # Add failure message and append failed feature ID to list
            printMsg("\nFailed to fully process feature " + str(myIndex))
            myFailList.append(int(myID))

            # Error handling code swiped from "A Python Primer for ArcGIS"
            tb = sys.exc_info()[2]
            tbinfo = traceback.format_tb(tb)[0]
            pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
            msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

            printWrng(msgs)
            printWrng(pymsg)
            printMsg(arcpy.GetMessages(1))

            # Add status message
            printMsg("\nMoving on to the next feature.  Note that the SBB output will be incomplete.")

         finally:
           # Increment the index by one
            myIndex += 1
            
            # Release cursor row
            del myPF

      # Once the script as a whole has succeeded, let the user know if any individual
      # features failed
      if len(myFailList) == 0:
         printMsg("All features successfully processed")
      else:
         printWrng("Processing failed for the following features: " + str(myFailList))
   else:
      printMsg('There are no PFs with this rule; passing...')