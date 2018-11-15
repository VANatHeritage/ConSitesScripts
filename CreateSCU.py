# ----------------------------------------------------------------------------------------
# CreateSCU.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2018-11-05
# Last Edit: 2018-11-15
# Creator(s):  Kirsten R. Hazler

# Summary:
# Functions for delineating Stream Conservation Units (SCUs).

# Usage Tips:
# 

# Dependencies:
# This set of functions will not work if the hydro network is not set up properly! The network geodatabase VA_HydroNet.gdb has been set up manually, not programmatically.

# Syntax:  
# 
# ----------------------------------------------------------------------------------------

# Import modules
import arcpy
from arcpy.sa import *
import libConSiteFx
from libConSiteFx import *
import os, sys, datetime, traceback, gc

# Check out extension licenses
arcpy.CheckOutExtension("Network")
arcpy.CheckOutExtension("Spatial")

def MakeServiceLayers_scu(in_GDB):
   '''Make two service layers needed for analysis.
   Parameters:
   - in_GDB = The geodatabase containing the hydro network and associated features. 
   '''
   
   # Set up some variables
   out_Dir = os.path.dirname(in_GDB)
   nwDataset = in_GDB + os.sep + "HydroNet" + os.sep + "HydroNet_ND"
   nwLines = in_GDB + os.sep + "HydroNet" + os.sep + "NHDLine"
   where_clause = "FType = 343" # DamWeir only
   arcpy.MakeFeatureLayer_management (nwLines, "lyr_DamWeir", where_clause)
   in_Lines = "lyr_DamWeir"
   lyrDownTrace = out_Dir + os.sep + "naDownTrace.lyr"
   lyrUpTrace = out_Dir + os.sep + "naUpTrace.lyr"
   
   # Downstream trace with breaks at 1609 (1 mile) and 3218 (2 miles)
   # Upstream trace with break at 3218 (2 miles)
   r = "NoCanalDitches;NoConnectors;NoPipelines;NoUndergroundConduits;NoEphemeralOrIntermittent;NoCoastline"
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
   
   return (lyrDownTrace, lyrUpTrace)

