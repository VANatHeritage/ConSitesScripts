# ----------------------------------------------------------------------------------------
# CreateTCS.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016-02-25 (Adapted from suite of ModelBuilder models)
# Last Edit: 2020-06-02
# Creator:  Kirsten R. Hazler

# Summary:
# Suite of functions to create standard Terrestrial Conservation Sites (TCS). Also allows construction of Anthropogenic Habitat Zones (AHZs).
# ----------------------------------------------------------------------------------------

# Import function libraries and settings
import Helper
from Helper import *
# import libConSiteFx
# from libConSiteFx import *

def GetEraseFeats (inFeats, selQry, elimDist, outEraseFeats, elimFeats = "", scratchGDB = "in_memory"):
   ''' For ConSite creation: creates exclusion features from input hydro or transportation surface features'''
   # Process: Make Feature Layer (subset of selected features)
   arcpy.MakeFeatureLayer_management(inFeats, "Selected_lyr", selQry)

   # If it's a string, parse elimination distance and get the negative
   if type(elimDist) == str:
      origDist, units, meas = multiMeasure(elimDist, 1)
      negDist, units, negMeas = multiMeasure(elimDist, -1)
   else:
      origDist = elimDist
      meas = elimDist
      negDist = -1*origDist
      negMeas = negDist
   
   # Process: Eliminate narrow features (or portions thereof)
   CoalEraseFeats = scratchGDB + os.sep + 'CoalEraseFeats'
   Coalesce("Selected_lyr", negDist, CoalEraseFeats, scratchGDB)
   
   # Process: Bump features back out to avoid weird pinched shapes
   BumpEraseFeats = scratchGDB + os.sep + 'BumpEraseFeats'
   Coalesce(CoalEraseFeats, elimDist, BumpEraseFeats, scratchGDB)

   if elimFeats == "":
      CleanFeatures(BumpEraseFeats, outEraseFeats)
   else:
      CleanErase(BumpEraseFeats, elimFeats, outEraseFeats)
   
   # Cleanup
   if scratchGDB == "in_memory":
      trashlist = [CoalEraseFeats]
      garbagePickup(trashlist)
   
   return outEraseFeats

def CullEraseFeats (inEraseFeats, in_Feats, fld_SFID, PerCov, outEraseFeats, scratchGDB = "in_memory"):
   '''For ConSite creation: Culls exclusion features containing a significant percentage of any input feature's (PF or SBB) area'''
   # Process:  Add Field (Erase ID) and Calculate
   arcpy.AddField_management (inEraseFeats, "eFID", "LONG")
   arcpy.CalculateField_management (inEraseFeats, "eFID", "!OBJECTID!", "PYTHON")
   
   # Process: Tabulate Intersection
   # This tabulates the percentage of each input feature that is contained within each erase feature
   TabIntersect = scratchGDB + os.sep + os.path.basename(inEraseFeats) + "_TabInter"
   arcpy.TabulateIntersection_analysis(in_Feats, fld_SFID, inEraseFeats, TabIntersect, "eFID", "", "", "HECTARES")
   
   # Process: Summary Statistics
   # This tabulates the maximum percentage of ANY input feature within each erase feature
   TabSum = scratchGDB + os.sep + os.path.basename(inEraseFeats) + "_TabSum"
   arcpy.Statistics_analysis(TabIntersect, TabSum, "PERCENTAGE SUM", fld_SFID)
   
   # Process: Join Field
   # This joins the summed percentage value back to the original input features
   try:
      arcpy.DeleteField_management (in_Feats, "SUM_PERCENTAGE")
   except:
      pass
   arcpy.JoinField_management(in_Feats, fld_SFID, TabSum, fld_SFID, "SUM_PERCENTAGE")
   
   # Process: Select features containing a large enough percentage of erase features
   WhereClause = "SUM_PERCENTAGE >= %s" % PerCov
   selInFeats = scratchGDB + os.sep + 'selInFeats'
   arcpy.Select_analysis(in_Feats, selInFeats, WhereClause)
   
   # Process:  Clean Erase (Use selected input features to chop out areas of exclusion features)
   CleanErase(inEraseFeats, selInFeats, outEraseFeats, scratchGDB)
   
   if scratchGDB == "in_memory":
      # Cleanup
      trashlist = [TabIntersect, TabSum]
      garbagePickup(trashlist)
   
   return outEraseFeats

