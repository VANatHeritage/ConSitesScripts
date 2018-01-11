# ----------------------------------------------------------------------------------------
# CreateConSites.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016-02-25 (Adapted from suite of ModelBuilder models)
# Last Edit: 2018-01-11
# Creator:  Kirsten R. Hazler

# Summary:
# Given a set of Site Building Blocks, corresponding Procedural Features, polygons delineating open water and road right-of-ways, and "Exclusion" features, creates a set of Conservation Sites.  Exclusion features are manually or otherwise delineated areas that are used to erase unsuitable areas from ProtoSites.  

# TO DO: Test code as it is now, then delete proposed deletions and test again.
# TO DO: Bring in rail features and merge with roads
# TO DO: Eliminate remaining holes in site if < 1 ha.
# ----------------------------------------------------------------------------------------

# Import function libraries and settings
import libConSiteFx
from libConSiteFx import *

def CreateConSites(in_SBB, ysn_Expand, in_PF, fld_SFID, in_TranSurf, in_Hydro, in_Exclude, in_ConSites, out_ConSites, scratchGDB):

   # Specify a bunch of parameters
   selDist = "1000 METERS" # Distance used to expand the SBB selection, if this option is selected.
   dilDist = "250 METERS" # Distance used to coalesce SBBs into ProtoSites (precursors to final automated CS boundaries). Features within twice this distance of each other will be merged into one.
   hydroPerCov = 25 # The minimum percent cover of any PF that must be within a given hydro feature, for that hydro feature to be eliminated from the set of features which are used to erase portions of the site.
   hydroQry = "Hydro = 1" # Expression used to select appropriate hydro features to create erase features
   hydroElimDist = "10 METERS" # Distance used to eliminate insignificant water features from the set of erasing features. Portions of water bodies less than double this width will not be used to split or erase portions of sites.
   transPerCov = 50 #The minimum percent cover of any PF that must be within a given transportation surface feature, for that feature to be eliminated from the set of features which are used to erase portions of the site.
   transQry = "" #"DCR_ROW_TYPE = 'IS' OR DCR_ROW_TYPE = 'PR'" # Expression used to select appropriate transportation surface features to create erase features
   transElimDist = "5 METERS" # Distance used to eliminate insignificant transportation surface features from the set of erasing features. Portions of features less than double this width will not be used to split or erase portions of sites.
   buffDist = "200 METERS" # Distance used to buffer ProtoSites to establish the area for further processing.
   searchDist = "0 METERS" # Distance from PFs used to determine whether to cull SBB and ConSite fragments after ProtoSites have been split.
   coalDist = "25 METERS" # Distance for coalescing split sites back together. This value, multiplied by 4, is also used as a final site smoothing parameter.
   
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

   if not scratchGDB:
      scratchGDB = "in_memory"
      # Use "in_memory" as default, but if script is failing, use scratchGDB on disk.
      
   if scratchGDB != "in_memory":
      printMsg("Scratch outputs will be stored here: %s" % scratchGDB)
      scratchParm = scratchGDB
   else:
      printMsg("Scratch products are being stored in memory and will not persist. If processing fails inexplicably, or if you want to be able to inspect scratch products, try running this with a specified scratchGDB on disk.")
      scratchParm = ""

   # Set overwrite option so that existing data may be overwritten
   arcpy.env.overwriteOutput = True 

   # Declare path/name of output data and workspace
   drive, path = os.path.splitdrive(out_ConSites) 
   path, filename = os.path.split(path)
   myWorkspace = drive + path
   Output_CS_fname = filename
   
   # If applicable, clear any selections on non-SBB inputs
   for fc in [in_PF, in_TranSurf, in_Hydro, in_Exclude]:
      typeFC= (arcpy.Describe(fc)).dataType
      if typeFC == 'FeatureLayer':
         arcpy.SelectLayerByAttribute_management (fc, "CLEAR_SELECTION")
   
   # Make Feature Layer from PFs
   arcpy.MakeFeatureLayer_management(in_PF, "PF_lyr")   

   # Set up output locations for subsets of SBBs and PFs to process
   SBB_sub = myWorkspace + os.sep + 'SBB_sub'
   PF_sub = myWorkspace + os.sep + 'PF_sub'

   if ysn_Expand == "true":
      # Expand SBB selection
      printMsg('Expanding the current SBB selection and making copies of the SBBs and PFs...')
      ExpandSBBselection(in_SBB, "PF_lyr", fld_SFID, in_ConSites, selDist, SBB_sub, PF_sub)
   else:
      # Subset PFs and SBBs
      printMsg('Using the current SBB selection and making copies of the SBBs and PFs...')
      SubsetSBBandPF(in_SBB, "PF_lyr", "PF", fld_SFID, SBB_sub, PF_sub)

   # Make Feature Layers from from subsets of PFs and SBBs
   arcpy.MakeFeatureLayer_management(PF_sub, "PF_lyr") 
   arcpy.MakeFeatureLayer_management(SBB_sub, "SBB_lyr") 

   # Process:  Create Feature Class (to store ConSites)
   printMsg("Creating ConSites features class to store output features...")
   arcpy.CreateFeatureclass_management (myWorkspace, Output_CS_fname, "POLYGON", in_ConSites, "", "", in_ConSites) 

   # Process:  ShrinkWrap
   printMsg("Creating ProtoSites by shrink-wrapping SBBs...")
   outPS = myWorkspace + os.sep + 'ProtoSites'
      # Saving ProtoSites to hard drive, just in case...
   printMsg('ProtoSites will be stored here: %s' % outPS)
   ShrinkWrap(SBB_sub, dilDist, outPS, scratchParm)

   # Process:  Get Count
   numPS = countFeatures(outPS)
   printMsg('There are %s ProtoSites' %numPS)

   # Loop through the ProtoSites to create final ConSites
   printMsg("Modifying individual ProtoSites to create final Conservation Sites...")
   myProtoSites = arcpy.da.SearchCursor(outPS, ["SHAPE@"])
   counter = 1

   for myPS in myProtoSites:
      try:
         printMsg('Working on ProtoSite %s' % str(counter))
         
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
         CleanClip(in_TranSurf, tmpBuff, tranClp, scratchParm)
         printMsg('Clipping hydro features to buffer...')
         hydroClp = scratchGDB + os.sep + 'hydroClp'
         CleanClip(in_Hydro, tmpBuff, hydroClp, scratchParm)
         printMsg('Clipping Exclusion Features to buffer...')
         efClp = scratchGDB + os.sep + 'efClp'
         CleanClip(in_Exclude, tmpBuff, efClp, scratchParm)
         
         # Get Transportation Surface Erase Features
         rowErase = scratchGDB + os.sep + 'rowErase'
         GetEraseFeats (tranClp, transQry, transElimDist, rowErase)
         
         # Cull Transportation Surface Erase Features 
         printMsg('Culling transportation erase features...')
         rowRtn = scratchGDB + os.sep + 'rowRtn'
         CullEraseFeats (rowErase, tmpBuff, tmpPF, fld_SFID, transPerCov, rowRtn)
         
         # Get Hydro Erase Features
         hydroErase = scratchGDB + os.sep + 'hydroErase'
         GetEraseFeats (hydroClp, hydroQry, hydroElimDist, hydroErase)
         
         # Cull Hydro Erase Features
         printMsg('Culling hydro erase features...')
         hydroRtn = scratchGDB + os.sep + 'hydroRtn'
         CullEraseFeats (hydroErase, tmpBuff, tmpPF, fld_SFID, hydroPerCov, hydroRtn)
         
         # Merge Erase Features (Exclusion features and retained Hydro and Transp features)
         printMsg('Merging erase features...')
         tmpErase = scratchGDB + os.sep + 'tmpErase'
         arcpy.Merge_management ([efClp, rowRtn, hydroRtn], tmpErase) 
         
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
         mySplitSites = arcpy.da.SearchCursor(coalFrags, ["SHAPE@"])
         counter2 = 1
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
            SubsetSBBandPF(sbbRtn, "PF_lyr", "SBB", fld_SFID, tmpSBB2, tmpPF2)
            
            # ShrinkWrap retained SBB fragments
            csShrink = scratchGDB + os.sep + 'csShrink' + str(counter2)
            ShrinkWrap(tmpSBB2, dilDist, csShrink, scratchParm)
            
            # Intersect shrinkwrap with original split site
            # This is necessary to keep it from "spilling over" across features used to split.
            csInt = scratchGDB + os.sep + 'csInt' + str(counter2)
            arcpy.Intersect_analysis ([tmpSS, csShrink], csInt, "ONLY_FID")
         
            # Remove gaps within site
            csNoGap = scratchGDB + os. sep + 'csNoGap' + str(counter2)
            arcpy.Union_analysis (csInt, csNoGap, "ONLY_FID", "", "NO_GAPS")
            csDiss = scratchGDB + os.sep + 'csDissolved' + str(counter2)
            arcpy.Dissolve_management (csNoGap, csDiss, "", "", "SINGLE_PART") 
            
            ## I think the next two blocks of code can be deleted, but awaiting further testing to be sure. 1/11/2018
            # Remove any fragments too far from a PF
            ### WHY would there be any more fragments at this point??? Delete this step??
            #csRtn = scratchGDB + os.sep + 'csRtn'
            #CullFrags(csDiss, tmpPF2, searchDist, csRtn)
            # Test output: d2
            
            # Process:  Coalesce (final smoothing of the site)  
            # WHY?? Probably should delete this step...
            #csCoal = scratchGDB + os.sep + 'csCoal' + str(counter2)
            #Coalesce(csDiss, coalDist, csCoal, scratchParm)
            # Test output: d3
            
            # Process:  Clean Erase (final removal of exclusion features)
            printMsg('Excising manually delineated exclusion features...')
            csBnd = scratchGDB + os.sep + 'csBnd' + str(counter2)
            CleanErase (csDiss, efClp, csBnd, scratchParm) 

            # Append the final geometry to the ConSites feature class.
            printMsg("Appending feature...")
            arcpy.Append_management(csBnd, out_ConSites, "NO_TEST", "", "")
            
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
         counter +=1
         del myPS
      
