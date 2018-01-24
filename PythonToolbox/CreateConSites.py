# ----------------------------------------------------------------------------------------
# CreateConSites.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016-02-25 (Adapted from suite of ModelBuilder models)
# Last Edit: 2018-01-24
# Creator:  Kirsten R. Hazler

# Summary:
# Given a set of Site Building Blocks, corresponding Procedural Features, polygons delineating open water and road right-of-ways, and "Exclusion" features, creates a set of Conservation Sites.  Exclusion features are manually or otherwise delineated areas that are used to erase unsuitable areas from ProtoSites.  

# TO DO: Test code as it is now, then delete proposed deletions and test again.
# ----------------------------------------------------------------------------------------

# Import function libraries and settings
import libConSiteFx
from libConSiteFx import *

def CreateConSites(in_SBB, ysn_Expand, in_PF, joinFld, in_Cores, in_TranSurf, in_Hydro, in_Exclude, in_ConSites, out_ConSites, scratchGDB = "in_memory"):
   '''Creates Conservation Sites from the specified inputs:
   - in_SBB: feature class representing Site Building Blocks
   - ysn_Expand: ["true"/"false"] - determines whether to expand the selection of SBBs to include more in the vicinity
   - in_PF: feature class representing Procedural Features
   - joinFld: name of the field containing the unique ID linking SBBs to PFs. Field name is must be the same for both.
   - in_TranSurf: feature class(es) representing transportation surfaces (i.e., road and rail) [If multiple, this is a string with items separated by ';']
   - in_Hydro: feature class representing water bodies
   - in_Exclude: feature class representing areas to definitely exclude from sites
   - in_ConSites: feature class representing current Conservation Sites (or, a template feature class)
   - out_ConSites: the output feature class representing updated Conservation Sites
   - scratchGDB: geodatabase to contain intermediate/scratch products. Setting this to "in_memory" can result in HUGE savings in processing time, but there's a chance you might run out of memory and cause a crash.
   '''
   tStart = datetime.now()
   # Specify a bunch of parameters
   selDist = "1000 METERS" # Distance used to expand the SBB selection, if this option is selected. Also used to add extra buffer to SBBs.
   dilDist = "250 METERS" # Distance used to coalesce SBBs into ProtoSites (precursors to final automated CS boundaries). Features within twice this distance of each other will be merged into one.
   hydroPerCov = 25 # The minimum percent cover of any PF that must be within a given hydro feature, for that hydro feature to be eliminated from the set of features which are used to erase portions of the site.
   hydroQry = "Hydro = 1" # Expression used to select appropriate hydro features to create erase features
   hydroElimDist = "10 METERS" # Distance used to eliminate insignificant water features from the set of erasing features. Portions of water bodies less than double this width will not be used to split or erase portions of sites.
   transPerCov = 50 #The minimum percent cover of any PF that must be within a given transportation surface feature, for that feature to be eliminated from the set of features which are used to erase portions of the site.
   transQry = "nhIgnore =0 OR nhIgnore IS NULL" ### Substituted old query with new query, allowing user to specify segments to ignore. Old query was: "DCR_ROW_TYPE = 'IS' OR DCR_ROW_TYPE = 'PR'" # Expression used to select appropriate transportation surface features to create erase features
   transElimDist = "5 METERS" # Distance used to eliminate insignificant transportation surface features from the set of erasing features. Portions of features less than double this width will not be used to split or erase portions of sites.
   buffDist = "200 METERS" # Distance used to buffer ProtoSites to establish the area for further processing.
   searchDist = "0 METERS" # Distance from PFs used to determine whether to cull SBB and ConSite fragments after ProtoSites have been split.
   coalDist = "10 METERS" # Distance for coalescing split sites back together. Sites with less than double this width between each other will merge.
   # smthMulti = 2 # Multiplier applied to coalDist to obtain final smoothing parameter 
   
   # Give user some info on parameters
   printMsg('Selection distance = %s' %selDist)
   printMsg('Dilation distance = %s' %dilDist)
   printMsg('Hydro percent cover = %s' %hydroPerCov)
   printMsg('Hydro elimination distance = %s' %hydroElimDist)
   printMsg('Transportation surface percent cover = %s' %transPerCov)
   printMsg('Transportation surface elimination distance = %s' %transElimDist)
   printMsg('Buffer distance = %s' %buffDist)
   printMsg('Search distance = %s' %searchDist)
   printMsg('Coalesce distance = %s' %coalDist)
   # printMsg('Smoothing multiplier = %s' %str(smthMulti))

   if not scratchGDB:
      scratchGDB = "in_memory"
      # Use "in_memory" as default, but if script is failing, use scratchGDB on disk.
      
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
   Trans = in_TranSurf.split(';')
   
   # If applicable, clear any selections on non-SBB inputs
   for fc in [in_PF, in_Hydro, in_Exclude]:
      typeFC= (arcpy.Describe(fc)).dataType
      if typeFC == 'FeatureLayer':
         arcpy.SelectLayerByAttribute_management (fc, "CLEAR_SELECTION")
   for fc in Trans:
      typeFC= (arcpy.Describe(fc)).dataType
      if typeFC == 'FeatureLayer':
         arcpy.SelectLayerByAttribute_management (fc, "CLEAR_SELECTION")
   
   ### Start data prep
   tStartPrep = datetime.now()
   
   # Merge the transportation layers, if necessary
   if len(Trans) == 1:
      Trans = Trans[0]
   else:
      printMsg('Merging transportation surfaces')
      mergeTrans = scratchGDB + os.sep + 'mergeTrans'
      arcpy.Merge_management(Trans, mergeTrans)
      Trans = mergeTrans
   
   # Get relevant subset of transportation features
   printMsg('Subsetting transportation features')
   subTrans = scratchGDB + os.sep + 'subTrans'
   arcpy.Select_analysis (Trans, subTrans, transQry)
   Trans = subTrans
   
   # # Get relevant subset of hydro features
   # printMsg('Subsetting hydro features')
   # subHydro = scratchGDB + os.sep + 'subHydro'
   # arcpy.Select_analysis (in_Hydro, subHydro, hydroQry)
   
   # Make Feature Layer from PFs
   arcpy.MakeFeatureLayer_management(in_PF, "PF_lyr")   

   # Set up output locations for subsets of SBBs and PFs to process
   SBB_sub = myWorkspace + os.sep + 'SBB_sub'
   PF_sub = myWorkspace + os.sep + 'PF_sub'

   if ysn_Expand == "true":
      # Expand SBB selection
      printMsg('Expanding the current SBB selection and making copies of the SBBs and PFs...')
      ExpandSBBselection(in_SBB, "PF_lyr", joinFld, in_ConSites, selDist, SBB_sub, PF_sub)
   else:
      # Subset PFs and SBBs
      printMsg('Using the current SBB selection and making copies of the SBBs and PFs...')
      SubsetSBBandPF(in_SBB, "PF_lyr", "PF", joinFld, SBB_sub, PF_sub)

   # Make Feature Layers
   arcpy.MakeFeatureLayer_management(PF_sub, "PF_lyr") 
   arcpy.MakeFeatureLayer_management(in_Cores, "Cores_lyr") 
   
   ### Cores incorporation code starts here
   # Process: Select Layer By Location (Get Cores intersecting PFs)
   printMsg('Selecting cores that intersect procedural features')
   arcpy.SelectLayerByLocation_management("Cores_lyr", "INTERSECT", "PF_lyr", "", "NEW_SELECTION", "NOT_INVERT")

   # Process:  Copy the selected Cores features to scratch feature class
   selCores = scratchGDB + os.sep + 'selCores'
   arcpy.CopyFeatures_management ("Cores_lyr", selCores) 

   # Process:  Repair Geometry and get feature count
   arcpy.RepairGeometry_management (selCores, "DELETE_NULL")
   numCores = countFeatures(selCores)
   printMsg('There are %s cores to process.' %str(numCores))
   
   # Add extra buffers to SBBs of PFs centered in Cores
   # Create Feature Class to store expanded SBBs
   printMsg("Creating feature class to store buffered SBBs...")
   arcpy.CreateFeatureclass_management (myWorkspace, 'sbbExpand', "POLYGON", SBB_sub, "", "", SBB_sub) 
   sbbExpand = myWorkspace + os.sep + 'sbbExpand'
   # Loop through Cores
   counter = 1
   with  arcpy.da.SearchCursor(selCores, ["SHAPE@", "OBJECTID"]) as myCores:
      for core in myCores:
         # Add extra buffer for SBBs of PFs located in cores. Extra buffer needs to be snipped to core in question.
         coreShp = core[0]
         coreID = core[1]
         printMsg('Working on Core ID %s' % str(coreID))
         out_SBB = scratchGDB + os.sep + 'sbb'
         AddCoreAreaToSBBs(PF_sub, SBB_sub, joinFld, coreShp, out_SBB, selDist, scratchGDB = "in_memory")
         
         # Append expanded SBB features to output
         arcpy.Append_management (out_SBB, sbbExpand, "NO_TEST")
         
         del core
   
   # Merge, then dissolve original SBBs with buffered SBBs to get final shapes
   printMsg('Finalizing...')
   sbbAll = scratchGDB + os.sep + "sbbAll"
   sbbFinal = scratchGDB + os.sep + "sbbFinal"
   arcpy.Merge_management ([SBB_sub, sbbExpand], sbbAll)
   arcpy.Dissolve_management (sbbAll, sbbFinal, joinFld, "")
   arcpy.MakeFeatureLayer_management(sbbFinal, "SBB_lyr") 
   
   ### Cores incorporation code ends here

   # Process:  Create Feature Class (to store ConSites)
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
   ShrinkWrap(sbbFinal, dilDist, outPS, scratchParm)

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
            printMsg('Buffering ProtoSite...')
            tmpBuff = scratchGDB + os.sep + 'tmpBuff'
            arcpy.Buffer_analysis (tmpPS, tmpBuff, buffDist, "", "", "", "")  
            
            # Clip exclusion features to buffer
            printMsg('Clipping transportation features to buffer...')
            tranClp = scratchGDB + os.sep + 'tranClp'
            CleanClip(Trans, tmpBuff, tranClp, scratchParm)
            printMsg('Clipping hydro features to buffer...')
            hydroClp = scratchGDB + os.sep + 'hydroClp'
            CleanClip(in_Hydro, tmpBuff, hydroClp, scratchParm)
            printMsg('Clipping exclusion features to buffer...')
            efClp = scratchGDB + os.sep + 'efClp'
            CleanClip(in_Exclude, tmpBuff, efClp, scratchParm)
            
            # Cull Transportation Surface Features 
            printMsg('Culling transportation erase features with significant PF coverage...')
            transRtn = scratchGDB + os.sep + 'transRtn'
            CullEraseFeats (tranClp, tmpBuff, tmpPF, joinFld, transPerCov, transRtn)
            
            # Eliminated GetEraseFeats process (2018-01-17)
            # # Get Transportation Surface Erase Features
            # transErase = scratchGDB + os.sep + 'transErase'
            # GetEraseFeats (transRtn, transQry, transElimDist, transErase)
            
            # # Cull Hydro Erase Features
            # printMsg('Culling hydro erase features...')
            # hydroRtn = scratchGDB + os.sep + 'hydroRtn'
            # CullEraseFeats (hydroClp, tmpBuff, tmpPF, joinFld, hydroPerCov, hydroRtn)
            
            # Get Hydro Erase Features
            printMsg('Eliminating some hydro features from erase features...')
            hydroErase = scratchGDB + os.sep + 'hydroErase'
            GetEraseFeats (hydroClp, hydroQry, hydroElimDist, hydroErase, tmpPF)
            
            # Merge Erase Features (Exclusion features, hydro features, and retained transportation features)
            printMsg('Merging erase features...')
            tmpErase = scratchGDB + os.sep + 'tmpErase'
            arcpy.Merge_management ([efClp, transRtn, hydroErase], tmpErase)

            # Use erase features to chop out areas of SBBs
            printMsg('Erasing portions of SBBs...')
            sbbFrags = scratchGDB + os.sep + 'sbbFrags'
            CleanErase (tmpSBB, tmpErase, sbbFrags, scratchParm) 
            
            # Remove any SBB fragments too far from a PF
            printMsg('Culling SBB fragments...')
            sbbRtn = scratchGDB + os.sep + 'sbbRtn'
            CullFrags(sbbFrags, tmpPF, searchDist, sbbRtn)
            arcpy.MakeFeatureLayer_management(sbbRtn, "sbbRtn_lyr")
            
            # Use erase features to chop out areas of ProtoSites
            printMsg('Erasing portions of ProtoSites...')
            psFrags = scratchGDB + os.sep + 'psFrags'
            CleanErase (psSHP, tmpErase, psFrags, scratchParm) 
            
            # Remove any ProtoSite fragments too far from a PF
            printMsg('Culling ProtoSite fragments...')
            psRtn = scratchGDB + os.sep + 'psRtn'
            CullFrags(psFrags, tmpPF, searchDist, psRtn)
            
            # Re-merge split sites, if applicable
            coalFrags = scratchGDB + os.sep + 'coalFrags'
            Coalesce(psRtn, coalDist, coalFrags, scratchParm)
            
            # Loop through the final (split) ProtoSites
            counter2 = 1
            with arcpy.da.SearchCursor(coalFrags, ["SHAPE@"]) as mySplitSites:
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
                  ShrinkWrap(tmpSBB2, dilDist, csShrink, scratchParm)
                  
                  # Intersect shrinkwrap with original split site
                  # This is necessary to keep it from "spilling over" across features used to split.
                  csInt = scratchGDB + os.sep + 'csInt' + str(counter2)
                  arcpy.Intersect_analysis ([tmpSS, csShrink], csInt, "ONLY_FID")
               
                  # # Remove gaps within site
                  # # Eliminate gaps at the end instead
                  # csNoGap = scratchGDB + os. sep + 'csNoGap' + str(counter2)
                  # arcpy.Union_analysis (csInt, csNoGap, "ONLY_FID", "", "NO_GAPS")
                  # csDiss = scratchGDB + os.sep + 'csDissolved' + str(counter2)
                  # arcpy.Dissolve_management (csNoGap, csDiss, "", "", "SINGLE_PART") 
                  
                  # Remove any fragments too far from a PF
                  # Verified this step is indeed necessary, 2018-01-23
                  printMsg('Culling site fragments...')
                  cleanFrags = scratchGDB + os.sep + 'clnFrags'
                  CleanFeatures(csInt, cleanFrags)
                  csRtn = scratchGDB + os.sep + 'csRtn'
                  CullFrags(cleanFrags, tmpPF2, searchDist, csRtn)
                  
                  # Process:  Coalesce (final smoothing of the site)  
                  # Verified this step is indeed necessary, 2018-01-23. It gets rid of linear intrusions (e.g., road cuts)
                  # num, units, smthDist = multiMeasure(coalDist, smthMulti)
                  csCoal = scratchGDB + os.sep + 'csCoal' + str(counter2)
                  Coalesce(csRtn, coalDist, csCoal, scratchParm)
                  
                  # Process:  Clean Erase (final removal of exclusion features)
                  printMsg('Excising manually delineated exclusion features...')
                  csBnd = scratchGDB + os.sep + 'csBnd' + str(counter2)
                  CleanErase (csCoal, efClp, csBnd, scratchParm) 
                  
                  # Eliminate gaps
                  printMsg('Eliminating insignificant gaps...')
                  finBnd = scratchGDB + os.sep + 'finBnd'
                  arcpy.EliminatePolygonPart_management (csBnd, finBnd, "AREA_OR_PERCENT", "1 HECTARES", "10", "CONTAINED_ONLY")

                  # Append the final geometry to the ConSites feature class.
                  printMsg("Appending feature...")
                  arcpy.Append_management(finBnd, out_ConSites, "NO_TEST", "", "")
                  
                  counter2 +=1
                  del mySS
               
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
   #in_SBB = r'C:\Testing\ConSiteTests20180123.gdb\sbb01'
   in_SBB = r'C:\Users\xch43889\Documents\Working\ConSites\Biotics_20171206.gdb\SBB_20171206' # Input Site Building Blocks
   ysn_Expand =  "false" # Expand SBB selection?
   #in_PF = r'C:\Testing\ConSiteTests20180123.gdb\pf01'
   in_PF = r'C:\Users\xch43889\Documents\Working\ConSites\Biotics_20171206.gdb\ProcFeats_20171206_183308' # Input Procedural Features
   joinFld = "SFID" # Source Feature ID field
   #in_Cores = r'C:\Testing\ConSiteTests20180123.gdb\Cores01'
   in_Cores = r'C:\Users\xch43889\Documents\Working\ConSites\VaNLA2017Cores4ConSites.gdb\VaNLACoresRanks123' # Cores used to expand sites
   Roads = r"H:\Backups\DCR_Work_DellD\TransportatationProc\RCL_Proc_20171206.gdb\RCL_surfaces_20171206"
   Rail = r"H:\Backups\DCR_Work_DellD\TransportatationProc\Rail_Proc_20180108.gdb\Rail_surfaces_20180108"
   in_TranSurf = r'C:\Testing\scratch20180118.gdb\mergeTrans' # Input transportation surface features
   in_Hydro = r"H:\Backups\DCR_Work_DellD\SBBs_ConSites\Automation\ConSitesReview_July2017\AutomationInputs_20170605.gdb\NHD_VA_2014" # Input open water features
   in_Exclude = r"H:\Backups\DCR_Work_DellD\SBBs_ConSites\ExclFeats_20171208.gdb\ExclFeats" # Input delineated exclusion features
   in_ConSites = r"C:\Users\xch43889\Documents\Working\ConSites\Biotics_20171206.gdb\ConSites_20171206_183308" # Current Conservation Sites; for template
   out_ConSites = r'C:\Testing\ConSiteTests20180123.gdb\ConSites_fullTest' # Output new Conservation Sites
   scratchGDB = "in_memory" # Workspace for temporary data
   # End of user input

   CreateConSites(in_SBB, ysn_Expand, in_PF, joinFld, in_Cores, in_TranSurf, in_Hydro, in_Exclude, in_ConSites, out_ConSites, scratchGDB)

if __name__ == '__main__':
   main()
