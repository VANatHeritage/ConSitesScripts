# ----------------------------------------------------------------------------------------
# SCU-Prioritization.pyt
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2017-08-29
# Last Edit: 2017-08-30
# Creator(s):  Kirsten R. Hazler

# Summary:
# A Python toolbox for prioritiziing Stream Conservation Units (SCUs) for conservation.

# Usage Tips:

# Dependencies:
# 
# ----------------------------------------------------------------------------------------

# Import modules and function library
import libScuFx
from libScuFx import *

# Define functions that help build the toolbox
# NOTE: The "defineParam" and "declareParams" functions MUST reside within the toolbox script, not imported from some other module!
def defineParam(p_name, p_displayName, p_datatype, p_parameterType, p_direction, defaultVal = None):
   '''Simplifies parameter creation. Thanks to http://joelmccune.com/lessons-learned-and-ideas-for-python-toolbox-coding/'''
   param = arcpy.Parameter(
      name = p_name,
      displayName = p_displayName,
      datatype = p_datatype,
      parameterType = p_parameterType,
      direction = p_direction)
   param.value = defaultVal 
   return param

def declareParams(params):
   '''Sets up parameter dictionary, then uses it to declare parameter values'''
   d = {}
   for p in params:
      name = str(p.name)
      value = str(p.valueAsText)
      d[name] = value
      
   for p in d:
      globals()[p] = d[p]
   return 

# Define the toolbox
class Toolbox(object):
   def __init__(self):
      """Toolbox for prioritization of Stream Conservation Units (SCUs)"""
      self.label = "SCU Prioritization Toolbox"
      self.alias = "SCU Prioritization Toolbox"

      # List of tool classes associated with this toolbox
      self.tools = [flowDistBuffer, zonalStats, landscapeScore, scuPrior]
      
# Define the tools
class flowDistBuffer(object):
   def __init__(self):
      """Delineates buffers for polygons based on flow distance."""
      self.label = "Delineate buffers based on flow distance"
      self.description = ""
      self.canRunInBackground = True

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_Feats", "Input features", "GPFeatureLayer", "Required", "Input")
      parm1 = defineParam("fld_ID", "Unique ID field (integer)", "String", "Required", "Input")
      parm2 = defineParam("in_FlowDir", "Input flow direction raster", "GPRasterLayer", "Required", "Input")
      parm3 = defineParam("out_Feats", "Output flow distance buffers", "DEFeatureClass", "Required", "Output")
      parm4 = defineParam("maxDist", "Maximum distance (in map units)", "GPDouble", "Required", "Input")
      parm4.value = 250
      parm5 = defineParam("dilDist", "Dilation distance for smoothing final shape (in map units)", "GPDouble", "Optional", "Input")
      parm6 = defineParam("out_Scratch", "Scratch geodatabase", "DEWorkspace", "Optional", "Input")
      parm6.filter.list = ["Local Database"]
      parms = [parm0, parm1, parm2, parm3, parm4, parm5, parm6]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      if parameters[0].altered:
         fc = parameters[0].valueAsText
         field_names = [f.name for f in arcpy.ListFields(fc, "", "Integer")]
         parameters[1].filter.list = field_names
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)
      mDist = float(maxDist) # Convert distance string back to number
      
      if dilDist == 'None':
         dDist = 0.0
      else:
         dDist = float(dilDist)

      if out_Scratch != 'None':
         scratchParm = out_Scratch 
      else:
         scratchParm = arcpy.env.scratchGDB
         #Note: I wanted to use 'in_memory' here, but was getting aberrant results for no discernible reason. Code works fine when using scratch workspace on disk; outputs square blocks if processing in memory. WHY???
      
      delinFlowDistBuff(in_Feats, fld_ID, in_FlowDir, out_Feats, mDist, dDist, scratchParm)

      return out_Feats