# Use the main function below to run CreateConSites function directly from Python IDE or command line with hard-coded variables
def main():
   # Set up variables
   in_SBB = r"C:\Testing\ConSiteTests20180111.gdb\sbb01" # Input Site Building Blocks
   ysn_Expand =  "false" # Expand SBB selection?
   in_PF = r"C:\Testing\ConSiteTests20180111.gdb\pf01" # Input Procedural Features
   fld_SFID = "SFID" # Source Feature ID field
   in_TranSurf = r"H:\Backups\DCR_Work_DellD\TransportatationProc\RCL_Proc_20171206.gdb\RCL_surfaces_20171206" # Input transportation surface features
   in_Hydro = r"H:\Backups\DCR_Work_DellD\SBBs_ConSites\Automation\ConSitesReview_July2017\AutomationInputs_20170605.gdb\NHD_VA_2014" # Input open water features
   in_Exclude = r"H:\Backups\DCR_Work_DellD\SBBs_ConSites\ExclFeats_20171208.gdb\ExclFeats" # Input delineated exclusion features
   in_ConSites = r"H:\Backups\DCR_Work_DellD\SBBs_ConSites\Automation\ConSitesReview_July2017\Biotics_20170605.gdb\ConSites_20170605_114532" # Current Conservation Sites; for template
   out_ConSites = r"C:\Testing\ConSiteTests20180111.gdb\acs01_NoCoresNoRailTrans5_exCoal1_d3" # Output new Conservation Sites
   scratchGDB = r"C:\Testing\scratch20180111.gdb" # Workspace for temporary data
   # End of user input

   CreateConSites(in_SBB, ysn_Expand, in_PF, fld_SFID, in_TranSurf, in_Hydro, in_Exclude, in_ConSites, out_ConSites, scratchGDB)

if __name__ == '__main__':
   main()