def CullFrags (inFrags, in_PF, searchDist, outFrags):
   '''For ConSite creation: Culls SBB or ConSite fragments farther than specified search distance from 
   Procedural Features'''
   
   # Process: Near
   arcpy.Near_analysis(inFrags, in_PF, searchDist, "NO_LOCATION", "NO_ANGLE", "PLANAR")

   # Process: Make Feature Layer
   WhereClause = '"NEAR_FID" <> -1'
   arcpy.MakeFeatureLayer_management(inFrags, "Frags_lyr", WhereClause)

   # Process: Clean Features
   CleanFeatures("Frags_lyr", outFrags)
   
   return outFrags

def ExpandSBBselection(inSBB, inPF, joinFld, inConSites, SearchDist, outSBB, outPF):
   '''Given an initial selection of Site Building Blocks (SBB) features, selects additional SBB features in the vicinity that should be included in any Conservation Site update. Also selects the Procedural Features (PF) corresponding to selected SBBs. Outputs the selected SBBs and PFs to new feature classes.'''
   # If applicable, clear any selections on the PFs and ConSites inputs
   typePF = (arcpy.Describe(inPF)).dataType
   typeCS = (arcpy.Describe(inConSites)).dataType
   if typePF == 'FeatureLayer':
      arcpy.SelectLayerByAttribute_management (inPF, "CLEAR_SELECTION")
   if typeCS == 'FeatureLayer':
      arcpy.SelectLayerByAttribute_management (inConSites, "CLEAR_SELECTION")
      
   # Make Feature Layers from PFs and ConSites
   arcpy.MakeFeatureLayer_management(inPF, "PF_lyr")   
   arcpy.MakeFeatureLayer_management(inConSites, "Sites_lyr")
      
   # # Process: Select subset of terrestrial ConSites
   # # WhereClause = "TYPE = 'Conservation Site'" 
   # arcpy.SelectLayerByAttribute_management ("Sites_lyr", "NEW_SELECTION", '')

   # Initialize row count variables
   initRowCnt = 0
   finRowCnt = 1

   while initRowCnt < finRowCnt:
      # Keep adding to the SBB selection as long as the counts of selected records keep changing
      # Get count of records in initial SBB selection
      initRowCnt = int(arcpy.GetCount_management(inSBB).getOutput(0))
      
      # Select SBBs within distance of current selection
      arcpy.SelectLayerByLocation_management(inSBB, "WITHIN_A_DISTANCE", inSBB, SearchDist, "ADD_TO_SELECTION", "NOT_INVERT")
      
      # Select ConSites intersecting current SBB selection
      arcpy.SelectLayerByLocation_management("Sites_lyr", "INTERSECT", inSBB, "", "NEW_SELECTION", "NOT_INVERT")
      
      # Select SBBs within current selection of ConSites
      arcpy.SelectLayerByLocation_management(inSBB, "INTERSECT", "Sites_lyr", "", "ADD_TO_SELECTION", "NOT_INVERT")
      
      # Make final selection
      arcpy.SelectLayerByLocation_management(inSBB, "WITHIN_A_DISTANCE", inSBB, SearchDist, "ADD_TO_SELECTION", "NOT_INVERT")
      
      # Get count of records in final SBB selection
      finRowCnt = int(arcpy.GetCount_management(inSBB).getOutput(0))
      
   # Save subset of SBBs and corresponding PFs to output feature classes
   SubsetSBBandPF(inSBB, inPF, "PF", joinFld, outSBB, outPF)
   
   featTuple = (outSBB, outPF)
   return featTuple
   
def SubsetSBBandPF(inSBB, inPF, selOption, joinFld, outSBB, outPF):
   '''Given input Site Building Blocks (SBB) features, selects the corresponding Procedural Features (PF). Or vice versa, depending on SelOption parameter.  Outputs the selected SBBs and PFs to new feature classes.'''
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
      printErr('Invalid selection option')
     
   # If applicable, clear any selections on the Selectee input
   typeSelectee = (arcpy.Describe(inSelectee)).dataType
   if typeSelectee == 'FeatureLayer':
      arcpy.SelectLayerByAttribute_management (inSelectee, "CLEAR_SELECTION")
      
   # Copy the Selector features to the output feature class
   arcpy.CopyFeatures_management (inSelector, outSelector) 

   # Make Feature Layer from Selectee features
   arcpy.MakeFeatureLayer_management(inSelectee, "Selectee_lyr") 

   # Get the Selectees associated with the Selectors, keeping only common records
   arcpy.AddJoin_management ("Selectee_lyr", joinFld, outSelector, joinFld, "KEEP_COMMON")

   # Select all Selectees that were joined
   arcpy.SelectLayerByAttribute_management ("Selectee_lyr", "NEW_SELECTION")

   # Remove the join
   arcpy.RemoveJoin_management ("Selectee_lyr")

   # Copy the selected Selectee features to the output feature class
   arcpy.CopyFeatures_management ("Selectee_lyr", outSelectee)
   
   featTuple = (outPF, outSBB)
   return featTuple

