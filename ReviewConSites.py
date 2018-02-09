# ---------------------------------------------------------------------------------------
# ReviewConSites.py
# Version:  ArcGIS 10.1 / Python 2.7
# Creation Date: 2016-06-07
# Last Edit: 2018-02-08
# Creator:  Kirsten R. Hazler
#
# Summary:
# Submits new (typically automated) Conservation Site features to a Quality Control procedure, comparing new to existing (old) shapes from the previous production cycle. 
# ---------------------------------------------------------------------------------------

# Import function libraries and settings
import libConSiteFx
from libConSiteFx import *

def ReviewConSites(auto_CS, orig_CS, cutVal, out_Sites, fld_SiteID = "SITEID", scratchGDB = arcpy.env.scratchWorkspace):
   '''# Submits new (typically automated) Conservation Site features to a Quality Control procedure, comparing new to existing (old) shapes  from the previous production cycle. It determines which of the following applies to the new site:
- N:  Site is new, not corresponding to any old site.
- I:  Site is identical to an old site.
- M:  Site is a merger of two or more old sites.
- S:  Site is one of several that split off from an old site.
- C:  Site is a combination of merger(s) and split(s)
- B:  Boundary change only.  Site corresponds directly to an old site, but the boundary has changed to some extent.

For the last group of sites (B), determines how much the boundary has changed.  A "PercDiff" field contains the percentage difference in area between old and new shapes.  The area that differs is determined by ArcGIS's Symmetrical Difference tool.  The user specifies a threshold beyond which the difference is deemed "significant".  (I recommend 10% change as the cutoff).

Finally, adds additional fields for QC purposes, and flags records that should be examined by a human (all N, M, and S sites, plus and B sites with change greater than the threshold).

In the output feature class, the output geometry is identical to the input new Conservation Sites features, but attributes have been added for QC purposes.  The addeded attributes are as follows:
- ModType:  Text field indicating how the site has been modified, relative to existing old sites.  Values are "N". "M", "S", "I", or "B" as described above.
- PercDiff:  Numeric field indicating the percent difference between old and new boundaries, as described above.  Applies only to sites where ModType = "B".
- AssignID:  Long integer field containing the old SITEID associated with the new site.  This field is automatically populated only for sites where ModType is "B" or "I".  For other sites, the ID should be manually assigned during site review.  Attributes associated with this ID may be transferred, in whole or in part, from the old site to the new site.  
- Flag:  Short integer field indicating whether the new site needs to be examined by a human (1) or not (0).  All sites where ModType is "N", "M", or "S" are flagged automatically.  Sites where ModType = "B" are flagged if the value in the PercDiff field is greater than the user-specified threshold.
- Comment:  Text field to be used by site reviewers to enter comments.  Nothing is entered automatically.

User inputs:
- auto_CS: new (typically automated) Conservation Site feature class
- orig_CS: old Conservation Site feature class for comparison (the one currently in Biotics)
- cutVal: a cutoff percentage that will be used to flag features that represent significant boundary growth or reduction(e.g., 10%)
- out_Sites: output new Conservation Sites feature class with QC information
- fld_SiteID: the unique site ID field in the old CS feature class
- scratchGDB: scratch geodatabase for intermediate products'''

   # Determine how many old sites are overlapped by each automated site.  Automated sites provide the output geometry
   printMsg("Performing first spatial join...")
   Join1 = scratchGDB + os.sep + "Join1"
   fldmap = "Shape_Length \"Shape_Length\" false true true 8 Double 0 0 ,First,#,auto_CS,Shape_Length,-1,-1;Shape_Area \"Shape_Area\" false true true 8 Double 0 0 ,First,#,auto_CS,Shape_Area,-1,-1"
   arcpy.SpatialJoin_analysis(auto_CS, orig_CS, Join1, "JOIN_ONE_TO_ONE", "KEEP_ALL", fldmap, "INTERSECT", "", "")

   # Get the new sites.
   # These are automated sites with no corresponding old site
   printMsg("Separating out brand new sites...")
   NewSites = scratchGDB + os.sep + "NewSites"
   arcpy.Select_analysis(Join1, NewSites, "Join_Count = 0")

   # Get the single and split sites.
   # These are sites that overlap exactly one old site each. This may be a one-to-one correspondence or a split.
   printMsg("Separating out sites that may be singles or splits...")
   ssSites = scratchGDB + os.sep + "ssSites"
   arcpy.Select_analysis(Join1, ssSites, "Join_Count = 1")
   arcpy.MakeFeatureLayer_management(ssSites, "ssLyr")

   # Get the merger sites.
   # These are sites overlapping multiple old sites. Some may be pure merges, others combo merge/split sites.
   printMsg("Separating out merged sites...")
   mSites = scratchGDB + os.sep + "mSites"
   arcpy.Select_analysis(Join1, mSites, "Join_Count > 1")
   arcpy.MakeFeatureLayer_management(mSites, "mergeLyr")

   # Process: Remove extraneous fields as needed
   for tbl in [NewSites, ssSites, mSites]:
      for fld in ["Join_Count", "TARGET_FID"]:
         try:
            arcpy.DeleteField_management (tbl, fld)
         except:
            pass

   # Determine how many automated sites are overlapped by each old site.  Old sites provide the output geometry
   printMsg("Performing second spatial join...")
   Join2 = scratchGDB + os.sep + "Join2"
   arcpy.SpatialJoin_analysis(orig_CS, auto_CS, Join2, "JOIN_ONE_TO_ONE", "KEEP_COMMON", fldmap, "INTERSECT", "", "")
   arcpy.JoinField_management (Join2, "TARGET_FID", orig_CS, "OBJECTID", "%s" %fld_SiteID)

   # Make separate layers for old sites that were or were not split
   arcpy.MakeFeatureLayer_management(Join2, "NoSplitLyr", "Join_Count = 1")
   arcpy.MakeFeatureLayer_management(Join2, "SplitLyr", "Join_Count > 1")

   # Get the single sites (= no splits, no merges; one-to-one relationship with old sites)
   printMsg("Separating out single sites...")
   arcpy.SelectLayerByLocation_management("ssLyr", "INTERSECT", "NoSplitLyr", "", "NEW_SELECTION", "NOT_INVERT")
   SingleSites = scratchGDB + os.sep + "SingleSites"
   arcpy.CopyFeatures_management("ssLyr", SingleSites, "", "0", "0", "0")

   # Get the old site IDs to attach to SingleSites.  SingleSites provide the output geometry
   printMsg("Performing third spatial join...")
   Join3 = scratchGDB + os.sep + "Join3"
   arcpy.SpatialJoin_analysis(SingleSites, orig_CS, Join3, "JOIN_ONE_TO_ONE", "KEEP_COMMON", "", "INTERSECT", "", "")
   arcpy.JoinField_management (SingleSites, "OBJECTID", Join3, "TARGET_FID", "%s" %fld_SiteID) 

   # Save out the single sites that are identical to old sites
   arcpy.MakeFeatureLayer_management(SingleSites, "SingleLyr")
   printMsg("Separating out single sites that are identical to old sites...")
   arcpy.SelectLayerByLocation_management("SingleLyr", "ARE_IDENTICAL_TO", orig_CS, "", "NEW_SELECTION", "NOT_INVERT")
   IdentSites = scratchGDB + os.sep + "IdentSites"
   arcpy.CopyFeatures_management("SingleLyr", IdentSites, "", "0", "0", "0")

   # Save out the single sites that are NOT identical to old sites
   printMsg("Separating out single sites where boundaries have changed...")
   arcpy.SelectLayerByAttribute_management("SingleLyr", "SWITCH_SELECTION", "")
   BndChgSites = scratchGDB + os.sep + "BndChgSites"
   arcpy.CopyFeatures_management("SingleLyr", BndChgSites, "", "0", "0", "0")
   
   # Save out the split sites
   printMsg("Separating out split sites...")
   arcpy.SelectLayerByAttribute_management("ssLyr", "SWITCH_SELECTION", "")
   SplitSites = scratchGDB + os.sep + "SplitSites"
   arcpy.CopyFeatures_management("ssLyr", SplitSites, "", "0", "0", "0")
   
   # Save out the combo merger sites (those that also involve splits)
   printMsg("Separating out combo merger sites...")
   arcpy.SelectLayerByLocation_management("mergeLyr", "INTERSECT", "SplitLyr", "", "NEW_SELECTION", "NOT_INVERT")
   ComboSites = scratchGDB + os.sep + "ComboSites"
   arcpy.CopyFeatures_management("mergeLyr", ComboSites, "", "0", "0", "0")
   
   # Save out the simple merger sites (no splits)
   printMsg("Separating out simple merger sites...")
   arcpy.SelectLayerByAttribute_management("mergeLyr", "SWITCH_SELECTION", "")
   MergeSites = scratchGDB + os.sep + "MergeSites"
   arcpy.CopyFeatures_management("mergeLyr", MergeSites, "", "0", "0", "0")

   # Process:  Add Fields; Calculate Fields
   printMsg("Calculating fields...")
   for tbl in [(NewSites, "N"), (MergeSites, "M"), (ComboSites, "C"), (SplitSites, "S"), (IdentSites, "I"), (BndChgSites, "B")]: 
      for fld in [("ModType", "TEXT", 1), ("PercDiff", "DOUBLE", ""), ("AssignID", "TEXT", 40), ("Flag", "SHORT", ""), ("Comment", "TEXT", 250)]:
         arcpy.AddField_management (tbl[0], fld[0], fld[1], "", "", fld[2]) 
      arcpy.CalculateField_management (tbl[0], "ModType", '"%s"' %tbl[1], "PYTHON") 
      CodeBlock = """def Flag(ModType):
         if ModType in ("N", "M", "C", "S", "B"):
            flg = 1
         else:
            flg = 0
         return flg"""
      Expression = "Flag(!ModType!)"
      arcpy.CalculateField_management (tbl[0], "Flag", Expression, "PYTHON", CodeBlock) 
      
   for tbl in [IdentSites, BndChgSites]:
      arcpy.CalculateField_management (tbl, "AssignID", "!%s!" %fld_SiteID, "PYTHON") 
      arcpy.DeleteField_management (tbl, "%s" %fld_SiteID) 
      
   # Loop through the individual Boundary Change sites and check for amount of change
   myIndex = 1 # Set a counter index
   printMsg("Examining boundary changes for boundary change only sites...")
   with arcpy.da.UpdateCursor(BndChgSites, ["AssignID", "PercDiff", "Flag"]) as mySites: 
      for site in mySites: 
         try: # put all this in a TRY block so that even if one feature fails, script can proceed to next feature
            # Extract the unique ID from the data record
            myID = site[0]
            printMsg("\nWorking on Site ID %s" %myID)
            
            # Process:  Select (Analysis)
            # Create temporary feature classes including only the current new and old sites
            myWhereClause_AutoSites = '"AssignID" = \'%s\'' %myID
            tmpAutoSite = "in_memory" + os.sep + "tmpAutoSite"
            arcpy.Select_analysis (BndChgSites, tmpAutoSite, myWhereClause_AutoSites)
            tmpOldSite = "in_memory" + os.sep + "tmpOldSite"
            myWhereClause_OldSite = '"%s" = \'%s\'' %(fld_SiteID, myID)
            arcpy.Select_analysis (orig_CS, tmpOldSite, myWhereClause_OldSite)

            # Get the area of the old site
            OldArea = arcpy.SearchCursor(tmpOldSite).next().shape.area

            # Process:  Symmetrical Difference (Analysis)
            # Create features from the portions of the old and new sites that do NOT overlap
            tmpSymDiff = "in_memory" + os.sep + "tmpSymDiff"
            arcpy.SymDiff_analysis (tmpOldSite, tmpAutoSite, tmpSymDiff, "ONLY_FID", "")

            # Process:  Dissolve (Data Management)
            # Dissolve the Symmetrical Difference polygons into a single (multi-part) polygon
            tmpDissolve = "in_memory" + os.sep + "tmpDissolve"
            arcpy.Dissolve_management (tmpSymDiff, tmpDissolve, "", "", "", "")

            # Get the area of the difference shape
            DiffArea = arcpy.SearchCursor(tmpDissolve).next().shape.area

            # Calculate the percent difference from old shape, and set the value in the record
            PercDiff = 100*DiffArea/OldArea
            printMsg("The shapes differ by " + str(PercDiff) + " percent of original site area")
            site[1] = PercDiff

            # If the difference is greater than the cutoff, set the flag value to "Suspect", otherwise "Okay"
            if PercDiff > cutVal:
               printMsg("Shapes are significantly different; flagging record")
               site[2] = 1
            else:
               printMsg("Shapes are similar; unflagging record")
               site[2] = 0

            # Update the data table
            mySites.updateRow(site) 
         
         except:       
            # Add failure message
            printMsg("Failed to fully process feature " + str(myIndex))
            print "Failed to fully process feature " + str(myIndex)

            # Error handling code swiped from "A Python Primer for ArcGIS"
            tb = sys.exc_info()[2]
            tbinfo = traceback.format_tb(tb)[0]
            pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
            msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

            arcpy.AddError(msgs)
            arcpy.AddError(pymsg)
            printMsg(arcpy.GetMessages(1))

            print msgs
            print pymsg
            print printMsg(arcpy.GetMessages(1))

            # Add status message
            printMsg("\nMoving on to the next feature.  Note that the output will be incomplete.")
         
         finally:
            # Increment the index by one, and clear the in_memory workspace before returning to beginning of the loop
            myIndex += 1 
            arcpy.Delete_management("in_memory")

   # Process:  Merge
   printMsg("Merging sites into final feature class...")
   fcList = [NewSites, MergeSites, ComboSites, SplitSites, IdentSites, BndChgSites]
   arcpy.Merge_management (fcList, out_Sites) 
   
   return out_Sites
   
# Use the main function below to run ReviewConSites function directly from Python IDE or command line with hard-coded variables
def main():
   # Set up variables
   auto_CS = r'C:\Testing\cs20180129.gdb\ConSites_Final'
   orig_CS = r'C:\Users\xch43889\Documents\Working\ConSites\Biotics.gdb\ConSites_20180131_173111'
   cutVal = 10
   out_Sites = r'C:\Testing\cs20180129.gdb\ConSites_Final_QC'
   fld_SiteID = 'SITEID'
   scratchGDB = "C:\Testing\scratch20180208.gdb" # Workspace for temporary data
   # End of user input

   ReviewConSites(auto_CS, orig_CS, cutVal, out_Sites, fld_SiteID, scratchGDB)

if __name__ == '__main__':
   main()
