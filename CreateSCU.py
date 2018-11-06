# ----------------------------------------------------------------------------------------
# CreateSCU.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2018-11-05
# Last Edit: 2018-11-06
# Creator(s):  Kirsten R. Hazler

# Summary:
# Functions for delineating Stream Conservation Units (SCUs).

# Usage Tips:
# 

# Dependencies:
# 

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

def MakeServiceLayers_scu(in_GDB, out_Dir):
   '''Make two service layers needed for analysis.
   Parameters:
   - in_GDB = The geodatabase containing the hydro network and associated features
   - out_Dir = Directory to contain output layer files '''
   
   # Set up some variables
   nwDataset = in_GDB + os.sep + "HydroNet" + os.sep + "HydroNet_ND"
   nwLines = in_GDB + os.sep + "HydroNet" + os.sep + "NHDLine"
   where_clause = "FType = 343" # DamWeir only
   arcpy.MakeFeatureLayer_management (nwLines, "lyr_DamWeir", where_clause)
   in_Lines = "lyr_DamWeir"
   lyrDownTrace = out_Dir + os.sep + "naDownTrace.lyr"
   lyrUpTrace = out_Dir + os.sep + "naUpTrace.lyr"
   
   # Downstream trace with breaks at 1500, 2000
   printMsg('Creating downstream service layer...')
   naDownTraceLayer = arcpy.MakeServiceAreaLayer_na(in_network_dataset=nwDataset,
         out_network_analysis_layer="naDownTrace", 
         impedance_attribute="Length", 
         travel_from_to="TRAVEL_FROM", 
         default_break_values="1500, 2000", 
         polygon_type="NO_POLYS", 
         merge="NO_MERGE", 
         nesting_type="RINGS", 
         line_type="TRUE_LINES_WITH_MEASURES", 
         overlap="NON_OVERLAP", 
         split="SPLIT", 
         excluded_source_name="", 
         accumulate_attribute_name="Length", 
         UTurn_policy="ALLOW_UTURNS", 
         restriction_attribute_name="NoConnectors;NoPipelines;NoUndergroundConduits;FlowDownOnly", 
         polygon_trim="TRIM_POLYS", 
         poly_trim_value="100 Meters", 
         lines_source_fields="LINES_SOURCE_FIELDS", 
         hierarchy="NO_HIERARCHY", 
         time_of_day="")
   
   printMsg('Adding dam barriers to downstream service layer...')
   barriers = arcpy.AddLocations_na(in_network_analysis_layer="naDownTrace", 
         sub_layer="Line Barriers", 
         in_table=in_Lines, 
         field_mappings="Name Permanent_Identifier #", 
         search_tolerance="100 Meters", 
         sort_field="", 
         search_criteria="NHDFlowline SHAPE_MIDDLE_END;HydroNet_ND_Junctions NONE", 
         match_type="MATCH_TO_CLOSEST", 
         append="CLEAR", 
         snap_to_position_along_network="SNAP", 
         snap_offset="5 Meters", 
         exclude_restricted_elements="INCLUDE", 
         search_query="NHDFlowline #;HydroNet_ND_Junctions #")
   
   printMsg('Saving downstream service layer...')
   arcpy.SaveToLayerFile_management(in_layer="naDownTrace", out_layer=lyrDownTrace, is_relative_path="RELATIVE", version="CURRENT") 
   
   naDownTraceLayer = naDownTraceLayer.getOutput(0)
   
   # Upstream trace with breaks at 3000, 3500
   printMsg('Creating upstream service layer...')
   naUpTraceLayer = arcpy.MakeServiceAreaLayer_na(in_network_dataset=nwDataset,
         out_network_analysis_layer="naUpTrace", 
         impedance_attribute="Length", 
         travel_from_to="TRAVEL_FROM", 
         default_break_values="3000, 3500", 
         polygon_type="NO_POLYS", 
         merge="NO_MERGE", 
         nesting_type="RINGS", 
         line_type="TRUE_LINES_WITH_MEASURES", 
         overlap="NON_OVERLAP", 
         split="SPLIT", 
         excluded_source_name="", 
         accumulate_attribute_name="Length", 
         UTurn_policy="ALLOW_UTURNS", 
         restriction_attribute_name="NoConnectors;NoPipelines;NoUndergroundConduits;FlowUpOnly", 
         polygon_trim="TRIM_POLYS", 
         poly_trim_value="100 Meters", 
         lines_source_fields="LINES_SOURCE_FIELDS", 
         hierarchy="NO_HIERARCHY", 
         time_of_day="")
   
   printMsg('Adding dam barriers to upstream service layer...')
   barriers = arcpy.AddLocations_na(in_network_analysis_layer="naUpTrace", 
         sub_layer="Line Barriers", 
         in_table=in_Lines, 
         field_mappings="Name Permanent_Identifier #", 
         search_tolerance="100 Meters", 
         sort_field="", 
         search_criteria="NHDFlowline SHAPE_MIDDLE_END;HydroNet_ND_Junctions NONE", 
         match_type="MATCH_TO_CLOSEST", 
         append="CLEAR", 
         snap_to_position_along_network="SNAP", 
         snap_offset="5 Meters", 
         exclude_restricted_elements="INCLUDE", 
         search_query="NHDFlowline #;HydroNet_ND_Junctions #")
         
   printMsg('Saving upstream service layer...')      
   arcpy.SaveToLayerFile_management(in_layer="naUpTrace", out_layer=lyrUpTrace, is_relative_path="RELATIVE", version="CURRENT") 
   
   naUpTraceLayer = naUpTraceLayer.getOutput(0)
   
   return(naDownTraceLayer, naUpTraceLayer)