def AddCoreAreaToSBBs(in_PF, in_SBB, joinFld, in_Core, out_SBB, BuffDist = "1000 METERS", scratchGDB = "in_memory"):
   '''Adds core area to SBBs of PFs intersecting that core. This function should only be used with a single Core feature; i.e., either embed it within a loop, or use an input Cores layer that contains only a single core. Otherwise it will not behave as needed.
   in_PF: layer or feature class representing Procedural Features
   in_SBB: layer or feature class representing Site Building Blocks
   joinFld: unique ID field relating PFs to SBBs
   in_Core: layer or feature class representing habitat Cores
   BuffDist: distance used to add buffer area to SBBs
   scratchGDB: geodatabase to store intermediate products'''
   
   # Make Feature Layer from PFs
   where_clause = "RULE NOT IN ('AHZ', '1')"
   arcpy.MakeFeatureLayer_management(in_PF, "PF_CoreSub", where_clause)
   
   # Get PFs centered in the core
   printMsg('Selecting PFs intersecting the core...')
   arcpy.SelectLayerByLocation_management("PF_CoreSub", "INTERSECT", in_Core, "", "NEW_SELECTION", "NOT_INVERT")
   
   # Get SBBs associated with selected PFs
   printMsg('Copying selected PFs and their associated SBBs...')
   sbbSub = scratchGDB + os.sep + 'sbb'
   pfSub = scratchGDB + os.sep + 'pf'
   SubsetSBBandPF(in_SBB, "PF_CoreSub", "SBB", joinFld, sbbSub, pfSub)
   
   # Buffer SBBs 
   printMsg("Buffering SBBs...")
   sbbBuff = scratchGDB + os.sep + "sbbBuff"
   arcpy.Buffer_analysis(sbbSub, sbbBuff, BuffDist, "FULL", "ROUND", "NONE", "", "PLANAR")
   
   # Clip buffers to core
   printMsg("Clipping buffered SBBs to core...")
   clpBuff = scratchGDB + os.sep + "clpBuff"
   CleanClip(sbbBuff, in_Core, clpBuff, scratchGDB)
   
   # Remove any SBB fragments not containing a PF
   printMsg('Culling SBB fragments...')
   sbbRtn = scratchGDB + os.sep + 'sbbRtn'
   CullFrags(clpBuff, pfSub, "0 METERS", sbbRtn)
   
   # Merge, then dissolve to get final shapes
   printMsg('Dissolving original SBBs with buffered SBBs to get final shapes...')
   sbbMerge = scratchGDB + os.sep + "sbbMerge"
   arcpy.Merge_management ([sbbSub, sbbRtn], sbbMerge)
   arcpy.Dissolve_management (sbbMerge, out_SBB, [joinFld, "intRule"], "")
   
   printMsg('Done.')
   return out_SBB

def ChopSBBs(in_PF, in_SBB, in_EraseFeats, out_Clusters, out_subErase, dilDist = "5 METERS", scratchGDB = "in_memory"):
   '''Uses Erase Features to chop out sections of SBBs. Stitches SBB fragments back together only if within twice the dilDist of each other. Subsequently uses output to erase EraseFeats.'''

   # Use in_EraseFeats to chop out sections of SBB
   # Use regular Erase, not Clean Erase; multipart is good output at this point
   printMsg('Chopping SBBs...')
   firstChop = scratchGDB + os.sep + 'firstChop'
   arcpy.Erase_analysis (in_SBB, in_EraseFeats, firstChop)

   # Eliminate parts comprising less than 5% of total SBB size
   printMsg('Eliminating insignificant parts of SBBs...')
   rtnParts = scratchGDB + os.sep + 'rtnParts'
   arcpy.EliminatePolygonPart_management (firstChop, rtnParts, 'PERCENT', '', 5, 'ANY')
   
   # Shrinkwrap to fill in gaps
   printMsg('Clustering SBB fragments...')
   initClusters = scratchGDB + os.sep + 'initClusters'
   ShrinkWrap(rtnParts, dilDist, initClusters, smthMulti = 2)
   
   # Remove any fragments without procedural features
   printMsg('Culling SBB fragments...')
   CullFrags(initClusters, in_PF, 0, out_Clusters)
   
   # Use SBB clusters to chop out sections of Erase Features
   printMsg('Eliminating irrelevant Erase Features')
   CleanErase(in_EraseFeats, out_Clusters, out_subErase)
   
   outTuple = (out_Clusters, out_subErase)
   return outTuple

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

