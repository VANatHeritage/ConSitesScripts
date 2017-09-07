# ----------------------------------------------------------------------------------------
# CreateConSites.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016-02-25 (Adapted from suite of ModelBuilder models)
# Last Edit: 2017-09-07
# Creator:  Kirsten R. Hazler

# Summary:
# Given a set of Site Building Blocks, corresponding Procedural Features, polygons delineating open water and road right-of-ways, and "Exclusion" features, creates a set of Conservation Sites.  Exclusion features are manually or otherwise delineated areas that are used to erase unsuitable areas from ProtoSites.  ***This tool version allows users to tweak parameters.

# TO DO: Continue converting to function from line 63
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
   transQry = "DCR_ROW_TYPE = 'IS' OR DCR_ROW_TYPE = 'PR'" # Expression used to select appropriate transportation surface features to create erase features
   transElimDist = "10 METERS" # Distance used to eliminate insignificant transportation surface features from the set of erasing features. Portions of features less than double this width will not be used to split or erase portions of sites.
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
      arcpy.AddMessage("Scratch outputs will be stored here: %s" % scratchGDB)
      scratchParm = scratchGDB
   else:
      arcpy.AddMessage("Scratch products are being stored in memory and will not persist. If processing fails inexplicably, or if you want to be able to inspect scratch products, try running this with a specified scratchGDB on disk.")
      scratchParm = ""

   # Set overwrite option so that existing data may be overwritten
   arcpy.env.overwriteOutput = True 

   # Declare path/name of output data and workspace
   drive, path = os.path.splitdrive(out_ConSites) 
   path, filename = os.path.split(path)
   myWorkspace = drive + path
   Output_CS_fname = filename
   
# Process: If applicable, clear any selections on non-SBB inputs
for fc in [in_PF, in_TranSurf, in_Hydro, in_Exclude]:
   typeFC= (arcpy.Describe(fc)).dataType
   if typeFC == 'FeatureLayer':
      arcpy.SelectLayerByAttribute_management (fc, "CLEAR_SELECTION")
   
# Process: Make Feature Layer from PFs
arcpy.MakeFeatureLayer_management(in_PF, "PF_lyr")   

# Set up output locations for subsets of SBBs and PFs to process
SBB_sub = myWorkspace + os.sep + 'SBB_sub'
PF_sub = myWorkspace + os.sep + 'PF_sub'

if ysn_Expand == "true":
   # Process:  Expand SBB selection
   arcpy.AddMessage('Expanding the current SBB selection and making copies of the SBBs and PFs...')
   arcpy.ExpandSBBselection_consiteTools(in_SBB, "PF_lyr", fld_SFID, in_ConSites, selDist, SBB_sub, PF_sub)
else:
   # Process:  Subset PFs and SBBs
   arcpy.AddMessage('Using the current SBB selection and making copies of the SBBs and PFs...')
   arcpy.SubsetSBBandPF_consiteTools(in_SBB, "PF_lyr", "PF", fld_SFID, SBB_sub, PF_sub)

# Process: Make Feature Layers from inclusion features, and from subsets of PFs and SBBs
arcpy.MakeFeatureLayer_management(PF_sub, "PF_lyr") 
arcpy.MakeFeatureLayer_management(SBB_sub, "SBB_lyr") 

# Select by location:  inclusion features w/in dist of SBBs
arcpy.AddMessage('Selecting relevant inclusion features. These will be treated as additional SBBs when creating sites....')
search_distance = str(inclDist) + " METERS"

# Process:  Create Feature Class (to store ConSites)
arcpy.AddMessage("Creating ConSites features class to store output features...")
arcpy.CreateFeatureclass_management (myWorkspace, Output_CS_fname, "POLYGON", in_ConSites, "", "", in_ConSites) 

# Process:  ShrinkWrap
arcpy.AddMessage("Creating ProtoSites by shrink-wrapping SBBs...")
outPS = myWorkspace + os.sep + 'ProtoSites'
   # Saving ProtoSites to hard drive, just in case...
arcpy.AddMessage('ProtoSites will be stored here: %s' % outPS)
arcpy.ShrinkWrap_consiteTools(SBB_sub, dilDist, outPS, scratchParm)

# Process:  Get Count
numPS = (arcpy.GetCount_management(outPS)).getOutput(0)
arcpy.AddMessage('There are %s ProtoSites' %numPS)

# Loop through the ProtoSites to create final ConSites
arcpy.AddMessage("Modifying individual ProtoSites to create final Conservation Sites...")
myProtoSites = arcpy.da.SearchCursor(outPS, ["SHAPE@"])
counter = 1

