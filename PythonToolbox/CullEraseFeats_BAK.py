def CullEraseFeats (inEraseFeats, inBnd, in_PF, fld_SFID, PerCov, outEraseFeats, scratchGDB = "in_memory"):
   '''For ConSite creation: Culls exclusion features containing a significant percentage of any 
Procedural Feature's area'''
   # Process:  Add Field (Erase ID) and Calculate
   arcpy.AddField_management (inEraseFeats, "eFID", "LONG")
   arcpy.CalculateField_management (inEraseFeats, "eFID", "!OBJECTID!", "PYTHON")
   
   # Process: Tabulate Intersection
   # This tabulates the percentage of each PF that is contained within each erase feature
   TabIntersect = scratchGDB + os.sep + "TabInter"
   arcpy.TabulateIntersection_analysis(in_PF, fld_SFID, inEraseFeats, TabIntersect, "eFID", "", "", "HECTARES")
   
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
   
   # Process:  Clean Erase (Use in_PF to chop out areas of remaining exclusion features)
   CleanErase(selEraseFeats, in_PF, outEraseFeats, scratchGDB)
   
   # Cleanup
   trashlist = [TabIntersect, TabMax]
   garbagePickup(trashlist)
   
   return outEraseFeats