def CreateConSites(in_SBB, ysn_Expand, in_PF, joinFld, in_ConSites, out_ConSites, site_Type, in_Hydro, in_TranSurf = None, in_Exclude = None, scratchGDB = "in_memory"):
   '''Creates Conservation Sites from the specified inputs:
   - in_SBB: feature class representing Site Building Blocks
   - ysn_Expand: ["true"/"false"] - determines whether to expand the selection of SBBs to include more in the vicinity
   - in_PF: feature class representing Procedural Features
   - joinFld: name of the field containing the unique ID linking SBBs to PFs. Field name is must be the same for both.
   - in_ConSites: feature class representing current Conservation Sites (or, a template feature class)
   - out_ConSites: the output feature class representing updated Conservation Sites
   - site_Type: type of conservation site (TERRESTRIAL|AHZ)
   - in_Hydro: feature class representing water bodies
   - in_TranSurf: feature class(es) representing transportation surfaces (i.e., road and rail) [If multiple, this is a string with items separated by ';']
   - in_Exclude: feature class representing areas to definitely exclude from sites
   - scratchGDB: geodatabase to contain intermediate/scratch products. Setting this to "in_memory" can result in HUGE savings in processing time, but there's a chance you might run out of memory and cause a crash.
   '''
   
   # Get timestamp
   tStart = datetime.now()
   
   # Specify a bunch of parameters
   selDist = "1000 METERS" # Distance used to expand the SBB selection, if this option is selected. Also used to add extra buffer to SBBs.
   dilDist = "250 METERS" # Distance used to coalesce SBBs into ProtoSites (precursors to final automated CS boundaries). Features within twice this distance of each other will be merged into one.
   hydroPerCov = 100 # The minimum percent of any SBB feature that must be covered by water, for those features to be eliminated from the set of features which are used to erase portions of the site. Set to 101 if you don't want features to ever be purged.
   hydroQry = "Hydro = 1" # Expression used to select appropriate hydro features to create erase features
   hydroElimDist = "10 METERS" # Distance used to eliminate insignificant water features from the set of erasing features. Portions of water bodies less than double this width will not be used to split or erase portions of sites.
   transPerCov = 101 #The minimum percent any SBB that must be covered by transportation surfaces, for those surfaces to be eliminated from the set of features which are used to erase portions of the site. Set to 101 if you don't want features to ever be purged.
   transQry = "NH_IGNORE = 0 OR NH_IGNORE IS NULL" ### Substituted old query with new query, allowing user to specify segments to ignore. Old query was: "DCR_ROW_TYPE = 'IS' OR DCR_ROW_TYPE = 'PR'" # Expression used to select appropriate transportation surface features to create erase features
   buffDist = "200 METERS" # Distance used to buffer ProtoSites to establish the area for further processing.
   searchDist = "0 METERS" # Distance from PFs used to determine whether to cull SBB and ConSite fragments after ProtoSites have been split.
   coalDist = "25 METERS" # Distance for coalescing split sites back together. Sites with less than double this width between each other will merge.
   
   if not scratchGDB:
      scratchGDB = "in_memory"
      # Use "in_memory" as default, but if script is failing, use scratchGDB on disk. Also use scratchGDB on disk if you are trying to run this in two or more instances of Arc or Python, otherwise you can run into catastrophic memory conflicts.
      
   if scratchGDB != "in_memory":
      printMsg("Scratch outputs will be stored here: %s" % scratchGDB)
      scratchParm = scratchGDB
   else:
      printMsg("Scratch products are being stored in memory and will not persist. If processing fails inexplicably, or if you want to be able to inspect scratch products, try running this with a specified scratchGDB on disk.")
      scratchParm = "in_memory"

   # Set overwrite option so that existing data may be overwritten
   arcpy.env.overwriteOutput = True 

   # Declare path/name of output data and workspace
   drive, path = os.path.splitdrive(out_ConSites) 
   path, filename = os.path.split(path)
   myWorkspace = drive + path
   Output_CS_fname = filename
   
   # Parse out transportation datasets
   if site_Type == 'TERRESTRIAL':
      Trans = in_TranSurf.split(';')
   
   # If applicable, clear any selections on non-SBB inputs
   for fc in [in_PF, in_Hydro]:
      clearSelection(fc)

   if site_Type == 'TERRESTRIAL':
      printMsg("Site type is %s" % site_Type)
      clearSelection(in_Exclude)
      for fc in Trans:
         clearSelection(fc)
   
   ### Start data prep
   tStartPrep = datetime.now()
   
   # Merge the transportation layers, if necessary
   if site_Type == 'TERRESTRIAL':
      if len(Trans) == 1:
         Trans = Trans[0]
      else:
         printMsg('Merging transportation surfaces')
         # Must absolutely write this to disk (myWorkspace) not to memory (scratchGDB), or for some reason there is no OBJECTID field and as a result, code for CullEraseFeats will fail.
         mergeTrans = myWorkspace + os.sep + 'mergeTrans'
         arcpy.Merge_management(Trans, mergeTrans)
         Trans = mergeTrans

   # Get relevant hydro features
   openWater = scratchGDB + os.sep + 'openWater'
   arcpy.Select_analysis (in_Hydro, openWater, hydroQry)

   # Set up output locations for subsets of SBBs and PFs to process
   SBB_sub = scratchGDB + os.sep + 'SBB_sub'
   PF_sub = scratchGDB + os.sep + 'PF_sub'
   
   if ysn_Expand == "true":
      # Expand SBB selection
      printMsg('Expanding the current SBB selection and making copies of the SBBs and PFs...')
      ExpandSBBselection(in_SBB, in_PF, joinFld, in_ConSites, selDist, SBB_sub, PF_sub)
   else:
      # Subset PFs and SBBs
      printMsg('Using the current SBB selection and making copies of the SBBs and PFs...')
      SubsetSBBandPF(in_SBB, in_PF, "PF", joinFld, SBB_sub, PF_sub)

   # Make Feature Layers
   arcpy.MakeFeatureLayer_management(PF_sub, "PF_lyr") 
   arcpy.MakeFeatureLayer_management(SBB_sub, "SBB_lyr") 
   arcpy.MakeFeatureLayer_management(openWater, "Hydro_lyr")
   sub_Hydro = "Hydro_lyr"
   
   # Process:  Create Feature Classes (to store ConSites)
   printMsg("Creating ConSites features class to store output features...")
   arcpy.CreateFeatureclass_management (myWorkspace, Output_CS_fname, "POLYGON", in_ConSites, "", "", in_ConSites) 

   ### End data prep
   tEndPrep = datetime.now()
   deltaString = GetElapsedTime (tStartPrep, tEndPrep)
   printMsg("Data prep complete. Elapsed time: %s" %deltaString)
   
   # Process:  ShrinkWrap
   tProtoStart = datetime.now()
   printMsg("Creating ProtoSites by shrink-wrapping SBBs...")
   outPS = myWorkspace + os.sep + 'ProtoSites'
      # Saving ProtoSites to hard drive, just in case...
   printMsg('ProtoSites will be stored here: %s' % outPS)
   ShrinkWrap("SBB_lyr", dilDist, outPS)

   # Generalize Features in hopes of speeding processing and preventing random processing failures 
   arcpy.AddMessage("Simplifying features...")
   arcpy.Generalize_edit(outPS, "0.1 Meters")
   
   # Get info on ProtoSite generation
   numPS = countFeatures(outPS)
   tProtoEnd = datetime.now()
   deltaString = GetElapsedTime(tProtoStart, tProtoEnd)
   printMsg('Finished ProtoSite creation. There are %s ProtoSites.' %numPS)
   printMsg('Elapsed time: %s' %deltaString)

   # Loop through the ProtoSites to create final ConSites
   printMsg("Modifying individual ProtoSites to create final Conservation Sites...")
   counter = 1
   with arcpy.da.SearchCursor(outPS, ["SHAPE@"]) as myProtoSites:
      for myPS in myProtoSites:
         try:
            printMsg('Working on ProtoSite %s' % str(counter))
            tProtoStart = datetime.now()
            
            psSHP = myPS[0]
            tmpPS = scratchGDB + os.sep + "tmpPS"
            arcpy.CopyFeatures_management (psSHP, tmpPS) 
            tmpSS_grp = scratchGDB + os.sep + "tmpSS_grp"
            arcpy.CreateFeatureclass_management (scratchGDB, "tmpSS_grp", "POLYGON", in_ConSites, "", "", in_ConSites) 
            
            # Get SBBs within the ProtoSite
            printMsg('Selecting SBBs within ProtoSite...')
            arcpy.SelectLayerByLocation_management("SBB_lyr", "INTERSECT", tmpPS, "", "NEW_SELECTION", "NOT_INVERT")
            
            # Copy the selected SBB features to tmpSBB
            tmpSBB = scratchGDB + os.sep + 'tmpSBB'
            arcpy.CopyFeatures_management ("SBB_lyr", tmpSBB)
            printMsg('Selected SBBs copied.')
            
            # Get PFs within the ProtoSite
            printMsg('Selecting PFs within ProtoSite...')
            arcpy.SelectLayerByLocation_management("PF_lyr", "INTERSECT", tmpPS, "", "NEW_SELECTION", "NOT_INVERT")
            
            # Copy the selected PF features to tmpPF
            tmpPF = scratchGDB + os.sep + 'tmpPF'
            arcpy.CopyFeatures_management ("PF_lyr", tmpPF)
            printMsg('Selected PFs copied.')
            
            # Buffer around the ProtoSite
            printMsg('Buffering ProtoSite to get processing area...')
            tmpBuff = scratchGDB + os.sep + 'tmpBuff'
            arcpy.Buffer_analysis (tmpPS, tmpBuff, buffDist, "", "", "", "")  
            
            # Clip exclusion features to buffer
            if site_Type == 'TERRESTRIAL':
               printMsg('Clipping transportation features to buffer...')
               tranClp = scratchGDB + os.sep + 'tranClp'
               CleanClip(Trans, tmpBuff, tranClp, scratchParm)
               printMsg('Clipping exclusion features to buffer...')
               efClp = scratchGDB + os.sep + 'efClp'
               CleanClip(in_Exclude, tmpBuff, efClp, scratchParm)
            printMsg('Clipping hydro features to buffer...')
            hydroClp = scratchGDB + os.sep + 'hydroClp'
            CleanClip(sub_Hydro, tmpBuff, hydroClp, scratchParm)
                        
            # Cull Transportation Surface and Exclusion Features 
            # This is to eliminate features intended to be ignored in automation process
            if site_Type == 'TERRESTRIAL':    
               # Get Transportation Surface Erase Features
               printMsg('Subsetting transportation features')
               transErase = scratchGDB + os.sep + 'transErase'
               arcpy.Select_analysis (tranClp, transErase, transQry)
               
               # Get Exclusion Erase Features
               printMsg('Subsetting exclusion features')
               exclErase = scratchGDB + os.sep + 'exclErase'
               arcpy.Select_analysis (efClp, exclErase, transQry)
               efClp = exclErase
            
            # Cull Hydro Erase Features
            printMsg('Culling hydro erase features based on prevalence in SBBs...')
            hydroRtn = scratchGDB + os.sep + 'hydroRtn'
            CullEraseFeats (hydroClp, tmpSBB, joinFld, hydroPerCov, hydroRtn, scratchParm)
            
            # Dissolve Hydro Erase Features
            printMsg('Dissolving hydro erase features...')
            hydroDiss = scratchGDB + os.sep + 'hydroDiss'
            arcpy.Dissolve_management(hydroRtn, hydroDiss, "Hydro", "", "SINGLE_PART", "")
            
            # Get Hydro Erase Features
            printMsg('Eliminating narrow hydro features from erase features...')
            hydroErase = scratchGDB + os.sep + 'hydroErase'
            GetEraseFeats (hydroDiss, hydroQry, hydroElimDist, hydroErase, tmpPF, scratchParm)
            
            # Merge Erase Features (Exclusions, hydro, and transportation)
            if site_Type == 'TERRESTRIAL':
               printMsg('Merging erase features...')
               tmpErase = scratchGDB + os.sep + 'tmpErase'
               arcpy.Merge_management ([efClp, transErase, hydroErase], tmpErase)
            else:
               tmpErase = hydroErase
            
            # Coalesce erase features to remove weird gaps and slivers
            printMsg('Coalescing erase features...')
            coalErase = scratchGDB + os.sep + 'coalErase'
            Coalesce(tmpErase, "0.5 METERS", coalErase, scratchParm)

            # Modify SBBs and Erase Features
            printMsg('Clustering SBBs...')
            sbbClusters = scratchGDB + os.sep + 'sbbClusters'
            sbbErase = scratchGDB + os.sep + 'sbbErase'
            ChopSBBs(tmpPF, tmpSBB, coalErase, sbbClusters, sbbErase, "5 METERS", scratchParm)
            
            # Use erase features to chop out areas of SBBs
            printMsg('Erasing portions of SBBs...')
            sbbFrags = scratchGDB + os.sep + 'sbbFrags'
            CleanErase (tmpSBB, sbbErase, sbbFrags, scratchParm) 
            
            # Remove any SBB fragments too far from a PF
            printMsg('Culling SBB fragments...')
            sbbRtn = scratchGDB + os.sep + 'sbbRtn'
            CullFrags(sbbFrags, tmpPF, searchDist, sbbRtn)
            arcpy.MakeFeatureLayer_management(sbbRtn, "sbbRtn_lyr")
            
            # Use erase features to chop out areas of ProtoSites
            printMsg('Erasing portions of ProtoSites...')
            psFrags = scratchGDB + os.sep + 'psFrags'
            CleanErase (psSHP, sbbErase, psFrags, scratchParm) 
            
            # Remove any ProtoSite fragments too far from a PF
            printMsg('Culling ProtoSite fragments...')
            psRtn = scratchGDB + os.sep + 'psRtn'
            CullFrags(psFrags, tmpPF, searchDist, psRtn)
            
            # Loop through the final (split) ProtoSites
            counter2 = 1
            with arcpy.da.SearchCursor(psRtn, ["SHAPE@"]) as mySplitSites:
               for mySS in mySplitSites:
                  printMsg('Working on split site %s' % str(counter2))
                  
                  ssSHP = mySS[0]
                  tmpSS = scratchGDB + os.sep + "tmpSS" + str(counter2)
                  arcpy.CopyFeatures_management (ssSHP, tmpSS) 
                  
                  # Make Feature Layer from split site
                  arcpy.MakeFeatureLayer_management (tmpSS, "splitSiteLyr", "", "", "")
                           
                  # Get PFs within split site
                  arcpy.SelectLayerByLocation_management("PF_lyr", "INTERSECT", tmpSS, "", "NEW_SELECTION", "NOT_INVERT")
                  
                  # Select retained SBB fragments corresponding to selected PFs
                  tmpSBB2 = scratchGDB + os.sep + 'tmpSBB2' 
                  tmpPF2 = scratchGDB + os.sep + 'tmpPF2'
                  SubsetSBBandPF(sbbRtn, "PF_lyr", "SBB", joinFld, tmpSBB2, tmpPF2)
                  
                  # ShrinkWrap retained SBB fragments
                  csShrink = scratchGDB + os.sep + 'csShrink' + str(counter2)
                  ShrinkWrap(tmpSBB2, dilDist, csShrink)
                  
                  # Intersect shrinkwrap with original split site
                  # This is necessary to keep it from "spilling over" across features used to split.
                  csInt = scratchGDB + os.sep + 'csInt' + str(counter2)
                  arcpy.Intersect_analysis ([tmpSS, csShrink], csInt, "ONLY_FID")
                  
                  # Process:  Clean Erase (final removal of exclusion features)
                  if site_Type == 'TERRESTRIAL':
                     printMsg('Excising manually delineated exclusion features...')
                     ssErased = scratchGDB + os.sep + 'ssBnd' + str(counter2)
                     CleanErase (csInt, efClp, ssErased, scratchParm) 
                  else:
                     ssErased = csInt
                  
                  # Remove any fragments too far from a PF
                  # Verified this step is indeed necessary, 2018-01-23
                  printMsg('Culling site fragments...')
                  ssBnd = scratchGDB + os.sep + 'ssBnd'
                  CullFrags(ssErased, tmpPF2, searchDist, ssBnd)
                  
                  # Append the final geometry to the split sites group feature class.
                  printMsg("Appending feature...")
                  arcpy.Append_management(ssBnd, tmpSS_grp, "NO_TEST", "", "")
                  
                  counter2 +=1
                  del mySS

            # Re-merge split sites, if applicable
            printMsg("Reconnecting split sites, where warranted...")
            shrinkFrags = scratchGDB + os.sep + 'shrinkFrags'
            ShrinkWrap(tmpSS_grp, coalDist, shrinkFrags, 8)
            
            # Process:  Clean Erase (final removal of exclusion features)
            if site_Type == 'TERRESTRIAL':
               printMsg('Excising manually delineated exclusion features...')
               csErased = scratchGDB + os.sep + 'csErased'
               CleanErase (shrinkFrags, efClp, csErased, scratchParm) 
            else:
               csErased = shrinkFrags
            
            # Remove any fragments too far from a PF
            # Verified this step is indeed necessary, 2018-01-23
            printMsg('Culling site fragments...')
            csCull = scratchGDB + os.sep + 'csCull'
            CullFrags(csErased, tmpPF, searchDist, csCull)
            
            # Eliminate gaps
            printMsg('Eliminating gaps...')
            finBnd = scratchGDB + os.sep + 'finBnd'
            arcpy.EliminatePolygonPart_management (csCull, finBnd, "PERCENT", "", 99.99, "CONTAINED_ONLY")
            
            # Generalize
            printMsg('Generalizing boundary...')
            arcpy.Generalize_edit(finBnd, "0.5 METERS")

            # Append the final geometry to the ConSites feature class.
            printMsg("Appending feature...")
            arcpy.Append_management(finBnd, out_ConSites, "NO_TEST", "", "")
            
         except:
            # Error handling code swiped from "A Python Primer for ArcGIS"
            tb = sys.exc_info()[2]
            tbinfo = traceback.format_tb(tb)[0]
            pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
            msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

            printWrng(msgs)
            printWrng(pymsg)
            printMsg(arcpy.GetMessages(1))
         
         finally:
            tProtoEnd = datetime.now()
            deltaString = GetElapsedTime(tProtoStart, tProtoEnd)
            printMsg("Processing complete for ProtoSite %s. Elapsed time: %s" %(str(counter), deltaString))
            counter +=1
            del myPS
            
   tFinish = datetime.now()
   deltaString = GetElapsedTime (tStart, tFinish)
   printMsg("Processing complete. Total elapsed time: %s" %deltaString)

   
