### SLATED FOR DELETION; functions have been moved to CreateConSites.py

# ----------------------------------------------------------------------------------------
# CreateSCS.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2018-11-05
# Last Edit: 2020-06-15
# Creator(s):  Kirsten R. Hazler

# Summary:
# Functions for delineating Stream Conservation Sites (formerly Stream Conservation Units aka SCUs)

# Usage Tips:
# "It ain"t perfect, but it"s pretty good."

# Dependencies:
# This set of functions will not work if the hydro network is not set up properly! The network geodatabase VA_HydroNet.gdb has been set up manually, not programmatically.

# The Network Analyst extension is required for some functions, which will fail if the license is unavailable.
# ----------------------------------------------------------------------------------------

# Import modules
import Helper
from Helper import *

def MakeServiceLayers_scs(in_hydroNet, upDist = 3000, downDist = 500):
   """Creates two Network Analyst service layers needed for SCU delineation. This tool only needs to be run the first time you run the suite of SCU delineation tools. After that, the output layers can be reused repeatedly for the subsequent tools in the SCU delineation sequence.
   
   NOTE: The restrictions (contained in "r" variable) for traversing the network must have been defined in the HydroNet itself (manually). If any additional restrictions are added, the HydroNet must be rebuilt or they will not take effect. I originally set a restriction of NoEphemeralOrIntermittent, but on testing I discovered that this eliminated some stream segments that actually might be needed. I set the restriction to NoEphemeral instead. We may find that we need to remove the NoEphemeral restriction as well, or that users will need to edit attributes of the NHDFlowline segments on a case-by-case basis. I also previously included NoConnectors as a restriction, but in some cases I noticed with INSTAR data, it seems necessary to allow connectors, so I have removed that restriction. The NoCanalDitch exclusion was also removed, after finding some INSTAR sites on this type of flowline, and with CanalDitch immediately upstream.
   
   Parameters:
   - in_hydroNet = Input hydrological network dataset
   - upDist = The distance (in map units) to traverse upstream from a point along the network
   - downDist = The distance (in map units) to traverse downstream from a point along the network
   """
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
   downString = (str(downDist)).replace(".","_")
   upString = (str(upDist)).replace(".","_")
   lyrDownTrace = hydroDir + os.sep + "naDownTrace_%s.lyr"%downString
   lyrUpTrace = hydroDir + os.sep + "naUpTrace_%s.lyr"%upString
   r = "NoPipelines;NoUndergroundConduits;NoEphemeral;NoCoastline"
   
   printMsg("Creating upstream and downstream service layers...")
   for sl in [["naDownTrace", downDist, "FlowDownOnly"], ["naUpTrace", upDist, "FlowUpOnly"]]:
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
   printMsg("Adding dam barriers to service layers...")
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
         
      printMsg("Saving service layer to %s..." %sl[1])      
      arcpy.SaveToLayerFile_management(sl[0], sl[1]) 
      del barriers
      
   del serviceLayer
   
   arcpy.CheckInExtension("Network")
   
   return (lyrDownTrace, lyrUpTrace)

