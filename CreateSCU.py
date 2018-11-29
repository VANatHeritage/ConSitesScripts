# ----------------------------------------------------------------------------------------
# CreateSCU.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2018-11-05
# Last Edit: 2018-11-29
# Creator(s):  Kirsten R. Hazler

# Summary:
# Functions for delineating Stream Conservation Units (SCUs).

# Usage Tips:
# "It ain't perfect, but it's pretty good."

# Dependencies:
# This set of functions will not work if the hydro network is not set up properly! The network geodatabase VA_HydroNet.gdb has been set up manually, not programmatically.

# The Network Analyst extension is required for most functions, which will fail if the license is unavailable.

# Note that the restrictions (contained in "r" variable below) for traversing the network must have been defined in the HydroNet itself (manually). If any additional restrictions are added, the HydroNet must be rebuilt or they will not take effect. I originally set a restriction of NoEphemeralOrIntermittent, but on testing I discovered that this eliminated some stream segments that actually contained EOs. I set the restriction to NoEphemeral instead. We may find that we need to remove the NoEphemeral restriction as well, or that users will need to edit attributes of the NHDFlowline segments on a case-by-case basis.

# Syntax:  
# 
# ----------------------------------------------------------------------------------------

# Import modules
import Helper
from Helper import *
from arcpy.sa import *

def MakeServiceLayers_scu(in_hydroNet):
   '''Make two service layers needed for analysis.
   Parameters:
   - in_hydroNet = The hydro network dataset
   '''
   arcpy.CheckOutExtension("Network")
   
   # Set up some variables
   descHydro = arcpy.Describe(in_hydroNet)
   nwDataset = descHydro.catalogPath
   catPath = os.path.dirname(nwDataset) # This is where hydro layers will be found
   hydroDir = os.path.dirname(catPath)
   hydroDir = os.path.dirname(hydroDir) # This is where output layer files will be saved
   nwLines = catPath + os.sep + "NHDLine"
   qry = "FType = 343" # DamWeir only
   arcpy.MakeFeatureLayer_management (nwLines, "lyr_DamWeir", qry)
   in_Lines = "lyr_DamWeir"
   lyrDownTrace = hydroDir + os.sep + "naDownTrace.lyr"
   lyrUpTrace = hydroDir + os.sep + "naUpTrace.lyr"
   
   # Downstream trace with breaks at 1609 (1 mile) and 3218 (2 miles)
   # Upstream trace with break at 3218 (2 miles)
   r = "NoCanalDitches;NoConnectors;NoPipelines;NoUndergroundConduits;NoEphemeral;NoCoastline"
   printMsg('Creating upstream and downstream service layers...')
   for sl in [["naDownTrace", "1609, 3218", "FlowDownOnly"], ["naUpTrace", "3218", "FlowUpOnly"]]:
      restrictions = r + ";" + sl[2]
      serviceLayer = arcpy.MakeServiceAreaLayer_na(in_network_dataset=nwDataset,
         out_network_analysis_layer=sl[0], 
         impedance_attribute="Length", 
         travel_from_to="TRAVEL_FROM", 
         default_break_values=sl[1], 
         polygon_type="NO_POLYS", 
         merge="NO_MERGE", 
         nesting_type="RINGS", 
         line_type="TRUE_LINES_WITH_MEASURES", 
         overlap="NON_OVERLAP", 
         split="SPLIT", 
         excluded_source_name="", 
         accumulate_attribute_name="Length", 
         UTurn_policy="ALLOW_UTURNS", 
         restriction_attribute_name=restrictions, 
         polygon_trim="TRIM_POLYS", 
         poly_trim_value="100 Meters", 
         lines_source_fields="LINES_SOURCE_FIELDS", 
         hierarchy="NO_HIERARCHY", 
         time_of_day="")
   
   # Add dam barriers to both service layers and save
   printMsg('Adding dam barriers to service layers...')
   for sl in [["naDownTrace", lyrDownTrace], ["naUpTrace", lyrUpTrace]]:
      barriers = arcpy.AddLocations_na(in_network_analysis_layer=sl[0], 
         sub_layer="Line Barriers", 
         in_table=in_Lines, 
         field_mappings="Name Permanent_Identifier #", 
         search_tolerance="100 Meters", 
         sort_field="", 
         search_criteria="NHDFlowline SHAPE_MIDDLE_END;HydroNet_ND_Junctions NONE", 
         match_type="MATCH_TO_CLOSEST", 
         append="CLEAR", 
         snap_to_position_along_network="SNAP", 
         snap_offset="0 Meters", 
         exclude_restricted_elements="INCLUDE", 
         search_query="NHDFlowline #;HydroNet_ND_Junctions #")
         
      printMsg('Saving service layer to %s...' %sl[1])      
      arcpy.SaveToLayerFile_management(sl[0], sl[1]) 
      del barriers
      
   del serviceLayer
   
   arcpy.CheckInExtension("Network")
   
   return (lyrDownTrace, lyrUpTrace)