def MakeNetworkPts_scu(in_PF, out_Points, fld_SFID = "SFID", in_downTrace = "naDownTrace", in_upTrace = "naUpTrace", out_Scratch = "in_memory"):
   '''Given SCU-worthy procedural features, creates points along the network, then loads them into service layers. 
   Parameters:
   - in_PF = Input SCU-worthy procedural features
   - out_Points = Output feature class containing points generated from procedural features
   - fld_SFID = Field in in_PF containing unique ID
   - in_downTrace = Service layer set up to run downstream
   - in_upTrace = Service layer set up to run upstream
   - out_Scratch = geodatabase to contain intermediate products'''
   
   # Set up some variables
   sr = arcpy.Describe(in_PF).spatialReference
   descDT = arcpy.Describe(in_downTrace)
   if descDT.dataType == 'Layer':
      in_downTrace = arcpy.mapping.Layer(in_downTrace)
      descDT = arcpy.Describe(in_downTrace)
   descUT = arcpy.Describe(in_upTrace)
   if descUT.dataType == 'Layer':
      in_upTrace = arcpy.mapping.Layer(in_upTrace)
      descUT = arcpy.Describe(in_upTrace)
   cp = descDT.network.catalogPath
   hydroNet = os.path.dirname(cp)
   nhdArea = hydroNet + os.sep + "NHDArea"
   nhdFlowline = hydroNet + os.sep + "NHDFlowline"
   outDir = os.path.dirname(hydroNet)
   outDir = os.path.dirname(outDir)
   lyrDownTrace = outDir + os.sep + 'naDownTrace.lyr'
   lyrUpTrace = outDir + os.sep + 'naUpTrace.lyr'
   pfCirc = out_Scratch + os.sep + 'pfCirc'
   pfBuff = out_Scratch + os.sep + 'pfBuff'
   tmpPts = out_Scratch + os.sep + 'tmpPts'
   tmpPts2 = out_Scratch + os.sep + 'tmpPts2'
   clpArea = out_Scratch + os.sep + 'clpArea'
      
   # Make some feature layers   
   arcpy.MakeFeatureLayer_management (nhdFlowline, "nhdfl")
   arcpy.MakeFeatureLayer_management (nhdArea, "nhda")
   
   # Create bounding circles around PFs
   printMsg('Creating bounding circles for procedural features...')
   arcpy.MinimumBoundingGeometry_management (in_PF, pfCirc, "CIRCLE", "NONE")
   
   # Create empty feature class to store points
   printMsg('Creating empty feature class for points')
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
         qry = "%s = '%s'" % (fld_SFID, id)
         arcpy.MakeFeatureLayer_management (pfCirc,  "tmpCirc", qry)
         arcpy.MakeFeatureLayer_management (in_PF,  "tmpPF", qry)
         arcpy.SelectLayerByLocation_management ("nhdfl", "INTERSECT", "tmpPF", "", "NEW_SELECTION")
         c = countSelectedFeatures("nhdfl")
         if c > 0:
            # Make points directly on network if possible
            arcpy.Intersect_analysis (["tmpPF", "nhdfl"], tmpPts, "", "", "POINT")
            arcpy.MultipartToSinglepart_management (tmpPts, tmpPts2)
            arcpy.Append_management (tmpPts2, out_Points, "NO_TEST")
         else:
            # Generate points on bounding circle
            # First buffer PF by small amount to avoid some weird results for some features
            arcpy.Buffer_analysis("tmpPF", pfBuff, "1 Meters", "", "", "NONE")
            arcpy.Intersect_analysis ([pfBuff, "tmpCirc"], tmpPts, "", "", "POINT")
            c = countFeatures(tmpPts) # Check for empty output and proceed accordingly
            if c == 0:
               # Empty output if PF is a perfect circle; generate centroid instead
               arcpy.FeatureToPoint_management ("tmpPF", tmpPts, "CENTROID")
               arcpy.Append_management (tmpPts, out_Points, "NO_TEST")
            else:
               arcpy.MultipartToSinglepart_management (tmpPts, tmpPts2)
               arcpy.Append_management (tmpPts2, out_Points, "NO_TEST")
            
         # If applicable, add points on nhdArea polygons
         # This catches some instances where the above didn't generate all needed points
         arcpy.SelectLayerByLocation_management ("nhda", "INTERSECT", "tmpPF", "", "NEW_SELECTION")
         c = countSelectedFeatures("nhda")
         if c > 0:
            arcpy.Clip_analysis ("nhda", "tmpCirc", clpArea)
            arcpy.Intersect_analysis ([clpArea, nhdFlowline], tmpPts, "", "", "POINT")
            arcpy.MultipartToSinglepart_management (tmpPts, tmpPts2)
            arcpy.Append_management (tmpPts2, out_Points, "NO_TEST")
         else:
            pass
     
   # Load all points as facilities into both service layers; search distance 500 meters
   printMsg('Loading points into service layers...')
   for sa in [[in_downTrace,lyrDownTrace], [in_upTrace, lyrUpTrace]]:
      inLyr = sa[0]
      outLyr = sa[1]
      naPoints = arcpy.AddLocations_na(in_network_analysis_layer=inLyr, 
         sub_layer="Facilities", 
         in_table=out_Points, 
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
      printMsg('Saving updated %s service layer to %s...' %(inLyr,outLyr))      
      arcpy.SaveToLayerFile_management(inLyr, outLyr)
   printMsg('Completed point loading.')
   
   del naPoints
   return (lyrDownTrace, lyrUpTrace)
   
def CreateLines_scu(out_Lines, in_downTrace = "naDownTrace", in_upTrace = "naUpTrace", out_Scratch = "in_memory"):
   '''Solves the upstream and downstream service layers, and combines segments to create linear SCUs
   Parameters:
   - in_downTrace = Service layer set up to run downstream
   - in_upTrace = Service layer set up to run upstream
   - out_Lines = Final output linear SCUs
   - out_Scratch = geodatabase to contain intermediate products'''
   
   # Set up some variables
   descDT = arcpy.Describe(in_downTrace)
   if descDT.dataType == 'Layer':
      in_downTrace = arcpy.mapping.Layer(in_downTrace)
      descDT = arcpy.Describe(in_downTrace)
   descUT = arcpy.Describe(in_upTrace)
   if descUT.dataType == 'Layer':
      in_upTrace = arcpy.mapping.Layer(in_upTrace)
      descUT = arcpy.Describe(in_upTrace)
   cp = descDT.network.catalogPath
   hydroNet = os.path.dirname(cp)
   # nhdArea = hydroNet + os.sep + "NHDArea"
   # nhdFlowline = hydroNet + os.sep + "NHDFlowline"
   outDir = os.path.dirname(hydroNet)
   outDir = os.path.dirname(outDir)
   lyrDownTrace = outDir + os.sep + 'naDownTrace.lyr'
   lyrUpTrace = outDir + os.sep + 'naUpTrace.lyr'
   downLines = out_Scratch + os.sep + 'downLines'
   upLines = out_Scratch + os.sep + 'upLines'
  
   # Solve upstream and downstream service layers; save out lines and updated layers
   for sa in [[in_downTrace,downLines, lyrDownTrace], [in_upTrace, upLines, lyrUpTrace]]:
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
      qry = ""
   arcpy.MakeFeatureLayer_management (dissolvedLines, "extendLines", qry)
   
   # Merge and dissolve the connected segments; ESRI does not make this simple
   printMsg('Merging primary segments with selected extension segments...')
   comboLines = out_Scratch + os.sep + 'comboLines'
   arcpy.Merge_management (["extendLines", mergedLines], comboLines)
   
   printMsg('Buffering segments...')
   buffLines = out_Scratch + os.sep + 'buffLines'
   arcpy.Buffer_analysis(comboLines, buffLines, "1 Meters", "FULL", "ROUND", "ALL") 
   
   printMsg('Exploding buffers...')
   explBuff = out_Scratch + os.sep + 'explBuff'
   arcpy.MultipartToSinglepart_management(buffLines, explBuff)
   
   printMsg('Grouping segments...')
   arcpy.AddField_management(explBuff, "grpID", "LONG")
   arcpy.CalculateField_management(explBuff, "grpID", "!OBJECTID!", "PYTHON")
   
   joinLines = out_Scratch + os.sep + 'joinLines'
   fldMap = 'grpID "grpID" true true false 4 Long 0 0, First, #, %s, grpID, -1, -1' % explBuff
   arcpy.SpatialJoin_analysis(comboLines, explBuff, joinLines, "JOIN_ONE_TO_ONE", "KEEP_ALL", fldMap, "INTERSECT")
   
   printMsg('Dissolving segments by group...')
   arcpy.Dissolve_management(joinLines, out_Lines, "grpID", "", "MULTI_PART", "DISSOLVE_LINES")
   
   printMsg('Mission accomplished')
   return out_Lines
   
   
def CreatePolys_scu():
   '''Converts linear SCUs to polygons, including associated NHD StreamRiver polygons'''
   # Generate endpoints of linear SCUs and get segment bearings
   # Eliminate endpoints not within StreamRiver polygons
   # Eliminate endpoints that are also starting points
   # For remaining points, generate lines perpendicular to segment
   # Buffer perpendiculars by small amount (1 m)
   # Use buffered perpendiculars to erase portions of StreamRiver polygons
   # Discard StreamRiver polygons not containing linear SCUs
   # Buffer linear SCUs by at least half of cell size in flow direction raster (5 m)
   # Merge buffered SCUs with retained StreamRiver polygons
   # Dissolve and assign IDs
   
def CreateCatchments_scu():
   '''Delineates buffers around polygon SCUs based on flow distance down to features (rather than straight distance)'''
   
# Use the main function below to run functions directly from Python IDE or command line with hard-coded variables
def main():
   in_GDB = r'C:\Users\xch43889\Documents\Working\SCU\VA_HydroNet.gdb'
   in_PF = r'C:\Users\xch43889\Documents\Working\SCU\testData.gdb\pfSet3'
   out_Points = r'C:\Users\xch43889\Documents\Working\SCU\testData.gdb\pfPoints'
   out_Lines = r'C:\Users\xch43889\Documents\Working\SCU\testData.gdb\scuLines'
   in_downTrace = r'C:\Users\xch43889\Documents\Working\SCU\naDownTrace.lyr'
   in_upTrace = r'C:\Users\xch43889\Documents\Working\SCU\naUpTrace.lyr'
   scratchGDB = r'C:\Users\xch43889\Documents\Working\SCU\scratch.gdb'
   # End of user input

   # Function(s) to run
   # (downLyr, upLyr) = MakeServiceLayers_scu(in_GDB)
   # MakeNetworkPts_scu(in_PF, out_Points, "SFID", in_downTrace, in_upTrace, "in_memory")
   CreateLines_scu(out_Lines, in_downTrace, in_upTrace, scratchGDB)
   
if __name__ == '__main__':
   main()