def MakeNetworkPts_scs(in_hydroNet, in_Catch, in_PF, out_Points):
   """Given a set of procedural features, creates points along the hydrological network. The user must ensure that the procedural features are "SCU-worthy."
   Parameters:
   - in_hydroNet = Input hydrological network dataset
   - in_Catch = Input catchments from NHDPlus
   - in_PF = Input Procedural Features
   - out_Points = Output feature class containing points generated from procedural features
   """
   
   # timestamp
   t0 = datetime.now()
   
   # Set up some variables
   sr = arcpy.Describe(in_PF).spatialReference   
   descHydro = arcpy.Describe(in_hydroNet)
   nwDataset = descHydro.catalogPath
   catPath = os.path.dirname(nwDataset) # This is where hydro layers will be found
   nhdFlowline = catPath + os.sep + "NHDFlowline"
   
   # Make feature layers  
   arcpy.MakeFeatureLayer_management (nhdFlowline, "lyr_Flowlines")
   arcpy.MakeFeatureLayer_management (in_Catch, "lyr_Catchments")
   
   # Select catchments intersecting PFs
   printMsg("Selecting catchments intersecting Procedural Features...")
   arcpy.SelectLayerByLocation_management ("lyr_Catchments", "INTERSECT", in_PF)
   
   # Buffer PFs by 30-m (standard slop factor) or by 250-m for wood turtles
   printMsg("Buffering Procedural Features...")
   code_block = """def buff(elcode):
      if elcode == "ARAAD02020":
         b = 250
      else:
         b = 30
      return b
      """
   expression = "buff(!ELCODE!)"
   arcpy.CalculateField_management (in_PF, "BUFFER", expression, "PYTHON", code_block)
   buff_PF = "in_memory" + os.sep + "buff_PF"
   arcpy.Buffer_analysis (in_PF, buff_PF, "BUFFER", "", "", "NONE")

   # Clip buffered PFs to selected catchments
   printMsg("Clipping buffered Procedural Features...")
   clipBuff_PF = "in_memory" + os.sep + "clipBuff_PF"
   arcpy.Clip_analysis (buff_PF, "lyr_Catchments", clipBuff_PF)
   
   # Select by location flowlines that intersect selected catchments
   printMsg("Selecting flowlines intersecting selected catchments...")
   arcpy.SelectLayerByLocation_management ("lyr_Flowlines", "INTERSECT", "lyr_Catchments")
   
   # Clip selected flowlines to clipped, buffered PFs
   printMsg("Clipping flowlines...")
   clipLines = "in_memory" + os.sep + "clipLines"
   arcpy.Clip_analysis ("lyr_Flowlines", clipBuff_PF, clipLines)
   
   # Create points from start- and endpoints of clipped flowlines
   arcpy.FeatureVerticesToPoints_management (clipLines, out_Points, "BOTH_ENDS")
   
   # timestamp
   t1 = datetime.now()
   ds = GetElapsedTime (t0, t1)
   printMsg("Completed function. Time elapsed: %s" % ds)
   
   return out_Points
   
def CreateLines_scs(out_Lines, in_PF, in_Points, in_downTrace, in_upTrace, out_Scratch = arcpy.env.scratchGDB):
   """Loads SCU points derived from Procedural Features, solves the upstream and downstream service layers, and combines network segments to create linear SCUs.
   Parameters:
   - out_Lines = Output lines representing Stream Conservation Units
   - in_PF = Input Procedural Features
   - in_Points = Input feature class containing points generated from procedural features
   - in_downTrace = Network Analyst service layer set up to run downstream
   - in_upTrace = Network Analyst service layer set up to run upstream
   - out_Scratch = Geodatabase to contain intermediate outputs"""
   
   arcpy.CheckOutExtension("Network")
   
   # timestamp
   t0 = datetime.now()
   
   # Set up some variables
   if out_Scratch == "in_memory":
      # recast to save to disk, otherwise there is no OBJECTID field for queries as needed
      outScratch = arcpy.env.scratchGDB
   printMsg("Casting strings to layer objects...")
   in_upTrace = arcpy.mapping.Layer(in_upTrace)
   in_downTrace = arcpy.mapping.Layer(in_downTrace)
   descDT = arcpy.Describe(in_downTrace)
   nwDataset = descDT.network.catalogPath
   catPath = os.path.dirname(nwDataset) # This is where hydro layers will be found
   hydroDir = os.path.dirname(catPath)
   hydroDir = os.path.dirname(hydroDir) # This is where output layer files will be saved
   lyrDownTrace = hydroDir + os.sep + "naDownTrace.lyr"
   lyrUpTrace = hydroDir + os.sep + "naUpTrace.lyr"
   downLines = out_Scratch + os.sep + "downLines"
   upLines = out_Scratch + os.sep + "upLines"
   outDir = os.path.dirname(out_Lines)
  
   # Load all points as facilities into both service layers; search distance 500 meters
   printMsg("Loading points into service layers...")
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
   printMsg("Completed point loading.")
   
   del naPoints
  
   # Solve upstream and downstream service layers; save out lines and updated layers
   for sa in [[in_downTrace, downLines, lyrDownTrace], [in_upTrace, upLines, lyrUpTrace]]:
      inLyr = sa[0]
      outLines = sa[1]
      outLyr = sa[2]
      printMsg("Solving service area for %s..." % inLyr)
      arcpy.Solve_na(in_network_analysis_layer=inLyr, 
         ignore_invalids="SKIP", 
         terminate_on_solve_error="TERMINATE", 
         simplification_tolerance="")
      inLines = arcpy.mapping.ListLayers(inLyr, "Lines")[0]
      printMsg("Saving out lines...")
      arcpy.CopyFeatures_management(inLines, outLines)
      arcpy.RepairGeometry_management (outLines, "DELETE_NULL")
      printMsg("Saving updated %s service layer to %s..." %(inLyr,outLyr))      
      arcpy.SaveToLayerFile_management(inLyr, outLyr)
   
   # # Merge the downstream segments with the upstream segments
   # printMsg("Merging primary segments...")
   # mergedLines = out_Scratch + os.sep + "mergedLines"
   # arcpy.Merge_management ([downLines, upLines], mergedLines)
   
   # Grab additional segments that may have been missed within large PFs in wide water areas
   # No longer sure this is necessary...?
   nhdFlowline = catPath + os.sep + "NHDFlowline"
   clpLines = out_Scratch + os.sep + "clpLines"
   qry = "FType in (460, 558)" # StreamRiver and ArtificialPath only
   arcpy.MakeFeatureLayer_management (nhdFlowline, "StreamRiver_Line", qry)
   CleanClip("StreamRiver_Line", in_PF, clpLines)
   
   # Merge and dissolve the segments; ESRI does not make this simple
   printMsg("Merging primary segments with selected extension segments...")
   comboLines = out_Scratch + os.sep + "comboLines"
   arcpy.Merge_management ([downLines, upLines, clpLines], comboLines)
   
   printMsg("Buffering segments...")
   buffLines = out_Scratch + os.sep + "buffLines"
   arcpy.Buffer_analysis(comboLines, buffLines, "1 Meters", "FULL", "ROUND", "ALL") 
   
   printMsg("Exploding buffers...")
   explBuff = outDir + os.sep + "explBuff"
   arcpy.MultipartToSinglepart_management(buffLines, explBuff)
   
   printMsg("Grouping segments...")
   arcpy.AddField_management(explBuff, "grpID", "LONG")
   arcpy.CalculateField_management(explBuff, "grpID", "!OBJECTID!", "PYTHON")
   
   joinLines = out_Scratch + os.sep + "joinLines"
   fldMap = 'grpID "grpID" true true false 4 Long 0 0, First, #, %s, grpID, -1, -1' % explBuff
   arcpy.SpatialJoin_analysis(comboLines, explBuff, joinLines, "JOIN_ONE_TO_ONE", "KEEP_ALL", fldMap, "INTERSECT")
   
   printMsg("Dissolving segments by group...")
   arcpy.Dissolve_management(joinLines, out_Lines, "grpID", "", "MULTI_PART", "DISSOLVE_LINES")
   
   # timestamp
   t1 = datetime.now()
   ds = GetElapsedTime (t0, t1)
   printMsg("Completed function. Time elapsed: %s" % ds)

   arcpy.CheckInExtension("Network")
   
   return (out_Lines, lyrDownTrace, lyrUpTrace)
   