for myPS in myProtoSites:
   try:
      arcpy.AddMessage('Working on ProtoSite %s' % str(counter))
      
      psSHP = myPS[0]
      tmpPS = scratchGDB + os.sep + "tmpPS"
      arcpy.CopyFeatures_management (psSHP, tmpPS) 
      
      # Process: Select Layer By Location (Get SBBs within the ProtoSite)
      arcpy.AddMessage('Selecting SBBs within ProtoSite...')
      arcpy.SelectLayerByLocation_management("SBB_lyr", "INTERSECT", tmpPS, "", "NEW_SELECTION", "NOT_INVERT")
      
      # Process:  Copy the selected SBB features to tmpSBB
      tmpSBB = scratchGDB + os.sep + 'tmpSBB'
      arcpy.CopyFeatures_management ("SBB_lyr", tmpSBB)
      arcpy.AddMessage('Selected SBBs copied.')
      
      # Process: Select Layer By Location (Get PFs within the ProtoSite)
      arcpy.AddMessage('Selecting PFs within ProtoSite...')
      arcpy.SelectLayerByLocation_management("PF_lyr", "INTERSECT", tmpPS, "", "NEW_SELECTION", "NOT_INVERT")
      
      # Process:  Copy the selected PF features to tmpPF
      tmpPF = scratchGDB + os.sep + 'tmpPF'
      arcpy.CopyFeatures_management ("PF_lyr", tmpPF)
      arcpy.AddMessage('Selected PFs copied.')
      
      # Process:  Buffer (around the ProtoSite)
      arcpy.AddMessage('Buffering ProtoSite...')
      tmpBuff = scratchGDB + os.sep + 'tmpBuff'
      arcpy.Buffer_analysis (tmpPS, tmpBuff, buffDist, "", "", "", "")  
      
      # Process:  Clip (exclusion features to buffer)
      arcpy.AddMessage('Clipping ROW features to buffer...')
      rowClp = scratchGDB + os.sep + 'rowClp'
      arcpy.CleanClip_consiteTools (in_TranSurf, tmpBuff, rowClp, scratchParm)
      arcpy.AddMessage('Clipping hydro features to buffer...')
      hydroClp = scratchGDB + os.sep + 'hydroClp'
      arcpy.CleanClip_consiteTools (in_Hydro, tmpBuff, hydroClp, scratchParm)
      arcpy.AddMessage('Clipping Exclusion Features to buffer...')
      efClp = scratchGDB + os.sep + 'efClp'
      arcpy.CleanClip_consiteTools (in_Exclude, tmpBuff, efClp, scratchParm)
      
      # Process:  Get ROW Erase Features
      rowErase = scratchGDB + os.sep + 'rowErase'
      GetEraseFeats (rowClp, transQry, transElimDist, rowErase)
      
      # Process:  Cull Erase Features (from rowErase)
      arcpy.AddMessage('Culling ROW erase features...')
      rowRtn = scratchGDB + os.sep + 'rowRtn'
      CullEraseFeats (rowErase, tmpBuff, tmpPF, fld_SFID, transPerCov, rowRtn)
      
      # Process:  Get Hydro Erase Features
      hydroErase = scratchGDB + os.sep + 'hydroErase'
      GetEraseFeats (hydroClp, hydroQry, hydroElimDist, hydroErase)
      
      # Process:  Cull Erase Features (from hydroErase)
      arcpy.AddMessage('Culling hydro erase features...')
      hydroRtn = scratchGDB + os.sep + 'hydroRtn'
      CullEraseFeats (hydroErase, tmpBuff, tmpPF, fld_SFID, hydroPerCov, hydroRtn)
      
      # Process:  Merge (efClp, rowRtn, and hydroRtn)
      arcpy.AddMessage('Merging erase features...')
      tmpErase = scratchGDB + os.sep + 'tmpErase'
      arcpy.Merge_management ([efClp, rowRtn, hydroRtn], tmpErase) 
      
      # Process:  Clean Erase (Use tmpErase to chop out areas of SBBs)
      arcpy.AddMessage('Erasing portions of SBBs...')
      sbbFrags = scratchGDB + os.sep + 'sbbFrags'
      arcpy.CleanErase_consiteTools (tmpSBB, tmpErase, sbbFrags, scratchParm) 
      
      # Cull Fragments (remove any SBB fragments too far from a PF)
      arcpy.AddMessage('Culling SBB fragments...')
      sbbRtn = scratchGDB + os.sep + 'sbbRtn'
      CullFrags(sbbFrags, tmpPF, searchDist, sbbRtn)
      arcpy.MakeFeatureLayer_management(sbbRtn, "sbbRtn_lyr")
      
      # Process:  Clean Erase (Use tmpErase to chop out areas of ProtoSites)
      arcpy.AddMessage('Erasing portions of ProtoSites...')
      psFrags = scratchGDB + os.sep + 'psFrags'
      arcpy.CleanErase_consiteTools (psSHP, tmpErase, psFrags, scratchParm) 
      
      # Process:  Cull Fragments (remove any ProtoSite fragments too far from a PF)
      arcpy.AddMessage('Culling ProtoSite fragments...')
      psRtn = scratchGDB + os.sep + 'psRtn'
      CullFrags(psFrags, tmpPF, searchDist, psRtn)
      
      # Process:  Coalesce (re-merge split sites, if applicable
      coalFrags = scratchGDB + os.sep + 'coalFrags'
      arcpy.Coalesce_consiteTools(psRtn, coalDist, coalFrags, scratchParm)
      
      # Loop through the split, shrunken ProtoSites
      mySplitSites = arcpy.da.SearchCursor(coalFrags, ["SHAPE@"])
      counter2 = 1
      for mySS in mySplitSites:
         arcpy.AddMessage('Working on split site %s' % str(counter2))
         
         ssSHP = mySS[0]
         tmpSS = scratchGDB + os.sep + "tmpSS" + str(counter2)
         arcpy.CopyFeatures_management (ssSHP, tmpSS) 
         
         # Process:  Make Feature Layer
         arcpy.MakeFeatureLayer_management (tmpSS, "splitSiteLyr", "", "", "")
                  
         # Process: Select Layer By Location (Get PFs within split site)
         arcpy.SelectLayerByLocation_management("PF_lyr", "INTERSECT", tmpSS, "", "NEW_SELECTION", "NOT_INVERT")
         
         # Process:  Subset SBBs and PFs (select SBB fragments corresponding to tmpPF)
         tmpSBB2 = scratchGDB + os.sep + 'tmpSBB2' 
         tmpPF2 = scratchGDB + os.sep + 'tmpPF2'
         arcpy.SubsetSBBandPF_consiteTools(sbbRtn, "PF_lyr", "SBB", fld_SFID, tmpSBB2, tmpPF2)
         
         # Process:  ShrinkWrap
         csShrink = scratchGDB + os.sep + 'csShrink' + str(counter2)
         arcpy.ShrinkWrap_consiteTools(tmpSBB2, dilDist, csShrink, scratchParm)
         
         # Process:  Intersect 
         csInt = scratchGDB + os.sep + 'csInt' + str(counter2)
         arcpy.Intersect_analysis ([tmpSS, csShrink], csInt, "ONLY_FID") 
      
         # Process:  Union (to remove gaps within sites)
         csNoGap = scratchGDB + os. sep + 'csNoGap' + str(counter2)
         arcpy.Union_analysis (csInt, csNoGap, "ONLY_FID", "", "NO_GAPS")
         
         # Process:  Dissolve
         csDiss = scratchGDB + os.sep + 'csDissolved' + str(counter2)
         arcpy.Dissolve_management (csNoGap, csDiss, "", "", "SINGLE_PART") 
         
         # Process:  Cull Fragments (remove any fragments too far from a PF)
         csRtn = scratchGDB + os.sep + 'csRtn'
         CullFrags(csDiss, tmpPF2, searchDist, csRtn)
         
         # Process:  Coalesce (final smoothing of the site)  -- Is this even necessary??  Delete??
         csCoal = scratchGDB + os.sep + 'csCoal' + str(counter2)
         arcpy.Coalesce_consiteTools(csRtn, (coalDist), csCoal, scratchParm)
         
         # Process:  Clean Erase (final removal of exclusion features)
         arcpy.AddMessage('Excising manually delineated exclusion features...')
         csBnd = scratchGDB + os.sep + 'csBnd' + str(counter2)
         arcpy.CleanErase_consiteTools (csCoal, efClp, csBnd, scratchParm) 

         # Append the final geometry to the ConSites feature class.
         arcpy.AddMessage("Appending feature...")
         arcpy.Append_management(csBnd, out_ConSites, "NO_TEST", "", "")
         
         counter2 +=1
      
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
      
# Use the main function below to run CreateConSites function directly from Python IDE or command line with hard-coded variables
def main():
   # Set up variables
   in_SBB =  # Input Site Building Blocks
   ysn_Expand =  # Expand SBB selection?
   in_PF =  # Input Procedural Features
   fld_SFID =  # Source Feature ID field
   in_TranSurf =  # Input transportation surface features
   in_Hydro =  # Input open water features
   in_Exclude =  # Input delineated exclusion features
   in_ConSites =  # Current Conservation Sites; for template
   out_ConSites =  # Output new Conservation Sites
   scratchGDB =  # Workspace for temporary data
   # End of user input

   CreateConSites(in_SBB, ysn_Expand, in_PF, fld_SFID, in_TranSurf, in_Hydro, in_Exclude, in_ConSites, out_ConSites, scratchGDB)

if __name__ == '__main__':
   main()