def MakeNetworkPts_scu(in_hydroNet, in_PF, out_Points, fld_SFID = "SFID", out_Scratch = arcpy.env.scratchGDB):
   '''Given SCU-worthy procedural features, creates points along the hydro network. 
   Parameters:
   - in_hydroNet = The hydro network dataset
   - in_PF = Input SCU-worthy procedural features
   - out_Points = Output feature class containing points generated from procedural features
   - fld_SFID = Field in in_PF containing unique ID
   - out_Scratch = geodatabase to contain intermediate products'''
   
   # timestamp
   t0 = datetime.now()
   
   # Set up some variables
   sr = arcpy.Describe(in_PF).spatialReference   
   descHydro = arcpy.Describe(in_hydroNet)
   nwDataset = descHydro.catalogPath
   catPath = os.path.dirname(nwDataset) # This is where hydro layers will be found
   nhdArea = catPath + os.sep + "NHDArea"
   nhdFlowline = catPath + os.sep + "NHDFlowline"
   pfCirc = out_Scratch + os.sep + 'pfCirc'
   
   # Variables used in-loop
   pfBuff = out_Scratch + os.sep + 'pfBuff'
   slopBuff = out_Scratch + os.sep + 'clpBuff'
   tmpPts = out_Scratch + os.sep + 'tmpPts'
   tmpPts2 = out_Scratch + os.sep + 'tmpPts2'
   attrib_Points = out_Scratch + os.sep + 'attrib_Points'
   clpArea = out_Scratch + os.sep + 'clpArea'
   clpLine = out_Scratch + os.sep + 'clpLine'
   # LineInArea = out_Scratch + os.sep + 'LineInArea'
      
   # Make some feature layers   
   qry = "FType in (460, 558)" # StreamRiver and ArtificialPath only
   arcpy.MakeFeatureLayer_management (nhdFlowline, "StreamRiver_Line", qry)
   qry = "FType = 460" # StreamRiver only
   arcpy.MakeFeatureLayer_management (nhdArea, "StreamRiver_Poly", qry)
   
   # Create bounding polygons around PFs
   printMsg('Creating bounding circles for procedural features...')
   arcpy.MinimumBoundingGeometry_management (in_PF, pfCirc, "CIRCLE", "NONE")
   
   # Create empty feature classes to store points
   printMsg('Creating empty feature classes for points')
   if arcpy.Exists(out_Points):
      arcpy.Delete_management(out_Points)
   outDir = os.path.dirname(out_Points)
   outName = os.path.basename(out_Points)
   arcpy.CreateFeatureclass_management (outDir, outName, "POINT", in_PF, '', '', sr)
   
   # This whole procedure is clunky but I think necessary b/c of spatial discrepancies between PFs and NHD features
   printMsg('Generating points on network...')
   with  arcpy.da.SearchCursor(in_PF, [fld_SFID]) as myPFs:
      for PF in myPFs:
         id = PF[0]
         printMsg('Working on SFID %s...' %id)
         
         # Create fresh feature class for storage
         if arcpy.Exists(attrib_Points):
            arcpy.Delete_management(attrib_Points)
         arcpy.CreateFeatureclass_management (out_Scratch, 'attrib_Points', "POINT", in_PF, '', '', sr)
         
         # Make feature layers
         qry = "%s = '%s'" % (fld_SFID, id)
         arcpy.MakeFeatureLayer_management (pfCirc,  "tmpCirc", qry)
         arcpy.MakeFeatureLayer_management (in_PF,  "tmpPF", qry)
         
         # Clip nhd layers
         CleanClip("StreamRiver_Line", "tmpCirc", clpLine)
         CleanClip("StreamRiver_Poly", "tmpCirc", clpArea)

         # Generate points on bounding circle; this ensures the length of the PF along the FlowLine network is captured, for all but perfect circular features
         ### First buffer PF by small amount to avoid some weird results for some features
         arcpy.Buffer_analysis("tmpPF", pfBuff, "1 Meters", "", "", "NONE")
         arcpy.Intersect_analysis ([pfBuff, "tmpCirc"], tmpPts, "", "", "POINT")
         c = countFeatures(tmpPts) # Check for empty output
         if c == 0: # Empty output if PF is a perfect circle; alternatives needed
            ### Make centroid
            arcpy.FeatureToPoint_management ("tmpPF", tmpPts, "CENTROID")
            arcpy.Append_management (tmpPts, attrib_Points, "NO_TEST")
            ### Make additional points for large circles
            arcpy.Intersect_analysis(["tmpPF", clpArea], tmpPts, "", "", "POINT")
            c = countFeatures(tmpPts) # Check for empty output
            if c > 0: 
               arcpy.MultipartToSinglepart_management (tmpPts, tmpPts2)
               arcpy.Append_management (tmpPts2, attrib_Points, "NO_TEST")
         else: # Finish processing normal generated points
            arcpy.MultipartToSinglepart_management (tmpPts, tmpPts2)
            arcpy.Append_management (tmpPts2, attrib_Points, "NO_TEST")
         
         # Get junctions with tributaries
         arcpy.Intersect_analysis([clpLine, "tmpPF"], tmpPts, "", "", "POINT")
         c = countFeatures(tmpPts) # Check for empty output
         if c > 0: # Trib junctions present within PF
            arcpy.MultipartToSinglepart_management (tmpPts, tmpPts2)
            arcpy.Append_management (tmpPts2, attrib_Points, "NO_TEST")
         else:
         ### Try using a "slop" buffer to account for discrepancies between PF and NHD
            arcpy.Buffer_analysis("tmpPF", pfBuff, "30 Meters", "", "", "NONE")
            CleanClip(pfBuff, "tmpCirc", slopBuff)
            arcpy.Intersect_analysis([clpLine, slopBuff], tmpPts, "", "", "POINT")
            c = countFeatures(tmpPts) # Check for empty output
            if c > 0: # Trib junctions present within slop buffer
               arcpy.MultipartToSinglepart_management (tmpPts, tmpPts2)
               arcpy.Append_management (tmpPts2, attrib_Points, "NO_TEST")

         arcpy.CalculateField_management (attrib_Points, fld_SFID, "%s" %id, 'PYTHON_9.3')
         arcpy.Append_management (attrib_Points, out_Points, "NO_TEST")

   if out_Scratch == "in_memory":
      # Clear out memory to avoid failures in subsequent functions
      arcpy.env.workspace = "in_memory"
      dataList = arcpy.ListDatasets()
      for item in dataList:
         try:
            arcpy.Delete_management(item)
            printMsg('Deleted %s from memory.' % item)
         except:
            pass
   
   # timestamp
   t1 = datetime.now()
   ds = GetElapsedTime (t0, t1)
   printMsg('Completed function. Time elapsed: %s' % ds)
   
   return out_Points
   
