# ----------------------------------------------------------------------------------------
# CreateConSites_ParamCntrl.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016-02-25 (Adapted from suite of ModelBuilder models)
# Last Edit: 2016-12-06
# Creator:  Kirsten R. Hazler

# Summary:
# Given a set of Site Building Blocks, corresponding Procedural Features, polygons delineating open water and road right-of-ways, and "Exclusion" features, creates a set of Conservation Sites.  Exclusion features are manually or otherwise delineated areas that are used to erase unsuitable areas from ProtoSites.  ***This tool version allows users to tweak parameters.

# Dependencies:
#     SubsetSBBandPF_consiteTools
#     CleanClip_consiteTools
#     CleanErase_consiteTools
#     Coalesce_consiteTools
#     ShrinkWrap_consiteTools

# Syntax:  
# FinalizeConSites_consiteTools(inSBB, ysnExpand, inPF, SFID, inTranSurf, inHydro, inExclude, inConSites, outConSites, scratchGDB, [multiple other parameters, see below])
# ----------------------------------------------------------------------------------------

# Import modules
import arcpy, os, sys, traceback

# Get path to toolbox, then import it
# Scenario 1:  script is in separate folder within folder holding toolbox
tbx1 = os.path.abspath(os.path.join(sys.argv[0],"../..", "consiteTools.tbx"))
# Scenario 2:  script is embedded in tool
tbx2 = os.path.abspath(os.path.join(sys.argv[0],"..", "consiteTools.tbx"))
if os.path.isfile(tbx1):
   arcpy.ImportToolbox(tbx1)
   arcpy.AddMessage("Toolbox location is %s" % tbx1)
elif os.path.isfile(tbx2):
   arcpy.ImportToolbox(tbx2)
   arcpy.AddMessage("Toolbox location is %s" % tbx2)
else:
   arcpy.AddError('Required toolbox not found.  Check script for errors.')

# Script arguments input by user:
# Primary arguments:
inSBB = arcpy.GetParameterAsText(0) # Input Site Building Blocks
ysnExpand = arcpy.GetParameterAsText(1) # Expand SBB selection?
inPF = arcpy.GetParameterAsText(2) # Input Procedural Features
SFID = arcpy.GetParameterAsText(3) # Source Feature ID field
inTranSurf = arcpy.GetParameterAsText(4) # Input transportation surface features
inHydro = arcpy.GetParameterAsText(5) # Input open water features
inExclude = arcpy.GetParameterAsText(6) # Input delineated exclusion features
inConSites = arcpy.GetParameterAsText(7) # Current Conservation Sites; for template
outConSites = arcpy.GetParameterAsText(8) # Output new Conservation Sites
scratchGDB = arcpy.GetParameterAsText(9) # Workspace for temporary data

# Secondary arguments, with defaults supplied.  Once procedures are finalized these can be removed from user's view.
selDist = arcpy.GetParameter (10) #1000
arcpy.AddMessage('Selection distance = %s' %selDist)
dilDist = arcpy.GetParameter(11) #250
arcpy.AddMessage('Dilation distance = %s' %dilDist)
inclDist = arcpy.GetParameter(12) #50
arcpy.AddMessage('Inclusion distance = %s' %inclDist)
hydroPerCov = arcpy.GetParameter(13) #25
arcpy.AddMessage('Hydro percent cover = %s' %hydroPerCov)
hydroQry = "Hydro = 1"
   # Expression used to select appropriate hydro features to create erase features
hydroElimDist = arcpy.GetParameter(14) #10
arcpy.AddMessage('Hydro elimination distance = %s' %hydroElimDist)
rowPerCov = arcpy.GetParameter(15) #50
arcpy.AddMessage('ROW percent cover = %s' %rowPerCov)
rowQry = "DCR_ROW_TYPE = 'IS' OR DCR_ROW_TYPE = 'PR'"
   # Expression used to select appropriate ROW features to create erase features
rowElimDist = arcpy.GetParameter(16) #10
arcpy.AddMessage('ROW elimination distance = %s' %rowElimDist)
buffDist = arcpy.GetParameter(17) #200
arcpy.AddMessage('Buffer distance = %s' %buffDist)
searchDist = arcpy.GetParameter(18) #0
   # Distance from PFs used to determine whether to cull SBB and ConSite fragments after ProtoSites have been split.
