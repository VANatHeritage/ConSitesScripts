# ----------------------------------------------------------------------------------------
# libConSiteFx.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2017-08-08
# Last Edit: 2018-11-21
# Creator:  Kirsten R. Hazler

# Summary:
# A library of helper functions used to automatically delineate Natural Heritage Conservation Sites 

# ----------------------------------------------------------------------------------------

# Import modules
import Helper
from Helper import *
   
def Coalesce(inFeats, dilDist, outFeats, scratchGDB = "in_memory"):
   '''If a positive number is entered for the dilation distance, features are expanded outward by the specified distance, then shrunk back in by the same distance. This causes nearby features to coalesce. If a negative number is entered for the dilation distance, features are first shrunk, then expanded. This eliminates narrow portions of existing features, thereby simplifying them. It can also break narrow "bridges" between features that were formerly coalesced.'''
   
   # If it's a string, parse dilation distance and get the negative
   if type(dilDist) == str:
      origDist, units, meas = multiMeasure(dilDist, 1)
      negDist, units, negMeas = multiMeasure(dilDist, -1)
   else:
      origDist = dilDist
      meas = dilDist
      negDist = -1*origDist
      negMeas = negDist

   # Parameter check
   if origDist == 0:
      arcpy.AddError("You need to enter a non-zero value for the dilation distance")
      raise arcpy.ExecuteError   

   # Set parameters. Dissolve parameter depends on dilation distance.
   if origDist > 0:
      dissolve1 = "ALL"
      dissolve2 = "NONE"
   else:
      dissolve1 = "NONE"
      dissolve2 = "ALL"

   # Process: Buffer
   Buff1 = scratchGDB + os.sep + "Buff1"
   arcpy.Buffer_analysis(inFeats, Buff1, meas, "FULL", "ROUND", dissolve1, "", "PLANAR")

   # Process: Clean Features
   Clean_Buff1 = scratchGDB + os.sep + "CleanBuff1"
   CleanFeatures(Buff1, Clean_Buff1)

   # Process:  Generalize Features
   # This should prevent random processing failures on features with many vertices, and also speed processing in general
   arcpy.Generalize_edit(Clean_Buff1, "0.1 Meters")
   
   # Eliminate gaps
   # Added step due to weird behavior on some buffers
   Clean_Buff1_ng = scratchGDB + os.sep + "Clean_Buff1_ng"
   arcpy.EliminatePolygonPart_management (Clean_Buff1, Clean_Buff1_ng, "AREA", "900 SQUAREMETERS", "", "CONTAINED_ONLY")

   # Process: Buffer
   Buff2 = scratchGDB + os.sep + "NegativeBuffer"
   arcpy.Buffer_analysis(Clean_Buff1_ng, Buff2, negMeas, "FULL", "ROUND", dissolve2, "", "PLANAR")

   # Process: Clean Features to get final dilated features
   CleanFeatures(Buff2, outFeats)
      
   # Cleanup
   if scratchGDB == "in_memory":
      garbagePickup([Buff1, Clean_Buff1, Buff2])
      
   return outFeats
   