def CreateLines_scu(out_Lines, in_Points, in_downTrace, in_upTrace, out_Scratch = arcpy.env.scratchGDB):
   '''Loads SCU points, solves the upstream and downstream service layers, and combines segments to create linear SCUs
   Parameters:
   - out_Lines = Final output linear SCUs
   - in_Points = Input feature class containing points generated from procedural features
   - in_downTrace = Service layer set up to run downstream
   - in_upTrace = Service layer set up to run upstream
   - out_Scratch = geodatabase to contain intermediate products'''
   
   arcpy.CheckOutExtension("Network")
   
   # timestamp
   t0 = datetime.now()
   
   # Set up some variables
   if out_Scratch == "in_memory":
      # recast to save to disk, otherwise there is no OBJECTID field for queries as needed
      outScratch = arcpy.env.scratchGDB
   printMsg('Casting strings to layer objects...')
   in_upTrace = arcpy.mapping.Layer(in_upTrace)
   in_downTrace = arcpy.mapping.Layer(in_downTrace)
   descDT = arcpy.Describe(in_downTrace)
   nwDataset = descDT.network.catalogPath
   catPath = os.path.dirname(nwDataset) # This is where hydro layers will be found
   hydroDir = os.path.dirname(catPath)
   hydroDir = os.path.dirname(hydroDir) # This is where output layer files will be saved
   lyrDownTrace = hydroDir + os.sep + 'naDownTrace.lyr'
   lyrUpTrace = hydroDir + os.sep + 'naUpTrace.lyr'
   downLines = out_Scratch + os.sep + 'downLines'
   upLines = out_Scratch + os.sep + 'upLines'
   outDir = os.path.dirname(out_Lines)
  
   # Load all points as facilities into both service layers; search distance 500 meters
   printMsg('Loading points into service layers...')
   for sa in [[in_downTrace,lyrDownTrace], [in_upTrace, lyrUpTrace]]:
      inLyr = sa[0]
      outLyr = sa[1]
      naPoints = arcpy.AddLocations_na(in_network_analysis_layer=inLyr, 
         sub_layer="Facilities", 
         in_table=in_Points, 
         field_mappings="Name FID #", 
         search_tolerance="500 Meters", 
         sort_field="", 
         search_criteria="NHDFlowline SHAPE;HydroNet_ND_Junctions NONE", 
         match_type="MATCH_TO_CLOSEST", 
         append="CLEAR", 
         snap_to_position_along_network="SNAP", 
         snap_offset="0 Meters", 
         exclude_restricted_elements="EXCLUDE", 
         search_query="NHDFlowline #;HydroNet_ND_Junctions #")
   printMsg('Completed point loading.')
   
   del naPoints
  
   # Solve upstream and downstream service layers; save out lines and updated layers
   for sa in [[in_downTrace, downLines, lyrDownTrace], [in_upTrace, upLines, lyrUpTrace]]:
      inLyr = sa[0]
      outLines = sa[1]
      outLyr = sa[2]
      printMsg('Solving service area for %s...' % inLyr)
      arcpy.Solve_na(in_network_analysis_layer=inLyr, 
         ignore_invalids="SKIP", 
         terminate_on_solve_error="TERMINATE", 
         simplification_tolerance="")
      inLines = arcpy.mapping.ListLayers(inLyr, "Lines")[0]
      printMsg('Saving out lines...')
      arcpy.CopyFeatures_management(inLines, outLines)
      arcpy.RepairGeometry_management (outLines, "DELETE_NULL")
      printMsg('Saving updated %s service layer to %s...' %(inLyr,outLyr))      
      arcpy.SaveToLayerFile_management(inLyr, outLyr)
   
   # Make feature layers for downstream lines
   qry = "ToCumul_Length <= 1609" 
   arcpy.MakeFeatureLayer_management (downLines, "downLTEbreak", qry)
   qry = "ToCumul_Length > 1609"
   arcpy.MakeFeatureLayer_management (downLines, "downGTbreak", qry)
   
   # Merge the downstream segments <= 1609 with the upstream segments
   printMsg('Merging primary segments...')
   mergedLines = out_Scratch + os.sep + 'mergedLines'
   arcpy.Merge_management (["downLTEbreak", upLines], mergedLines)
   
   # Erase downstream segments > 1609 that overlap the merged segments
   printMsg('Erasing irrelevant downstream extension segments...')
   erasedLines = out_Scratch + os.sep + 'erasedLines'
   arcpy.Erase_analysis ("downGTbreak", mergedLines, erasedLines)
   
   # Dissolve (on Facility ID, allowing multiparts) the remaining downstream segments > 1609
   printMsg('Dissolving remaining downstream extension segments...')
   dissolvedLines = out_Scratch + os.sep + 'dissolvedLines'
   arcpy.Dissolve_management(erasedLines, dissolvedLines, "FacilityID", "", "SINGLE_PART", "DISSOLVE_LINES")
   
   # From dissolved segments, select only those intersecting 2+ merged downstream/upstream segments
   ### Conduct nearest neighbor analysis with zero distance (i.e. touching)
   printMsg('Analyzing adjacency of extension segments to primary segments...')
   nearTab = out_Scratch + os.sep + 'nearTab'
   arcpy.GenerateNearTable_analysis(dissolvedLines, mergedLines, nearTab, "0 Meters", "NO_LOCATION", "NO_ANGLE", "ALL", "2", "PLANAR")
   
   #### Find out if segment touches at least two neighbors
   printMsg('Counting neighbors...')
   countTab = out_Scratch + os.sep + 'countTab'
   arcpy.Statistics_analysis(nearTab, countTab, "NEAR_FID COUNT", "IN_FID")
   qry = "FREQUENCY = 2"
   arcpy.MakeTableView_management(countTab, "connectorTab", qry)
   
   ### Get list of segments meeting the criteria, cast as a query and make feature layer
   printMsg('Extracting extension segments with at least two primary neighbors...')
   valList = unique_values("connectorTab", "IN_FID")
   if len(valList) > 0:
      qryList = str(valList)
      qryList = qryList.replace('[', '(')
      qryList = qryList.replace(']', ')')
      qry = "OBJECTID in %s" % qryList
   else:
      qry = "OBJECTID = -1"
   arcpy.MakeFeatureLayer_management (dissolvedLines, "extendLines", qry)
   
   # Merge and dissolve the connected segments; ESRI does not make this simple
   printMsg('Merging primary segments with selected extension segments...')
   comboLines = out_Scratch + os.sep + 'comboLines'
   arcpy.Merge_management (["extendLines", mergedLines], comboLines)
   
   printMsg('Buffering segments...')
   buffLines = out_Scratch + os.sep + 'buffLines'
   arcpy.Buffer_analysis(comboLines, buffLines, "1 Meters", "FULL", "ROUND", "ALL") 
   
   printMsg('Exploding buffers...')
   explBuff = outDir + os.sep + 'explBuff'
   arcpy.MultipartToSinglepart_management(buffLines, explBuff)
   
   printMsg('Grouping segments...')
   arcpy.AddField_management(explBuff, "grpID", "LONG")
   arcpy.CalculateField_management(explBuff, "grpID", "!OBJECTID!", "PYTHON")
   
   joinLines = out_Scratch + os.sep + 'joinLines'
   fldMap = 'grpID "grpID" true true false 4 Long 0 0, First, #, %s, grpID, -1, -1' % explBuff
   arcpy.SpatialJoin_analysis(comboLines, explBuff, joinLines, "JOIN_ONE_TO_ONE", "KEEP_ALL", fldMap, "INTERSECT")
   
   printMsg('Dissolving segments by group...')
   arcpy.Dissolve_management(joinLines, out_Lines, "grpID", "", "MULTI_PART", "DISSOLVE_LINES")
   
   # timestamp
   t1 = datetime.now()
   ds = GetElapsedTime (t0, t1)
   printMsg('Completed function. Time elapsed: %s' % ds)

   arcpy.CheckInExtension("Network")
   
   return (out_Lines, lyrDownTrace, lyrUpTrace)
   