arcpy.AddMessage('Search distance = %s' %searchDist)
searchDist = str(searchDist) + ' METERS'
coalDist = arcpy.GetParameter(19) #25
arcpy.AddMessage('Coalesce distance = %s' %coalDist)

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
drive, path = os.path.splitdrive(outConSites) 
path, filename = os.path.split(path)
myWorkspace = drive + path
Output_CS_fname = filename
   
# Define some sub-routines
def GetEraseFeats (inFeats, selQry, elimDist, outEraseFeats):
   # Creates exclusion features from input hydro or ROW features
   # Process: Make Feature Layer (subset of selected features)
   arcpy.MakeFeatureLayer_management(inFeats, "Selected_lyr", selQry)

   # Process: Dissolve
   DissEraseFeats = scratchGDB + os.sep + 'DissEraseFeats'
   arcpy.Dissolve_management("Selected_lyr", DissEraseFeats, "", "", "SINGLE_PART")

   # Process: Coalesce
   CoalEraseFeats = scratchGDB + os.sep + 'CoalEraseFeats'
   arcpy.Coalesce_consiteTools(DissEraseFeats, -(elimDist), CoalEraseFeats, scratchParm)

   # Process: Clean Features
   arcpy.CleanFeatures_consiteTools(CoalEraseFeats, outEraseFeats)

def CullEraseFeats (inEraseFeats, inBnd, inPF, SFID, PerCov, outEraseFeats):
   # Culls exclusion features containing a significant percentage of any 
   # Procedural Features' area
   
   # Process:  Add Field (Erase ID) and Calculate
   arcpy.AddField_management (inEraseFeats, "eFID", "LONG")
   arcpy.CalculateField_management (inEraseFeats, "eFID", "!OBJECTID!", "PYTHON")
   
   # Process: Tabulate Intersection
   # This tabulates the percentage of each PF that is contained within each erase feature
   TabIntersect = scratchGDB + os.sep + "TabInter"
   arcpy.TabulateIntersection_analysis(inPF, SFID, inEraseFeats, TabIntersect, "eFID", "", "", "HECTARES")
   
   # Process: Summary Statistics
   # This tabulates the maximum percentage of ANY PF within each erase feature
   TabMax = scratchGDB + os.sep + "TabMax"
   arcpy.Statistics_analysis(TabIntersect, TabMax, "PERCENTAGE MAX", "eFID")
   
   # Process: Join Field
   # This joins the max percentage value back to the original erase features
   arcpy.JoinField_management(inEraseFeats, "eFID", TabMax, "eFID", "MAX_PERCENTAGE")
   
   # Process: Select
   # Any erase features containing a large enough percentage of a PF are discarded
   WhereClause = "MAX_PERCENTAGE < %s OR MAX_PERCENTAGE IS null" % PerCov
   selEraseFeats = scratchGDB + os.sep + 'selEraseFeats'
   arcpy.Select_analysis(inEraseFeats, selEraseFeats, WhereClause)
   
   # Process:  Clean Erase (Use inPF to chop out areas of remaining exclusion features)
   arcpy.CleanErase_consiteTools (selEraseFeats, inPF, outEraseFeats, scratchParm) 
   
def CullFrags (inFrags, inPF, searchDist, outFrags):
   # Culls SBB or ConSite fragments farther than specified search distance from 
   # Procedural Features
   
   # Process: Near
   arcpy.Near_analysis(inFrags, inPF, searchDist, "NO_LOCATION", "NO_ANGLE", "PLANAR")

   # Process: Make Feature Layer
   WhereClause = '"NEAR_FID" <> -1'
   arcpy.MakeFeatureLayer_management(inFrags, "Frags_lyr", WhereClause)

   # Process: Clean Features
   arcpy.CleanFeatures_consiteTools("Frags_lyr", outFrags)

# Process: If applicable, clear any selections on non-SBB inputs
for fc in [inPF, inTranSurf, inHydro, inExclude]:
   typeFC= (arcpy.Describe(fc)).dataType
   if typeFC == 'FeatureLayer':
      arcpy.SelectLayerByAttribute_management (fc, "CLEAR_SELECTION")
   