def MakeNetworkPts_scu(in_PF, in_GDB, out_Points):
   '''Given SCU-worthy procedural features, creates points on the network by intersection, then loads them into service layers.
   Parameters:
   - in_PF = Input SCU-worthy procedural features
   - in_GDB = The geodatabase containing the hydro network and associated features
   - out_Points = Output points feature class'''
   # select the PFs that intersect the hydro network
   # intersect features with network and get points
   arcpy.env.Extent = in_PF
   nhdFlowlines = in_GDB + os.sep + 'HydroNet' + os.sep + 'NHDFlowline'
   inFeats = [in_PF, nhdFlowlines]
   arcpy.Intersect_analysis(inFeats, out_Points, "ALL", "", "POINT") 
   
   # select the PFs that do not intersect the hydro network
   # generate the point on network closest to each feature
   # or should original feature be shifted, then points generated??
  
   # combine all points and load as facilities in both service layers
   
def CreateLines_scu():
   '''Solves the service area layers, and combines them to get baseline linear SCUs'''
   # Run upstream
   # Run downstream
   # Split upstream into 3000, > 3000
   # Split downstream into 1500, > 1500
   # For upstream segments >3000, select only those intersecting downstream segments <=1500
   # For downstream segments > 1500, select only those intersecting upstream segments <=3000
   # Merge the relevant segments: upstream up to 3000, downstream up to 1500, and the additional selected segments
   # Dissolve the merged segments; no multiparts
   
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
   in_GDB = r'C:\Users\xch43889\Documents\Working\ConsVision\HydroNet_testing\VA_HydroNet.gdb'
   out_Dir = r'C:\Users\xch43889\Documents\ArcGIS\scratch'
   in_PF = r'C:\Users\xch43889\Documents\Working\SCU\scupfs\mr_1541444345008.gdb\query_result'
   out_Points = r'C:\Users\xch43889\Documents\Working\SCU\testData.gdb\pfPoints'
   # End of user input

   # MakeServiceLayers_scu(in_GDB, out_Dir)
   MakeNetworkPts_scu(in_PF, in_GDB, out_Points)
   
if __name__ == '__main__':
   main()