def CreatePolys_scu(in_Lines, in_hydroNet, out_Polys, out_Scratch = arcpy.env.scratchGDB):
   '''Converts linear SCUs to polygons, including associated NHD StreamRiver polygons
   Parameters:
   - in_Lines = input linear SCUs, output from previous function
   - in_hydroNet = The hydro network dataset
   - out_Polys = output polygon SCUs
   - out_Scratch = geodatabase to contain intermediate products
   '''
   
   # timestamp
   t0 = datetime.now()
   
   # Create empty feature class to store polygons
   sr = arcpy.Describe(in_Lines).spatialReference
   appendPoly = out_Scratch + os.sep + 'appendPoly'
   printMsg('Creating empty feature class for polygons')
   if arcpy.Exists(appendPoly):
      arcpy.Delete_management(appendPoly)
   arcpy.CreateFeatureclass_management (out_Scratch, 'appendPoly', "POLYGON", in_Lines, '', '', sr)
   
   # Set up some variables:
   descHydro = arcpy.Describe(in_hydroNet)
   nwDataset = descHydro.catalogPath
   catPath = os.path.dirname(nwDataset) # This is where hydro layers will be found
   nhdArea = catPath + os.sep + "NHDArea"
   nhdFlowline = catPath + os.sep + "NHDFlowline"
   qry = "FType = 460" # StreamRiver only
   arcpy.MakeFeatureLayer_management (nhdArea, "StreamRiver", qry)
   
   # Variables used in-loop:
   bufferLines = out_Scratch + os.sep + 'bufferLines'
   danglePts = out_Scratch + os.sep + 'danglePts'
   bufferPts = out_Scratch + os.sep + 'bufferPts'
   mbgRect = out_Scratch + os.sep + 'mbgRect'
   bufferRect = out_Scratch + os.sep + 'bufferRect'
   clipRiver = out_Scratch + os.sep + 'clipRiver'
   clipLines = out_Scratch + os.sep + 'clipLines'
   perpLine1 = out_Scratch + os.sep + 'perpLine1'
   perpLine2 = out_Scratch + os.sep + 'perpLine2'
   perpLine = out_Scratch + os.sep + 'perpLine'
   perpClip = out_Scratch + os.sep + 'perpClip'
   splitPoly = out_Scratch + os.sep + 'splitPoly'
   mergePoly = out_Scratch + os.sep + 'mergePoly'
   tmpPoly = out_Scratch + os.sep + 'tmpPoly'
      
   with  arcpy.da.SearchCursor(in_Lines, ["SHAPE@", "grpID"]) as myLines:
      for line in myLines:
         shp = line[0]
         id = line[1]
         arcpy.env.Extent = shp
         
         printMsg('Working on %s...' % str(id))
         
         # Buffer linear SCU by at least half of cell size in flow direction raster (5 m)
         printMsg('Buffering linear SCU...')
         arcpy.Buffer_analysis(shp, bufferLines, "5 Meters", "", "FLAT")
         
         # Generate points at line ends
         printMsg('Generating split points...')
         arcpy.FeatureVerticesToPoints_management(shp, danglePts, "DANGLE") 
         arcpy.MakeFeatureLayer_management (danglePts, "danglePts")
         
         # Generate minimum convex polygon around line, buffer, and use to clip nhdArea
         printMsg('Generating minimum bounding rectangle and buffering...')
         arcpy.MinimumBoundingGeometry_management(shp, mbgRect, "RECTANGLE_BY_WIDTH")
         arcpy.Buffer_analysis(mbgRect, bufferRect, "20 Meters")
         printMsg('Clipping NHD to buffer...')
         CleanClip("StreamRiver", bufferRect, clipRiver)
         arcpy.MakeFeatureLayer_management (clipRiver, "clipRiver")

         # Select only the points within clipped StreamRiver polygons
         arcpy.SelectLayerByLocation_management("danglePts", "COMPLETELY_WITHIN", "clipRiver")
         c = countSelectedFeatures("danglePts")
         if c > 0:
            # Buffer points and use them to clip flowlines
            printMsg('Buffering split points...')
            arcpy.Buffer_analysis("danglePts", bufferPts, "1 Meters")
            printMsg('Clipping flowlines at split points...')
            CleanClip(nhdFlowline, bufferPts, clipLines)
            
            # Add geometry attributes to clipped segments
            printMsg('Adding geometry attributes...')
            arcpy.AddGeometryAttributes_management(clipLines, "CENTROID;LINE_BEARING")
            arcpy.AddField_management(clipLines, "PERP_BEARING1", "DOUBLE")
            arcpy.AddField_management(clipLines, "PERP_BEARING2", "DOUBLE")
            arcpy.AddField_management(clipLines, "DISTANCE", "DOUBLE")
            expression = "PerpBearing(!BEARING!)"
            code_block1='''def PerpBearing(bearing):
               p = bearing + 90
               if p > 360:
                  p -= 360
               return p'''
            code_block2='''def PerpBearing(bearing):
               p = bearing - 90
               if p < 0:
                  p += 360
               return p'''
            arcpy.CalculateField_management(clipLines, "PERP_BEARING1", expression, "PYTHON_9.3", code_block1)
            arcpy.CalculateField_management(clipLines, "PERP_BEARING2", expression, "PYTHON_9.3", code_block2)
            arcpy.CalculateField_management(clipLines, "DISTANCE", 500, "PYTHON_9.3")

            # Generate lines perpendicular to segment (is 500 m sufficient for all cases?)
            printMsg('Creating perpendicular lines at split points...')
            for l in [["PERP_BEARING1", perpLine1],["PERP_BEARING2", perpLine2]]:
               bearingFld = l[0]
               outLine = l[1]
               arcpy.BearingDistanceToLine_management(clipLines, outLine, "CENTROID_X", "CENTROID_Y", "DISTANCE", "METERS", bearingFld, "DEGREES", "GEODESIC", "", sr)
            arcpy.Merge_management ([perpLine1, perpLine2], perpLine)
            
            # Clip perpendicular lines to clipped StreamRiver
            CleanClip(perpLine, "clipRiver", perpClip)
            arcpy.MakeFeatureLayer_management (perpClip, "perpClip")
            
            # Select lines intersecting the point buffers
            arcpy.SelectLayerByLocation_management("perpClip", "INTERSECT", bufferPts, "", "NEW_SELECTION")
            
            # Select clipped StreamRiver polygons containing selected lines
            arcpy.SelectLayerByLocation_management("clipRiver", "CONTAINS", "perpClip", "", "NEW_SELECTION")
            
            # Use selected lines to split clipped StreamRiver polygons
            printMsg('Splitting river polygons with perpendiculars...')
            arcpy.FeatureToPolygon_management("perpClip;clipRiver", splitPoly)
            arcpy.MakeFeatureLayer_management (splitPoly, "splitPoly")
            
            # Select split StreamRiver polygons containing scuLines
            arcpy.SelectLayerByLocation_management("splitPoly", "CROSSED_BY_THE_OUTLINE_OF", shp, "", "NEW_SELECTION")
            arcpy.SelectLayerByLocation_management("splitPoly", "CONTAINS", shp, "", "ADD_TO_SELECTION")
            
            # Merge/dissolve polygons in with baseline buffered scuLines
            printMsg('Merging and dissolving shapes...')
            arcpy.Merge_management ([bufferLines, "splitPoly"], mergePoly)
            arcpy.Dissolve_management (mergePoly, tmpPoly, "", "", "SINGLE_PART")
            
         else:
            tmpPoly = bufferLines
            
         # Append to output
         printMsg('Appending shape to output...')
         arcpy.Append_management (tmpPoly, appendPoly, "NO_TEST")
         
   # Dissolve final output
   printMsg('Dissolving final shapes...')
   arcpy.Dissolve_management (appendPoly, out_Polys, "", "", "SINGLE_PART")
   
   # timestamp
   t1 = datetime.now()
   ds = GetElapsedTime (t0, t1)
   printMsg('Completed function. Time elapsed: %s' % ds)

   return out_Polys
   
