# ----------------------------------------------------------------------------------------
# CreateConSites.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016-02-25 (Adapted from suite of ModelBuilder models)
# Last Edit: 2018-07-19
# Creator:  Kirsten R. Hazler

# Summary:
# Function to create Conservation Sites (ConSites) from Site Building Blocks (SBBs), corresponding Procedural Features (PFs), polygons delineating open water and transportation surfaces, and "Exclusion" features. 
# ----------------------------------------------------------------------------------------

# Import function libraries and settings
import libConSiteFx
from libConSiteFx import *

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