def DelinSite_scs(in_Lines, in_Catch, out_Polys):
   """Selects the catchments intersecting linear SCUs, dissolves them, and fills in the gaps.
   
   Parameters:
   in_Lines = Input SCU lines, generated as output from CreateLines_scu function
   in_Catch = Input catchments from NHDPlus
   out_Polys = output polygons representing partial watersheds draining to the SCU lines
   """
   # timestamp
   t0 = datetime.now()

   # Select catchments intersecting scuLines
   arcpy.MakeFeatureLayer_management (in_Catch, "lyr_Catchments")
   arcpy.SelectLayerByLocation_management ("lyr_Catchments", "INTERSECT", in_Lines)

   # Dissolve catchments
   dissFeats = "in_memory" + os.sep + "dissFeats"
   arcpy.Dissolve_management ("lyr_Catchments", dissFeats, "", "", "SINGLE_PART", "")
   
   # Fill in gaps to create final sites
   arcpy. EliminatePolygonPart_management (dissFeats, out_Polys, "PERCENT", "", 99, "CONTAINED_ONLY")
   
   # timestamp
   t1 = datetime.now()
   ds = GetElapsedTime (t0, t1)
   printMsg("Completed function. Time elapsed: %s" % ds)
   
   return out_Polys

def TrimSite_scs(in_Lines, in_hydroNet, in_catchPolys, out_Polys, buffDist = 250):
   """Reduces the delineated sites to a specified buffer distance from streams and rivers. If we decide to implement this procedure, it should probably be folded into the previous function. Also, may want to add gap-filling at the end.
   Parameters:
   in_Lines = Input SCU lines, generated as output from CreateLines_scu function
   in_hydroNet = Input hydrological network dataset
   in_catchPolys = Input partial watershed polygons, generated as output from DelinSite_scu function
   buffDist = Distance, in meters, to buffer the SCU lines and their associated NHD polygons
   out_Polys = Output polygons representing buffer zone draining to SCU lines
   """
   # timestamp
   t0 = datetime.now()
   
   # Set up some variables
   descHydro = arcpy.Describe(in_hydroNet)
   nwDataset = descHydro.catalogPath
   catPath = os.path.dirname(nwDataset) # This is where hydro layers will be found
   nhdArea = catPath + os.sep + "NHDArea"
   nhdWaterbody = catPath + os.sep + "NHDWaterbody"
   out_Scratch = "in_memory"
   
   # Create empty feature class to store polygons
   sr = arcpy.Describe(in_catchPolys).spatialReference
   fname = os.path.basename(out_Polys)
   fpath = os.path.dirname(out_Polys)
   printMsg("Creating empty feature class for polygons")
   if arcpy.Exists(out_Polys):
      arcpy.Delete_management(out_Polys)
   arcpy.CreateFeatureclass_management (fpath, fname, "POLYGON", in_catchPolys, "", "", sr)
   
   # Make feature layers including only StreamRiver and LakePond polygons from NHD
   printMsg("Making feature layers...")
   qry = "FType = 460" # StreamRiver only+++++++++++++
   arcpy.MakeFeatureLayer_management (nhdArea, "StreamRiver_Poly", qry)
   qry = "FType = 390" # LakePond only
   arcpy.MakeFeatureLayer_management (nhdWaterbody, "LakePond_Poly", qry)
   
   # Set up more variables
   clipRiverPoly = out_Scratch + os.sep + "clipRiverPoly"
   fillRiverPoly = out_Scratch + os.sep + "fillRiverPoly"
   clipLakePoly = out_Scratch + os.sep + "clipLakePoly"
   fillLakePoly = out_Scratch + os.sep + "fillLakePoly"
   clipLines = out_Scratch + os.sep + "clipLines"
   StreamRiverBuff = out_Scratch + os.sep + "StreamRiverBuff"
   LakePondBuff = out_Scratch + os.sep + "LakePondBuff"
   LineBuff = out_Scratch + os.sep + "LineBuff"
   mergeBuff = out_Scratch + os.sep + "mergeBuff"
   dissBuff = out_Scratch + os.sep + "dissBuff"
   clipBuff = out_Scratch + os.sep + "clipBuff"
   
   # Clip input layers to partial watersheds
   # Also need to fill any holes in polygons to avoid aberrant results
   printMsg("Clipping StreamRiver polygons...")
   CleanClip("StreamRiver_Poly", in_catchPolys, clipRiverPoly)
   arcpy.EliminatePolygonPart_management (clipRiverPoly, fillRiverPoly, "PERCENT", "", 99, "CONTAINED_ONLY")
   arcpy.MakeFeatureLayer_management (fillRiverPoly, "StreamRivers")
   
   printMsg("Clipping LakePond polygons...")
   CleanClip("LakePond_Poly", in_catchPolys, clipLakePoly)
   arcpy.EliminatePolygonPart_management (clipLakePoly, fillLakePoly, "PERCENT", "", 99, "CONTAINED_ONLY")
   arcpy.MakeFeatureLayer_management (fillLakePoly, "LakePonds")
   
   # Select clipped NHD polygons intersecting clipped SCU lines
   printMsg("Selecting by location the clipped NHD polygons intersecting clipped SCU lines...")
   arcpy.SelectLayerByLocation_management("StreamRivers", "INTERSECT", in_Lines, "", "NEW_SELECTION")
   arcpy.SelectLayerByLocation_management("LakePonds", "INTERSECT", in_Lines, "", "NEW_SELECTION")
   
   # Buffer SCU lines and selected NHD polygons
   printMsg("Buffering StreamRiver polygons...")
   arcpy.Buffer_analysis("StreamRivers", StreamRiverBuff, buffDist, "", "ROUND", "NONE")
   
   printMsg("Buffering LakePond polygons...")
   arcpy.Buffer_analysis("LakePonds", LakePondBuff, buffDist, "", "ROUND", "NONE")
   
   printMsg("Buffering SCU lines...")
   arcpy.Buffer_analysis(in_Lines, LineBuff, buffDist, "", "ROUND", "NONE")
   
   # Merge buffers and dissolve
   printMsg("Merging buffer polygons...")
   arcpy.Merge_management ([StreamRiverBuff, LakePondBuff, LineBuff], mergeBuff)
   
   printMsg("Dissolving...")
   arcpy.Dissolve_management (mergeBuff, dissBuff, "", "", "SINGLE_PART")
   
   # Clip buffers to partial watershed
   printMsg("Clipping to partial watershed...")
   CleanClip(dissBuff, in_catchPolys, clipBuff)
   arcpy.MakeFeatureLayer_management (clipBuff, "clipBuffers")
   
   # Eliminate buffer fragments, fill holes, and save
   printMsg("Eliminating buffer fragments and filling holes...")
   arcpy.SelectLayerByLocation_management("clipBuffers", "CONTAINS", in_Lines, "", "NEW_SELECTION")
   arcpy. EliminatePolygonPart_management ("clipBuffers", out_Polys, "PERCENT", "", 99, "CONTAINED_ONLY")
   # arcpy.CopyFeatures_management ("clipBuffers", out_Polys)
   
   # timestamp
   t1 = datetime.now()
   ds = GetElapsedTime (t0, t1)
   printMsg("Completed function. Time elapsed: %s" % ds)
   
   return out_Polys