def CreateFlowBuffers_scu(in_Polys, fld_ID, in_FlowDir, out_Polys, maxDist, dilDist = 'None', out_Scratch = 'in_memory'):
   '''Delineates buffers around polygon SCUs based on flow distance down to features (rather than straight distance)'''
   
   arcpy.CheckOutExtension("Spatial")
   
   # Get cell size and output spatial reference from in_FlowDir
   cellSize = (arcpy.GetRasterProperties_management(in_FlowDir, "CELLSIZEX")).getOutput(0)
   srRast = arcpy.Describe(in_FlowDir).spatialReference
   linUnit = srRast.linearUnitName
   printMsg('Cell size of flow direction raster is %s %ss' %(cellSize, linUnit))
   printMsg('Flow modeling is strongly dependent on cell size.')

   # Set environment setting and other variables
   arcpy.env.snapRaster = in_FlowDir
   (num, units, procDist) = multiMeasure(maxDist, 3)

   # Check if input features and input flow direction have same spatial reference.
   # If so, just make a copy. If not, reproject features to match raster.
   srFeats = arcpy.Describe(in_Polys).spatialReference
   if srFeats.Name == srRast.Name:
      printMsg('Coordinate systems for features and raster are the same. Copying...')
      arcpy.CopyFeatures_management (in_Polys, out_Polys)
   else:
      printMsg('Reprojecting features to match raster...')
      # Check if geographic transformation is needed, and handle accordingly.
      if srFeats.GCS.Name == srRast.GCS.Name:
         geoTrans = ""
         printMsg('No geographic transformation needed...')
      else:
         transList = arcpy.ListTransformations(srFeats,srRast)
         geoTrans = transList[0]
      arcpy.Project_management (in_Polys, out_Polys, srRast, geoTrans)

   # Add and calculate a field needed for raster conversion
   arcpy.AddField_management (out_Polys, 'rasterVal', 'SHORT')
   arcpy.CalculateField_management (out_Polys, 'rasterVal', '1', 'PYTHON_9.3')
      
   # Count features and report
   numFeats = countFeatures(out_Polys)
   printMsg('There are %s features to process.' % numFeats)
   
   # Variables used in loop
   trashList = [] # Empty list for trash collection
   tmpFeat = out_Scratch + os.sep + 'tmpFeat'
   srcRast = out_Scratch + os.sep + 'srcRast'
   procBuff = out_Scratch + os.sep + 'procBuff'
   clp_FlowDir = out_Scratch + os.sep + 'clp_FlowDir'
   clp_Watershed = out_Scratch + os.sep + 'clp_Watershed'
   snk_FlowDir = out_Scratch + os.sep + 'snk_FlowDir'
   FlowDist = out_Scratch + os.sep + 'FlowDist'
   clipBuff = out_Scratch + os.sep + 'clipBuff'
   clp_FlowDist = out_Scratch + os.sep + 'clp_FlowDist'
   binRast = out_Scratch + os.sep + 'binRast'
   cleanRast = out_Scratch + os.sep + 'cleanRast'
   prePoly = out_Scratch + os.sep + 'prePoly'
   finPoly = out_Scratch + os.sep + 'finPoly'
   coalescedPoly = out_Scratch + os.sep + 'coalPoly'
   multiPoly = out_Scratch + os.sep + 'multiPoly'
   
   # Create an empty list to store IDs of features that fail to get processed
   myFailList = []

   # Set up processing cursor and loop
   flags = [] # Initialize empty list to keep track of suspects
   cursor = arcpy.da.UpdateCursor(out_Polys, [fld_ID, "SHAPE@"])
   counter = 1
   for row in cursor:
      try:
         # Extract the unique ID and geometry object
         myID = row[0]
         myShape = row[1]

         printMsg('Working on feature %s with ID %s' % (counter, str(myID)))

         # Process:  Select (Analysis)
         # Create a temporary feature class including only the current feature
         selQry = "%s = %s" % (fld_ID, str(myID))
         arcpy.Select_analysis (out_Polys, tmpFeat, selQry)

         # Clip flow direction raster to processing buffer
         printMsg('Buffering feature to set maximum processing distance')
         arcpy.Buffer_analysis (tmpFeat, procBuff, procDist, "", "", "ALL", "")
         myExtent = str(arcpy.Describe(procBuff).extent).replace(" NaN", "")
         #printMsg('Extent: %s' %myExtent)
         printMsg('Clipping flow direction raster to processing buffer')
         arcpy.Clip_management (in_FlowDir, myExtent, clp_FlowDir, procBuff, "", "ClippingGeometry")
         arcpy.env.extent = clp_FlowDir
         arcpy.env.mask = clp_FlowDir
         
         # Convert feature to raster
         arcpy.PolygonToRaster_conversion (tmpFeat, 'rasterVal', srcRast, "MAXIMUM_COMBINED_AREA", 'rasterVal', cellSize)

         # Get the watershed for the SCU feature (truncated by processing buffer)
         printMsg('Creating truncated watershed from feature...')
         tmpRast = Watershed (clp_FlowDir, srcRast)
         tmpRast.save(clp_Watershed)
         arcpy.env.mask = clp_Watershed # Processing now restricted to Watershed
         
         # Burn SCU feature into flow direction raster as sink
         printMsg('Creating sink from feature...')
         tmpRast = Con(IsNull(srcRast),clp_FlowDir)
         tmpRast.save(snk_FlowDir)
         
         # Calculate flow distance down to sink
         printMsg('Within watershed, calculating flow distance to sink...')
         tmpRast = FlowLength (snk_FlowDir, "DOWNSTREAM")
         tmpRast.save(FlowDist)
         
         # Clip flow distance raster to the maximum distance buffer
         arcpy.Buffer_analysis (tmpFeat, clipBuff, maxDist, "", "", "ALL", "")
         myExtent = str(arcpy.Describe(clipBuff).extent).replace(" NaN", "")
         #printMsg('Extent: %s' %myExtent)
         printMsg('Clipping flow distance raster to maximum distance buffer')
         arcpy.Clip_management (FlowDist, myExtent, clp_FlowDist, clipBuff, "", "ClippingGeometry")
         arcpy.env.extent = clp_FlowDist
         
         # Make a binary raster based on flow distance
         printMsg('Creating binary raster from flow distance...')
         tmpRast = Con((IsNull(clp_FlowDist) == 1),
                  (Con((IsNull(srcRast)== 0),1,0)),
                  (Con((Raster(clp_FlowDist) <= num),1,0)))
         tmpRast.save(binRast)
         printMsg('Boundary cleaning...')
         tmpRast = BoundaryClean (binRast, 'NO_SORT', 'TWO_WAY')
         tmpRast.save(cleanRast)
         printMsg('Setting zeros to nulls...')
         tmpRast = SetNull (cleanRast, 1, 'Value = 0')
         tmpRast.save(prePoly)

         # Convert raster to polygon
         printMsg('Converting flow distance raster to polygon...')
         arcpy.RasterToPolygon_conversion (prePoly, finPoly, "NO_SIMPLIFY")

         # If user specifies, coalesce to smooth
         if dilDist == 'None':
            printMsg('Final shape will not be smoothed.')
            coalPoly = finPoly
         else:
            printMsg('Smoothing final shape...')
            coalPoly = coalescedPoly
            Coalesce(finPoly, dilDist, coalPoly, 'in_memory')
         
         # Check the number of features at this point. 
         # It should be just one. If more, the output is likely bad and should be flagged.
         count = countFeatures(coalPoly)
         if count > 1:
            printWrng('Output is suspect for feature %s' % str(myID))
            flags.append(myID)
            arcpy.Dissolve_management (coalPoly, multiPoly, "", "", "MULTI_PART")
            coalPoly = multiPoly
         
         # Use the flow distance buffer geometry as the final shape
         myFinalShape = arcpy.SearchCursor(coalPoly).next().Shape

         # Update the feature with its final shape
         row[1] = myFinalShape
         cursor.updateRow(row)
         del row 

         printMsg('Finished processing feature %s' %str(myID))

      except:
         # Add failure message and append failed feature ID to list
         printMsg("\nFailed to fully process feature " + str(myID))
         myFailList.append(myID)

         # Error handling code swiped from "A Python Primer for ArcGIS"
         tb = sys.exc_info()[2]
         tbinfo = traceback.format_tb(tb)[0]
         pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
         msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

         printWrng(msgs)
         printWrng(pymsg)
         printMsg(arcpy.GetMessages(1))

         # Add status message
         printMsg("\nMoving on to the next feature.  Note that the output will be incomplete.")
         
      finally:
         # Reset extent, because Arc is stupid.
         arcpy.env.extent = "MAXOF"
         
         # Update counter
         counter += 1
         
         # Grasping at straws here to avoid failure processing large datasets.
         if counter%25 == 0:
            printMsg('Compacting scratch geodatabase...')
            arcpy.Compact_management (out_Scratch)
   
   if len(flags) > 0:
      printWrng('These features may be incorrect: %s' % str(flags))
   if len(myFailList) > 0:
      printWrng('These features failed to process: %s' % str(myFailList))
      
   arcpy.CheckInExtension("Spatial")
   
   return out_Polys
   