# Use the main function below to run CreateConSites function directly from Python IDE or command line with hard-coded variables
def main():
   # Set up variables
   in_SBB = r'C:\Users\xch43889\Documents\Working\ConSites\Biotics.gdb\SBB_20180131_expand' # Input Site Building Blocks
   ysn_Expand =  "false" # Expand SBB selection?
   in_PF = r'C:\Users\xch43889\Documents\Working\ConSites\Biotics.gdb\ProcFeats_20180131_173111' # Input Procedural Features
   joinFld = "SFID" # Source Feature ID field
   in_Cores = r'C:\Users\xch43889\Documents\Working\ConSites\VaNLA2017Cores4ConSites.gdb\VaNLACoresRanks123' # Cores used to expand sites
   Roads = r"H:\Backups\DCR_Work_DellD\TransportatationProc\RCL_Proc_20171206.gdb\RCL_surfaces_20171206"
   Rail = r"H:\Backups\DCR_Work_DellD\TransportatationProc\Rail_Proc_20180108.gdb\Rail_surfaces_20180108"
   in_TranSurf = r'C:\Testing\csTroubleShoot.gdb\mergeTrans' # Input transportation surface features
   in_Hydro = r"H:\Backups\DCR_Work_DellD\SBBs_ConSites\Automation\ConSitesReview_July2017\AutomationInputs_20170605.gdb\NHD_VA_2014" # Input open water features
   in_Exclude = r"H:\Backups\DCR_Work_DellD\SBBs_ConSites\ExclFeats_20171208.gdb\ExclFeats" # Input delineated exclusion features
   in_ConSites = r"C:\Users\xch43889\Documents\Working\ConSites\Biotics.gdb\ConSites_20180131_173111" # Current Conservation Sites; for template
   out_ConSites = r'C:\Testing\cs20180129.gdb\ConSites_Final' # Output new Conservation Sites
   scratchGDB = "in_memory" # Workspace for temporary data
   # End of user input

   CreateConSites(in_SBB, ysn_Expand, in_PF, joinFld, in_TranSurf, in_Hydro, in_Exclude, in_ConSites, out_ConSites, scratchGDB)

if __name__ == '__main__':
   main()
