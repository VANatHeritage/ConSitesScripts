# ----------------------------------------------------------------------------------------
# CreateSBBs.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016-01-29
# Last Edit: 2018-03-09
# Creator:  Kirsten R. Hazler
#
# Summary:
# Collection of functions to create rule-specific Site Building Blocks (SBBs) from Procedural Features (PFs), and to expand SBBs by adding core habitat area.
# ----------------------------------------------------------------------------------------

# Import function libraries and settings
import libConSiteFx
from libConSiteFx import *

# Define various functions
def warnings(rule):
   '''Generates warning messages specific to SBB rules'''
   warnMsgs = arcpy.GetMessages(1)
   if warnMsgs:
      printWrng('Finished processing Rule %s, but there were some problems.' % str(rule))
      printWrng(warnMsgs)
   else:
      printMsg('Rule %s SBBs completed' % str(rule))

def PrepProcFeats(in_PF, fld_Rule, fld_Buff, tmpWorkspace):
   '''Makes a copy of the Procedural Features, preps them for SBB processing'''
   try:
      # Process: Copy Features
      tmp_PF = tmpWorkspace + os.sep + 'tmp_PF'
      arcpy.CopyFeatures_management(in_PF, tmp_PF)

      # Process: Add Field (fltBuffer)
      arcpy.AddField_management(tmp_PF, "fltBuffer", "FLOAT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

      # Process: Add Field (intRule)
      arcpy.AddField_management(tmp_PF, "intRule", "SHORT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

      # Process: Calculate Field (intRule)
      expression1 = "string2int(!" + fld_Rule + "!)"
      codeblock1 = """def string2int(RuleString):
         try:
            RuleInteger = int(RuleString)
         except:
            if RuleString == 'AHZ':
               RuleInteger = -1
            else:
               RuleInteger = 0
         return RuleInteger"""
      arcpy.CalculateField_management(tmp_PF, "intRule", expression1, "PYTHON", codeblock1)

      # Process: Calculate Field (fltBuffer)
      # Note that code here will have to change if changes are made to buffer standards
      expression2 = "string2float(!intRule!, !" + fld_Buff + "!)"
      codeblock2 = """def string2float(RuleInteger, BufferString):
         if RuleInteger == 1:
            BufferFloat = 150
         elif RuleInteger in (2,3,4,8,14):
            BufferFloat = 250
         elif RuleInteger in (11,12):
            BufferFloat = 450
         else:
            try:
               BufferFloat = float(BufferString)
            except:
               BufferFloat = 0
         return BufferFloat"""
      arcpy.CalculateField_management(tmp_PF, "fltBuffer", expression2, "PYTHON", codeblock2)

      return tmp_PF
   except:
      arcpy.AddError('Unable to complete intitial pre-processing necessary for all further steps.')
      tback()
      quit()

def CreateStandardSBB(in_PF, out_SBB, scratchGDB = "in_memory"):
   '''Creates standard buffer SBBs for specified subset of PFs'''
   try:
      # Process: Select (Defined Buffer Rules)
      selQry = "(intRule in (-1,1,2,3,4,8,10,11,12,13,14)) AND (fltBuffer <> 0)"
      arcpy.MakeFeatureLayer_management(in_PF, "tmpLyr", selQry)

      # Count records and proceed accordingly
      count = countFeatures("tmpLyr")
      if count > 0:
         # Process: Buffer
         tmpSBB = scratchGDB + os.sep + 'tmpSBB'
         arcpy.Buffer_analysis("tmpLyr", tmpSBB, "fltBuffer", "FULL", "ROUND", "NONE", "", "PLANAR")
         # Append to output and cleanup
         arcpy.Append_management (tmpSBB, out_SBB, "NO_TEST")
         printMsg('Simple buffer SBBs completed')
         garbagePickup([tmpSBB])
      else:
         printMsg('There are no PFs using the simple buffer rules')
   except:
      printWrng('Unable to process the simple buffer features')
      tback()

def CreateNoBuffSBB(in_PF, out_SBB):
   '''Creates SBBs that are simple copies of PFs for specified subset'''
   try:
      # Process: Select (No-Buffer Rules)
      selQry = "(intRule in (-1,13,15) AND (fltBuffer = 0))"
      arcpy.MakeFeatureLayer_management(in_PF, "tmpLyr", selQry)

      # Count records and proceed accordingly
      count = countFeatures("tmpLyr")
      if count > 0:
         # Append to output and cleanup
         arcpy.Append_management ("tmpLyr", out_SBB, "NO_TEST")
         printMsg('No-buffer SBBs completed')
      else:
         printMsg('There are no PFs using the no-buffer rules')
   except:
      printWrng('Unable to process the no-buffer features.')
      tback()

def CreateWetlandSBB(in_PF, fld_SFID, selQry, in_NWI, out_SBB, tmpWorkspace = "in_memory", scratchGDB = "in_memory"):
   '''Creates standard wetland SBBs from Rule 5, 6, 7, or 9 Procedural Features (PFs). The procedures are the same for all rules, the only difference being the rule-specific inputs.
   
#     Carries out the following general procedures:
#     1.  Buffer the PF by 250-m.  This is the minimum buffer.
#     2.  Buffer the PF by 500-m.  This is the maximum buffer.
#     3.  Clip any NWI wetland features to the maximum buffer, then shrinkwrap features.
#     4.  Select clipped NWI features within 15-m of the PF.
#     5.  Buffer the selected NWI feature(s), if applicable, by 100-m.
#     6.  Merge the minimum buffer with the buffered NWI feature(s).
#     7.  Clip the merged feature to the maximum buffer.'''

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

      # Loop through the individual Procedural Features
      myIndex = 1 # Set a counter index
      with arcpy.da.SearchCursor(sub_PF, [fld_SFID, "SHAPE@"]) as myProcFeats:
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
               ShrinkWrap("tmpClipNWI", newMeas, shrinkNWI)

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
      
def CreateSBBs(in_PF, fld_SFID, fld_Rule, fld_Buff, in_nwi5, in_nwi67, in_nwi9, out_SBB, scratchGDB = "in_memory"):
   '''Creates SBBs for all input PFs, subsetting and applying rules as needed.
   Usage Notes:  
   - This function does not test to determine if all of the input Procedural Features should be subject to a particular rule. The user must ensure that this is so.
   - It is recommended that the NWI feature class be stored on your local drive rather than a network drive, to optimize processing speed.
   - For the CreateWetlandSBBs function to work properly, the input NWI data must contain a subset of only those features applicable to the particular rule.  Adjacent NWI features should have boundaries dissolved.
   - For best results, it is recommended that you close all other programs before running this tool, since it relies on having ample memory for processing.'''

   tStart = datetime.now()
   
   # Print helpful message to geoprocessing window
   getScratchMsg(scratchGDB)

   # Set up some variables
   tmpWorkspace = createTmpWorkspace()
   sr = arcpy.Describe(in_PF).spatialReference
   printMsg("Additional critical temporary products will be stored here: %s" % tmpWorkspace)
   sub_PF = scratchGDB + os.sep + 'sub_PF' # for storing PF subsets

   # Set up trashList for later garbage collection
   trashList = [sub_PF]

   # Prepare input procedural featuers
   printMsg('Prepping input procedural features')
   tmp_PF = PrepProcFeats(in_PF, fld_Rule, fld_Buff, tmpWorkspace)
   trashList.append(tmp_PF)

   printMsg('Beginning SBB creation...')

   # Create empty feature class to store SBBs
   printMsg('Creating empty feature class for output')
   if arcpy.Exists(out_SBB):
      arcpy.Delete_management(out_SBB)
   outDir = os.path.dirname(out_SBB)
   outName = os.path.basename(out_SBB)
   printMsg('Creating %s in %s' %(outName, outDir))
   arcpy.CreateFeatureclass_management (outDir, outName, "POLYGON", tmp_PF, '', '', sr)

   # Standard buffer SBBs
   printMsg('Processing the simple defined-buffer features...')
   CreateStandardSBB(tmp_PF, out_SBB)

   # No buffer SBBs
   printMsg('Processing the no-buffer features')
   CreateNoBuffSBB(tmp_PF, out_SBB)

   # Rule 5 SBBs
   printMsg('Processing the Rule 5 features')
   selQry = "intRule = 5"
   in_NWI = in_nwi5
   try:
      CreateWetlandSBB(tmp_PF, fld_SFID, selQry, in_NWI, out_SBB, tmpWorkspace, "in_memory")
      warnings(5)
   except:
      printWrng('Unable to process Rule 5 features')
      tback()

   # Rule 6 SBBs
   printMsg('Processing the Rule 6 features')
   selQry = "intRule = 6"
   in_NWI = in_nwi67
   try:
      CreateWetlandSBB(tmp_PF, fld_SFID, selQry, in_NWI, out_SBB, tmpWorkspace, "in_memory")
      warnings(6)
   except:
      printWrng('Unable to process Rule 6 features')
      tback()

   # Rule 7 SBBs
   printMsg('Processing the Rule 7 features')
   selQry = "intRule = 7"
   in_NWI = in_nwi67
   try:
      CreateWetlandSBB(tmp_PF, fld_SFID, selQry, in_NWI, out_SBB, tmpWorkspace, "in_memory")
      warnings(7)
   except:
      printWrng('Unable to process Rule 7 features')
      tback()

   # Rule 9 SBBs
   printMsg('Processing the Rule 9 features')
   selQry = "intRule = 9"
   in_NWI = in_nwi9
   try:
      CreateWetlandSBB(tmp_PF, fld_SFID, selQry, in_NWI, out_SBB, tmpWorkspace, "in_memory")
      warnings(9)
   except:
      printWrng('Unable to process Rule 9 features')
      tback()

   printMsg('SBB processing complete')
   
   tFinish = datetime.now()
   deltaString = GetElapsedTime (tStart, tFinish)
   printMsg("Processing complete. Total elapsed time: %s" %deltaString)
   
   return out_SBB

def ExpandSBBs(in_Cores, in_SBB, in_PF, joinFld, out_SBB, scratchGDB = "in_memory"):
   '''Expands SBBs by adding core area.'''
   
   tStart = datetime.now()
   
   # Declare path/name of output data and workspace
   drive, path = os.path.splitdrive(out_SBB) 
   path, filename = os.path.split(path)
   myWorkspace = drive + path
   
   # Print helpful message to geoprocessing window
   getScratchMsg(scratchGDB)
   
   # Set up output locations for subsets of SBBs and PFs to process
   SBB_sub = scratchGDB + os.sep + 'SBB_sub'
   PF_sub = scratchGDB + os.sep + 'PF_sub'
   
   # Subset PFs and SBBs
   printMsg('Using the current SBB selection and making copies of the SBBs and PFs...')
   SubsetSBBandPF(in_SBB, in_PF, "PF", joinFld, SBB_sub, PF_sub)
   
   # Process: Select Layer By Location (Get Cores intersecting PFs)
   printMsg('Selecting cores that intersect procedural features')
   arcpy.MakeFeatureLayer_management(in_Cores, "Cores_lyr")
   arcpy.MakeFeatureLayer_management(PF_sub, "PF_lyr") 
   arcpy.SelectLayerByLocation_management("Cores_lyr", "INTERSECT", "PF_lyr", "", "NEW_SELECTION", "NOT_INVERT")

   # Process:  Copy the selected Cores features to scratch feature class
   selCores = scratchGDB + os.sep + 'selCores'
   arcpy.CopyFeatures_management ("Cores_lyr", selCores) 

   # Process:  Repair Geometry and get feature count
   arcpy.RepairGeometry_management (selCores, "DELETE_NULL")
   numCores = countFeatures(selCores)
   printMsg('There are %s cores to process.' %str(numCores))
   
   # Create Feature Class to store expanded SBBs
   printMsg("Creating feature class to store buffered SBBs...")
   arcpy.CreateFeatureclass_management (scratchGDB, 'sbbExpand', "POLYGON", SBB_sub, "", "", SBB_sub) 
   sbbExpand = scratchGDB + os.sep + 'sbbExpand'
   
   # Loop through Cores and add core buffers to SBBs
   counter = 1
   with  arcpy.da.SearchCursor(selCores, ["SHAPE@", "CoreID"]) as myCores:
      for core in myCores:
         # Add extra buffer for SBBs of PFs located in cores. Extra buffer needs to be snipped to core in question.
         coreShp = core[0]
         coreID = core[1]
         printMsg('Working on Core ID %s' % str(coreID))
         tmpSBB = scratchGDB + os.sep + 'sbb'
         AddCoreAreaToSBBs(PF_sub, SBB_sub, joinFld, coreShp, tmpSBB, "1000 METERS", scratchGDB)
         
         # Append expanded SBB features to output
         arcpy.Append_management (tmpSBB, sbbExpand, "NO_TEST")
         
         del core
   
   # Merge, then dissolve original SBBs with buffered SBBs to get final shapes
   printMsg('Merging all SBBs...')
   sbbAll = scratchGDB + os.sep + "sbbAll"
   #sbbFinal = myWorkspace + os.sep + "sbbFinal"
   arcpy.Merge_management ([SBB_sub, sbbExpand], sbbAll)
   arcpy.Dissolve_management (sbbAll, out_SBB, [joinFld, "intRule"], "")
   #arcpy.MakeFeatureLayer_management(sbbFinal, "SBB_lyr") 
   
   printMsg('SBB processing complete')
   
   tFinish = datetime.now()
   deltaString = GetElapsedTime (tStart, tFinish)
   printMsg("Processing complete. Total elapsed time: %s" %deltaString)
   
   return out_SBB

def ParseSBBs(in_SBB, out_terrSBB, out_ahzSBB):
   '''Splits input SBBs into two feature classes, one for standard terrestrial SBBs and one for AHZ SBBs.'''
   terrQry = "intRule <> -1" 
   ahzQry = "intRule = -1"
   arcpy.Select_analysis (in_SBB, out_terrSBB, terrQry)
   arcpy.Select_analysis (in_SBB, out_ahzSBB, ahzQry)
   
   sbbTuple = (out_terrSBB, out_ahzSBB)
   return sbbTuple

# Use the main function below to run function(s) directly from Python IDE or command line with hard-coded variables
def main():
   # Set up your variables here
   in_PF = r'C:\Users\xch43889\Documents\Working\ConSites\Biotics.gdb\ProcFeats_20180131_173111'
   out_SBB = r'C:\Users\xch43889\Documents\Working\ConSites\Biotics.gdb\SBB_20180131'
   joinFld = 'SFID' # probably can leave this as is
   in_Core = r'C:\Testing\ConSiteTests20180118.gdb\core03'
   # out_SBB = r'C:\Testing\ConSiteTests20180118.gdb\sbb03_out'
   BuffDist = "1000 METERS"
   #scratchGDB = r'C:\Testing\scratch20180118.gdb'
   in_nwi5 = r'H:\Backups\DCR_Work_DellD\SBBs_ConSites\Automation\AutomationData_Working\ConSite_Tools_Inputs.gdb\VA_Wetlands_Rule5'
   in_nwi67 = r'H:\Backups\DCR_Work_DellD\SBBs_ConSites\Automation\AutomationData_Working\ConSite_Tools_Inputs.gdb\VA_Wetlands_Rule67'
   in_nwi9 = r'H:\Backups\DCR_Work_DellD\SBBs_ConSites\Automation\AutomationData_Working\ConSite_Tools_Inputs.gdb\VA_Wetlands_Rule9'

   # End of user input
   
   CreateSBBs(in_PF, "SFID", "RULE", "BUFFER", in_nwi5, in_nwi67, in_nwi9, out_SBB)
   #AddCoreAreaToSBBs(in_PF, in_SBB, joinFld, in_Core, out_SBB, BuffDist, scratchGDB)

if __name__ == '__main__':
   main()