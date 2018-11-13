# ----------------------------------------------------------------------------------------
# CreateSCU.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2018-11-05
# Last Edit: 2018-11-13
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

def MakeServiceLayers_scu(in_GDB):
   '''Make two service layers needed for analysis.
   Parameters:
   - in_GDB = The geodatabase containing the hydro network and associated features'''
   
   # Set up some variables
   out_Dir = os.path.dirname(in_GDB)
   nwDataset = in_GDB + os.sep + "HydroNet" + os.sep + "HydroNet_ND"
   nwLines = in_GDB + os.sep + "HydroNet" + os.sep + "NHDLine"
   where_clause = "FType = 343" # DamWeir only
   arcpy.MakeFeatureLayer_management (nwLines, "lyr_DamWeir", where_clause)
   in_Lines = "lyr_DamWeir"
   lyrDownTrace = out_Dir + os.sep + "naDownTrace.lyr"
   lyrUpTrace = out_Dir + os.sep + "naUpTrace.lyr"
   
   # Downstream trace with breaks at 1609 (1 mile), 3218 (2 miles)
   printMsg('Creating downstream service layer...')
   naDownTraceLayer = arcpy.MakeServiceAreaLayer_na(in_network_dataset=nwDataset,
         out_network_analysis_layer="naDownTrace", 
         impedance_attribute="Length", 
         travel_from_to="TRAVEL_FROM", 
         default_break_values="1609, 3218", 
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
   
   printMsg('Saving downstream service layer to %s...' %lyrDownTrace)
   arcpy.SaveToLayerFile_management("naDownTrace", lyrDownTrace) 
   
   naDownTraceLayer = naDownTraceLayer.getOutput(0)
   
   # Upstream trace with break at 3218 (2 miles)
   printMsg('Creating upstream service layer...')
   naUpTraceLayer = arcpy.MakeServiceAreaLayer_na(in_network_dataset=nwDataset,
         out_network_analysis_layer="naUpTrace", 
         impedance_attribute="Length", 
         travel_from_to="TRAVEL_FROM", 
         default_break_values="3218", 
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
         
   printMsg('Saving upstream service layer to %s...' %lyrUpTrace)      
   arcpy.SaveToLayerFile_management("naUpTrace", lyrUpTrace) 
   
   naUpTraceLayer = naUpTraceLayer.getOutput(0)
   
   return(naDownTraceLayer, naUpTraceLayer)

def MakeNetworkPts_scu(in_PF, fld_SFID = "SFID", in_downTrace = "naDownTrace", in_upTrace = "naUpTrace", out_Scratch = "in_memory"):
   '''Given SCU-worthy procedural features, creates points on the network by intersection, then loads them into service layers.
   Parameters:
   - in_PF = Input SCU-worthy procedural features
   - fld_SFID = Field in in_PF containing unique ID
   - in_downTrace = Service layer set up to run downstream
   - in_upTrace = Service layer set up to run upstream
   - out_Scratch = geodatabase to contain intermediate products'''
   
   # Set up some variables
   pf = arcpy.mapping.Layer(in_PF)
   pfData = pf.dataSource
   dt = arcpy.mapping.Layer(in_downTrace)
   ut = arcpy.mapping.Layer(in_upTrace)
   wsp = dt.workspacePath
   out_Dir = os.path.dirname(wsp)
   lyrDownTrace = out_Dir + os.sep + 'naDownTrace'
   lyrUpTrace = out_Dir + os.sep + 'naUpTrace'
   pfCirc = out_Scratch + os.sep + 'pfCirc'
   scuPoints = out_Scratch + os.sep + 'scuPoints'
   sr = arcpy.Describe(in_PF).spatialReference
   tmpPts = out_Scratch + os.sep + 'tmpPts'
   tmpPts2 = out_Scratch + os.sep + 'tmpPts2'
   pfBuff = out_Scratch + os.sep + 'pfBuff'
   
   # Create bounding circles around PFs
   printMsg('Creating bounding circles for procedural features...')
   arcpy.MinimumBoundingGeometry_management (in_PF, pfCirc, "CIRCLE", "NONE", "", "MBG_FIELDS")
   
   # Create empty feature class to store points
   printMsg('Creating empty feature class for points')
   if arcpy.Exists(scuPoints):
      arcpy.Delete_management(scuPoints)
   outDir = os.path.dirname(scuPoints)
   outName = os.path.basename(scuPoints)
   printMsg('Creating %s in %s' %(outName, outDir))
   arcpy.CreateFeatureclass_management (outDir, outName, "POINT", in_PF, '', '', sr)
   
   # For each PF, get the intersections of the PF with its bounding circle
   printMsg('Generating points on circles...')
   with  arcpy.da.SearchCursor(in_PF, [fld_SFID]) as myPFs:
      for PF in myPFs:
         id = PF[0]
         qry = "%s = '%s'" % (fld_SFID, id)
         arcpy.MakeFeatureLayer_management (pfCirc,  "tmpCirc", qry)
         arcpy.MakeFeatureLayer_management (pfData,  "tmpPF", qry)
         # Buffer first by small amount to avoid some weird results for some features
         arcpy.Buffer_analysis("tmpPF", pfBuff, "1 Meters", "", "", "NONE")
         arcpy.Intersect_analysis ([pfBuff, "tmpCirc"], tmpPts, "", "", "POINT")
         c = countFeatures(tmpPts) # Check for empty output and proceed accordingly
         # You get empty output if PF is a perfect circle
         if c == 0:
            # generate centroid instead
            arcpy.FeatureToPoint_management ("tmpPF", tmpPts, "CENTROID")
            arcpy.Append_management (tmpPts, scuPoints, "NO_TEST")
         else:
            # explode multipoint
            arcpy.MultipartToSinglepart_management (tmpPts, tmpPts2)
            arcpy.Append_management (tmpPts2, scuPoints, "NO_TEST")
     
   # Load all points as facilities into both service layers; search distance 500 meters
   printMsg('Loading points into service layers...')
   for sa in [[dt,lyrDownTrace], [ut, lyrUpTrace]]:
      inLyr = sa[0]
      outLyr = sa[1]
      naPoints = arcpy.AddLocations_na(in_network_analysis_layer=inLyr, 
         sub_layer="Facilities", 
         in_table=scuPoints, 
         field_mappings="Name FID #", 
         search_tolerance="500 Meters", 
         sort_field="", 
         search_criteria="NHDFlowline SHAPE;HydroNet_ND_Junctions NONE", 
         match_type="MATCH_TO_CLOSEST", 
         append="CLEAR", 
         snap_to_position_along_network="SNAP", ###?
         snap_offset="", 
         exclude_restricted_elements="EXCLUDE", 
         search_query="NHDFlowline #;HydroNet_ND_Junctions #")
      printMsg('Saving updated %s service layer to %s...' %(inLyr,outLyr))      
      arcpy.SaveToLayerFile_management(inLyr, outLyr)
   printMsg('Completed point loading.')
   
   del pf, dt, ut
   return()
   
def CreateLines_scu(in_downTrace, in_upTrace, out_Lines, out_Scratch = "in_memory"):
   '''Given service areas with loaded points, solves the service area lines, and combines them to get baseline linear SCUs
   - in_downTrace = Service layer set up to run downstream
   - in_upTrace = Service layer set up to run upstream
   - out_Lines = Output linear SCUs
   - out_Scratch = geodatabase to contain intermediate products'''
   
   # Set up some variables
   dt = arcpy.mapping.Layer(in_downTrace)
   ut = arcpy.mapping.Layer(in_upTrace)
   wsp = dt.workspacePath
   out_Dir = os.path.dirname(wsp)
   lyrDownTrace = out_Dir + os.sep + 'naDownTrace'
   lyrUpTrace = out_Dir + os.sep + 'naUpTrace'

   # Solve upstream and downstream service layers; save
   # For downstream segments > 1609, select only those intersecting upstream segments 
   # Merge the relevant segments: upstream up to 3218, downstream up to 1609, and the additional selected segments
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