# Process: Make Feature Layer from PFs
arcpy.MakeFeatureLayer_management(inPF, "PF_lyr")   

# Set up output locations for subsets of SBBs and PFs to process
SBB_sub = myWorkspace + os.sep + 'SBB_sub'
PF_sub = myWorkspace + os.sep + 'PF_sub'

if ysnExpand == "true":
   # Process:  Expand SBB selection
   arcpy.AddMessage('Expanding the current SBB selection and making copies of the SBBs and PFs...')
   arcpy.ExpandSBBselection_consiteTools(inSBB, "PF_lyr", SFID, inConSites, selDist, SBB_sub, PF_sub)
else:
   # Process:  Subset PFs and SBBs
   arcpy.AddMessage('Using the current SBB selection and making copies of the SBBs and PFs...')
   arcpy.SubsetSBBandPF_consiteTools(inSBB, "PF_lyr", "PF", SFID, SBB_sub, PF_sub)

# Process: Make Feature Layers from inclusion features, and from subsets of PFs and SBBs
arcpy.MakeFeatureLayer_management(PF_sub, "PF_lyr") 
arcpy.MakeFeatureLayer_management(SBB_sub, "SBB_lyr") 

# Select by location:  inclusion features w/in dist of SBBs
arcpy.AddMessage('Selecting relevant inclusion features. These will be treated as additional SBBs when creating sites....')
search_distance = str(inclDist) + " METERS"

# Process:  Create Feature Class (to store ConSites)
arcpy.AddMessage("Creating ConSites features class to store output features...")
arcpy.CreateFeatureclass_management (myWorkspace, Output_CS_fname, "POLYGON", inConSites, "", "", inConSites) 

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
      arcpy.CleanClip_consiteTools (inTranSurf, tmpBuff, rowClp, scratchParm)
      arcpy.AddMessage('Clipping hydro features to buffer...')
      hydroClp = scratchGDB + os.sep + 'hydroClp'
      arcpy.CleanClip_consiteTools (inHydro, tmpBuff, hydroClp, scratchParm)
      arcpy.AddMessage('Clipping Exclusion Features to buffer...')
      efClp = scratchGDB + os.sep + 'efClp'
      arcpy.CleanClip_consiteTools (inExclude, tmpBuff, efClp, scratchParm)
      
      # Process:  Get ROW Erase Features
      rowErase = scratchGDB + os.sep + 'rowErase'
      GetEraseFeats (rowClp, rowQry, rowElimDist, rowErase)
      
      # Process:  Cull Erase Features (from rowErase)
      arcpy.AddMessage('Culling ROW erase features...')
      rowRtn = scratchGDB + os.sep + 'rowRtn'
      CullEraseFeats (rowErase, tmpBuff, tmpPF, SFID, rowPerCov, rowRtn)
      
      # Process:  Get Hydro Erase Features
      hydroErase = scratchGDB + os.sep + 'hydroErase'
      GetEraseFeats (hydroClp, hydroQry, hydroElimDist, hydroErase)
      
      # Process:  Cull Erase Features (from hydroErase)
      arcpy.AddMessage('Culling hydro erase features...')
      hydroRtn = scratchGDB + os.sep + 'hydroRtn'
      CullEraseFeats (hydroErase, tmpBuff, tmpPF, SFID, hydroPerCov, hydroRtn)
      
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
         arcpy.SubsetSBBandPF_consiteTools(sbbRtn, "PF_lyr", "SBB", SFID, tmpSBB2, tmpPF2)
         
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
         arcpy.Append_management(csBnd, outConSites, "NO_TEST", "", "")
         
         counter2 +=1
      
   except:
      # Error handling code swiped from "A Python Primer for ArcGIS"
      tb = sys.exc_info()[2]
      tbinfo = traceback.format_tb(tb)[0]
      pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
      msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

      arcpy.AddWarning(msgs)
      arcpy.AddWarning(pymsg)
      arcpy.AddMessage(arcpy.GetMessages(1))
   
   finally:
      counter +=1

# Clear memory
if scratchGDB == "in_memory":
   del scratchGDB