def ShrinkWrap(inFeats, dilDist, outFeats, smthMulti = 8, scratchGDB = "in_memory"):
   # Parse dilation distance, and increase it to get smoothing distance
   smthMulti = float(smthMulti)
   origDist, units, meas = multiMeasure(dilDist, 1)
   smthDist, units, smthMeas = multiMeasure(dilDist, smthMulti)

   # Parameter check
   if origDist <= 0:
      arcpy.AddError("You need to enter a positive, non-zero value for the dilation distance")
      raise arcpy.ExecuteError   

   #tmpWorkspace = arcpy.env.scratchGDB
   #arcpy.AddMessage("Additional critical temporary products will be stored here: %s" % tmpWorkspace)
   
   # Set up empty trashList for later garbage collection
   trashList = []

   # Declare path/name of output data and workspace
   drive, path = os.path.splitdrive(outFeats) 
   path, filename = os.path.split(path)
   myWorkspace = drive + path
   Output_fname = filename

   # Process:  Create Feature Class (to store output)
   arcpy.CreateFeatureclass_management (myWorkspace, Output_fname, "POLYGON", "", "", "", inFeats) 

   # Process:  Clean Features
   #cleanFeats = tmpWorkspace + os.sep + "cleanFeats"
   cleanFeats = scratchGDB + os.sep + "cleanFeats"
   CleanFeatures(inFeats, cleanFeats)
   trashList.append(cleanFeats)

   # Process:  Dissolve Features
   #dissFeats = tmpWorkspace + os.sep + "dissFeats"
   # Writing to disk in hopes of stopping geoprocessing failure
   #arcpy.AddMessage("This feature class is stored here: %s" % dissFeats)
   dissFeats = scratchGDB + os.sep + "dissFeats"
   arcpy.Dissolve_management (cleanFeats, dissFeats, "", "", "SINGLE_PART", "")
   trashList.append(dissFeats)

   # Process:  Generalize Features
   # This should prevent random processing failures on features with many vertices, and also speed processing in general
   arcpy.Generalize_edit(dissFeats, "0.1 Meters")

   # Process:  Buffer Features
   #arcpy.AddMessage("Buffering features...")
   #buffFeats = tmpWorkspace + os.sep + "buffFeats"
   buffFeats = scratchGDB + os.sep + "buffFeats"
   arcpy.Buffer_analysis (dissFeats, buffFeats, meas, "", "", "ALL")
   trashList.append(buffFeats)

   # Process:  Explode Multiparts
   #explFeats = tmpWorkspace + os.sep + "explFeats"
   # Writing to disk in hopes of stopping geoprocessing failure
   #arcpy.AddMessage("This feature class is stored here: %s" % explFeats)
   explFeats = scratchGDB + os.sep + "explFeats"
   arcpy.MultipartToSinglepart_management (buffFeats, explFeats)
   trashList.append(explFeats)

   # Process:  Get Count
   numWraps = (arcpy.GetCount_management(explFeats)).getOutput(0)
   arcpy.AddMessage('Shrinkwrapping: There are %s features after consolidation' %numWraps)

   # Loop through the exploded buffer features
   counter = 1
   with arcpy.da.SearchCursor(explFeats, ["SHAPE@"]) as myFeats:
      for Feat in myFeats:
         arcpy.AddMessage('Working on shrink feature %s' % str(counter))
         featSHP = Feat[0]
         tmpFeat = scratchGDB + os.sep + "tmpFeat"
         arcpy.CopyFeatures_management (featSHP, tmpFeat)
         trashList.append(tmpFeat)
         
         # Process:  Repair Geometry
         arcpy.RepairGeometry_management (tmpFeat, "DELETE_NULL")
         
         # Process:  Make Feature Layer
         arcpy.MakeFeatureLayer_management (dissFeats, "dissFeatsLyr", "", "", "")
         trashList.append("dissFeatsLyr")

         # Process: Select Layer by Location (Get dissolved features within each exploded buffer feature)
         arcpy.SelectLayerByLocation_management ("dissFeatsLyr", "INTERSECT", tmpFeat, "", "NEW_SELECTION")
         
         # Process:  Coalesce features (expand)
         coalFeats = scratchGDB + os.sep + 'coalFeats'
         Coalesce("dissFeatsLyr", smthMeas, coalFeats, scratchGDB)
         # Increasing the dilation distance improves smoothing and reduces the "dumbbell" effect.
         trashList.append(coalFeats)
         
         # Eliminate gaps
         noGapFeats = scratchGDB + os.sep + "noGapFeats"
         arcpy. EliminatePolygonPart_management (coalFeats, noGapFeats, "PERCENT", "", 99, "CONTAINED_ONLY")
         
         # Process:  Append the final geometry to the ShrinkWrap feature class
         arcpy.AddMessage("Appending feature...")
         arcpy.Append_management(noGapFeats, outFeats, "NO_TEST", "", "")
         
         counter +=1
         del Feat

   # Cleanup
   if scratchGDB == "in_memory":
      garbagePickup(trashList)
      
   return outFeats
   
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