class zonalStats(object):
   def __init__(self):
      """Attaches zonal statistics from a raster to polygons."""
      self.label = "Get zonal statistics for polygons"
      self.description = ""
      self.canRunInBackground = True
   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_Polys", "Input polygons", "GPFeatureLayer", "Required", "Input")
      parm1 = defineParam("in_Raster", "Input raster", "GPRasterLayer", "Required", "Input")
      parm2 = defineParam("fld_ID", "Unique ID field (integer)", "String", "Required", "Input", "lngID")
      parm3 = defineParam("fld_Stats", "Statistics field basename", "String", "Required", "Input")
      parm4 = defineParam("type_Stats", "Statistics to append", "String", "Required", "Input")
      parm4.filter.list = ['MIN', 'MAX', 'MEAN', 'STD', 'MEDIAN']
      parm4.multiValue = True
      parm5 = defineParam("out_Polys", "Output attributed polygons", "DEFeatureClass", "Required", "Output")
      parm6 = defineParam("out_Scratch", "Scratch geodatabase", "DEWorkspace", "Optional", "Input")
      parm6.filter.list = ["Local Database"]
      parms = [parm0, parm1, parm2, parm3, parm4, parm5, parm6]
      return parms
      
   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True
      
   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      return
      
   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return
      
   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)
      statsList = type_Stats.split(";")

      if out_Scratch != 'None':
         scratchParm = out_Scratch 
      else:
         scratchParm = arcpy.env.scratchGDB
         #Note: I wanted to use 'in_memory' here, but was getting aberrant results for no discernible reason. Code works fine when using scratch workspace on disk; outputs square blocks if processing in memory. WHY???
      
      getZonalStats(in_Polys, in_Raster, fld_ID, fld_Stats, statsList, out_Polys, scratchParm)

      return in_Polys
      
class landscapeScore(object):
   def __init__(self):
      """Assigns a landscape score to features based on forest/wetland and impervious surface cover."""
      self.label = "Assign landscape score to features"
      self.description = ""
      self.canRunInBackground = True
   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_Feats", "Input features", "GPFeatureLayer", "Required", "Input")
      parm1 = defineParam("fld_ForWet", "Field containing forest/wetland cover", "String", "Required", "Input")
      parm2 = defineParam("fld_ImpSur", "Field containing impervious surface cover", "String", "Required", "Input")
      parms = [parm0, parm1, parm2]
      return parms
      
   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True
      
   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      if parameters[0].altered:
         in_Feats = parameters[0].valueAsText
         fldNames = [field.name for field in arcpy.ListFields(in_Feats)]
         parameters[1].filter.list = fldNames
         parameters[2].filter.list = fldNames
      return
      
   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return
      
   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)
      
      getLandscapeScore(in_Feats, fld_ForWet, fld_ImpSur)

      return in_Feats
      
class scuPrior(object):
   def __init__(self):
      """Prioritizes Stream Conservation Units (SCUs) for conservation."""
      self.label = "Prioritize Stream Conservation Units"
      self.description = ""
      self.canRunInBackground = True

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_Feats", "Input buffered SCU features", "GPFeatureLayer", "Required", "Input")
      parm1 = defineParam("fld_ID", "Unique ID field (integer)", "String", "Required", "Input")
      parm2 = defineParam("fld_BRANK", "BRANK field", "String", "Required", "Input")
      parm3 = defineParam("lo_BRANK", "Lowest BRANK to consider", "String", "Required", "Input")
      parm3.value = 'B2'
      parm3.filter.list = ['B1', 'B2', 'B3', 'B4', 'B5']
      parm4 = defineParam("in_Integrity", "Input Watershed Integrity Raster", "GPRasterLayer", "Required", "Input")
      parm5 = defineParam("lo_Integrity", "Minimum integrity value to consider", "GPLong", "Required", "Input")
      parm5.value = 80
      parm6 = defineParam("in_ConsPriority", "Input Conservation Priority Raster", "GPRasterLayer", "Required", "Input")
      parm7 = defineParam("in_Vulnerability", "Input Development Vulnerability Raster", "GPRasterLayer", "Required", "Input")
      parm8 = defineParam("out_Feats", "Output scored features", "DEFeatureClass", "Required", "Output")
      parm9 = defineParam("out_Scratch", "Scratch geodatabase", "DEWorkspace", "Optional", "Input")
      parm9.filter.list = ["Local Database"]
      parms = [parm0, parm1, parm2, parm3, parm4, parm5, parm6, parm7, parm8, parm9]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      if parameters[0].altered:
         fc = parameters[0].valueAsText
         int_field_names = [f.name for f in arcpy.ListFields(fc, "", "Integer")]
         parameters[1].filter.list = int_field_names
         field_names = [f.name for f in arcpy.ListFields(fc)]
         parameters[2].filter.list = field_names
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)
      loInteg = float(lo_Integrity) # Convert value string back to number

      if out_Scratch != 'None':
         scratchParm = out_Scratch 
      else:
         scratchParm = 'in_memory'
      
      prioritizeSCUs(in_Feats, fld_ID, fld_BRANK, lo_BRANK, in_Integrity, loInteg, in_ConsPriority, in_Vulnerability, out_Feats, scratchParm)

      return out_Feats