# Use the main function below to run functions directly from Python IDE or command line with hard-coded variables
def main():
   in_hydroGDB = r'C:\Users\xch43889\Documents\Working\SCU\VA_HydroNet.gdb'
   # in_PF = r'C:\Users\xch43889\Documents\Working\SCU\testData.gdb\scuPFs'
   in_PF = r'C:\Users\xch43889\Documents\Working\SCU\testData.gdb\pfSet5'
   out_Points = r'C:\Users\xch43889\Documents\Working\SCU\testData.gdb\pfPoints_set5'
   out_Lines = r'C:\Users\xch43889\Documents\Working\SCU\testData.gdb\scuLines_set5'
   in_downTrace = r'C:\Users\xch43889\Documents\Working\SCU\naDownTrace.lyr'
   in_upTrace = r'C:\Users\xch43889\Documents\Working\SCU\naUpTrace.lyr'
   scratchGDB = r'C:\Users\xch43889\Documents\Working\SCU\scratch2.gdb'
   out_Polys = r'C:\Users\xch43889\Documents\Working\SCU\testData.gdb\scuPolys_set5'
   # End of user input

   # Function(s) to run
   # (downLyr, upLyr) = MakeServiceLayers_scu(in_GDB)
   # MakeNetworkPts_scu(in_PF, out_Points, "SFID", in_downTrace, in_upTrace, "in_memory")
   # CreateLines_scu(out_Lines, in_downTrace, in_upTrace, scratchGDB)
   CreatePolys_scu(out_Lines, in_hydroGDB, out_Polys, scratchGDB)
   
if __name__ == '__main__':
   main()