def ExtractBiotics(BioticsPF, BioticsCS, outGDB):
   '''Extracts data from Biotics5 query layers for Procedural Features and Conservation Sites and saves to a file geodatabase.
   Note: this tool must be run from within a map document containing the relevant query layers.'''
   # Local variables:
   ts = datetime.now().strftime("%Y%m%d_%H%M%S") # timestamp
   
   # Inform user
   printMsg('This process can only be run in the foreground, and takes a few minutes...')

   # Process: Copy Features (ConSites)
   printMsg('Copying ConSites')
   outCS = outGDB + os.sep + 'ConSites_' + ts
   arcpy.CopyFeatures_management(BioticsCS, outCS)
   printMsg('Conservation Sites successfully exported to %s' %outCS)

   # Process: Copy Features (ProcFeats)
   printMsg('Copying Procedural Features')
   unprjPF = r'in_memory\unprjProcFeats'
   arcpy.CopyFeatures_management(BioticsPF, unprjPF)
   
   # Process: Project
   printMsg('Projecting ProcFeats features')
   outPF = outGDB + os.sep + 'ProcFeats_' + ts
   outCoordSyst = "PROJCS['NAD_1983_Virginia_Lambert',GEOGCS['GCS_North_American_1983',DATUM['D_North_American_1983',SPHEROID['GRS_1980',6378137.0,298.257222101]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Lambert_Conformal_Conic'],PARAMETER['False_Easting',0.0],PARAMETER['False_Northing',0.0],PARAMETER['Central_Meridian',-79.5],PARAMETER['Standard_Parallel_1',37.0],PARAMETER['Standard_Parallel_2',39.5],PARAMETER['Latitude_Of_Origin',36.0],UNIT['Meter',1.0]]"
   transformMethod = "WGS_1984_(ITRF00)_To_NAD_1983"
   inCoordSyst = "PROJCS['WGS_1984_Web_Mercator_Auxiliary_Sphere',GEOGCS['GCS_WGS_1984',DATUM['D_WGS_1984',SPHEROID['WGS_1984',6378137.0,298.257223563]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Mercator_Auxiliary_Sphere'],PARAMETER['False_Easting',0.0],PARAMETER['False_Northing',0.0],PARAMETER['Central_Meridian',0.0],PARAMETER['Standard_Parallel_1',0.0],PARAMETER['Auxiliary_Sphere_Type',0.0],UNIT['Meter',1.0]]"
   arcpy.Project_management(unprjPF, outPF, outCoordSyst, transformMethod, inCoordSyst, "PRESERVE_SHAPE", "")
   printMsg('Procedural Features successfully exported to %s' %outPF)

   # # Add layers to map after removing existing layers, if present
   # printMsg('Adding layers to map document')
   # mxd = arcpy.mapping.MapDocument("CURRENT")
   # dataFrame = arcpy.mapping.ListDataFrames(mxd, "*")[0] 
   # for lyr in ["Biotics_TerrSites", "Biotics_AHZSites", "Biotics_ProcFeats"]: 
      # try:
         # arcpy.mapping.RemoveLayer(dataFrame, lyr)
      # except: pass
      
   # addTerrSites = arcpy.mapping.Layer(outCS)
   # addTerrSites.name = "Biotics_TerrSites"
   # addTerrSites.definitionQuery = "SITE_TYPE = 'Conservation Site'"
   # arcpy.mapping.AddLayer(dataFrame, addTerrSites)

   # addAHZSites = arcpy.mapping.Layer(outCS)
   # addAHZSites.name = "Biotics_AHZSites"
   # addAHZSites.definitionQuery = "SITE_TYPE = 'Anthropogenic Habitat Zone'"
   # arcpy.mapping.AddLayer(dataFrame, addAHZSites)

   # addProcFeats = arcpy.mapping.Layer(outPF)
   # addProcFeats.name = "Biotics_ProcFeats"
   # addProcFeats.definitionQuery = "RULE NOT IN ( 'CAVE' , 'SCU' )"
   # arcpy.mapping.AddLayer(dataFrame, addProcFeats)
   
def SelectCopy(in_FeatLyr, selFeats, selDist, out_Feats):
   '''Selects features within specified distance of selection features, and copies to output.
   Input features to be selected must be a layer, not a feature class.
   NOTE: This does not seem to work with feature services. ESRI FAIL.'''
   # Select input features within distance of selection features
   arcpy.SelectLayerByLocation_management (in_FeatLyr, "WITHIN_A_DISTANCE", selFeats, selDist, "NEW_SELECTION", "NOT_INVERT")
   
   # Get the number of SELECTED features
   numSelected = countSelectedFeatures(in_FeatLyr)
   
   # Copy selected features to output
   if numSelected == 0:
      # Create an empty dataset
      fc = os.path.basename(out_Feats)
      gdb = os.path.dirname(out_Feats)
      geom = arcpy.Describe(in_Feats).shapeType
      CreateFeatureclass_management (gdb, fc, geom, in_Feats)
   else:
      arcpy.CopyFeatures_management (in_FeatLyr, out_Feats)
      
   return out_Feats
   
def subsetDataInputs(selFeats, out_GDB, selDist = "3000 METERS", nwi5 = None, nwi67 = None, nwi9 = None, hydro = None, cores = None, roads = None, rail = None, exclusions = None):
   '''Selects the subset of data inputs within specified distance of selection features, and copies them to the output geodatabase. Inputs must be feature layers, not feature classes.
   NOTE: This does not work with feature services. ESRI FAIL.'''
   outNames = {nwi5:"Wetlands_Rule5", nwi67:"Wetlands_Rule67", nwi9:"Wetlands_Rule9", hydro:"Hydro", cores:"Cores", roads:"Roads", rail:"Rail", exclusions:"Exclusions"}
   outLayers = []
   for fc in [nwi5, nwi67, nwi9, hydro, cores, roads, rail, exclusions]:
      if fc != None:
         out_Name = outNames[fc]
         out_Feats = out_GDB + os.sep + out_Name
         SelectCopy(fc, selFeats, selDist, out_Feats)
         arcpy.MakeFeatureLayer_management (out_Feats, out_Name)
         outLayers.append(out_Name)
         
   return outLayers
   
def  main():
   # Set up variables
   inFeats = r'C:\Users\xch43889\Documents\ArcGIS\Default.gdb\dissFeats_Elim'
   dilDist = '2000 METERS'
   outFeats = r'C:\Testing\scratch20180127.gdb\dissFeats_Elim_coalesce2k_ng'
   scratchGDB = r'C:\Testing\scratch20180127.gdb'
   
   # Call function
   Coalesce(inFeats, dilDist, outFeats, scratchGDB)

if __name__ == '__main__':
   main()