# Use the main function below to run functions directly from Python IDE or command line with hard-coded variables
def main():
   # Set up basic input variables
   in_hydroNet = r"F:\Working\SCU\VA_HydroNet.gdb\HydroNet\HydroNet_ND"
   in_Catch = r"E:\SpatialData\NHD_Plus_HR\Proc_NHDPlus_HR.gdb\NHDPlusCatchment_Merge_valam"
   in_PF = r"F:\Working\EssentialConSites\ECS_Inputs_December2019.gdb\ProcFeats_20191213_scu"
   out_GDB = r"F:\Working\SCS\TestOutputs_20200604.gdb"

   ### Set up trial variables
   # Trial 1
   upDist1 = 2000
   downDist1 = 1000
   buffDist1 = 250
   trial_1 = ["Trial_1", upDist1, downDist1, buffDist1]
   
   # Trial 2
   upDist2 = 2000
   downDist2 = 500
   buffDist2 = 250
   trial_2 = ["Trial_2", upDist2, downDist2, buffDist2]
   
   # Trial 3
   upDist3 = 3000
   downDist3 = 1000
   buffDist3 = 250
   trial_3 = ["Trial_3", upDist3, downDist3, buffDist3]
   
   # Trial 4
   upDist4 = 3000
   downDist4 = 500
   buffDist4 = 250
   trial_4 = ["Trial_4", upDist4, downDist4, buffDist4]
   
   # End of user input

   # Function(s) to run
   for t in [trial_1, trial_2, trial_3, trial_4]:
      # timestamp
      tStart = datetime.now()
      
      printMsg("Working on %s" %t[0])
      
      nameTag = t[0]
      upDist = t[1]
      downDist = t[2]
      buffDist = t[3]
      
      scsPts = out_GDB + os.sep + "scsPts_%s" %nameTag
      scsLines = out_GDB + os.sep + "scsLines_%s" %nameTag
      scsCatch = out_GDB + os.sep + "scsCatch_%s" %nameTag
      scsFinal = out_GDB + os.sep + "scsFinal_%s" %nameTag
      
      # printMsg("Starting MakeServiceLayers_scs function.")
      # (lyrDownTrace, lyrUpTrace) = MakeServiceLayers_scs(in_hydroNet, upDist, downDist)
      
      # printMsg("Starting MakeNetworkPts_scs function.")
      # MakeNetworkPts_scs(in_hydroNet, in_Catch, in_PF, scsPts)
      
      # printMsg("Starting CreateLines_scs function.")
      # CreateLines_scs(scsLines, in_PF, scsPts, lyrDownTrace, lyrUpTrace)
      
      # printMsg("Starting DelinSite_scs function.")
      # DelinSite_scs(scsLines, in_Catch, scsCatch)
      
      printMsg("Starting TrimSite_scs function.")
      TrimSite_scs(scsLines, in_hydroNet, scsCatch, scsFinal, buffDist)
      
      printMsg("Finished with %s." %t[0])
      
      # timestamp
      tEnd = datetime.now()
      ds = GetElapsedTime (tStart, tEnd)
      printMsg("Time elapsed: %s" % ds)
   
if __name__ == "__main__":
   main()
