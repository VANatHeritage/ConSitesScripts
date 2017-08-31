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
      self.tools = [flowDistBuffer]
      
# Define the tools
class flowDistBuffer(object):
   def __init__(self):
      """Delineates buffers for polygons based on flow distance."""
      self.label = "Delineate buffers based on flow distance"
      self.description = ""
      self.canRunInBackground = True

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_Feats", "Input SCU features", "GPFeatureLayer", "Required", "Input")
      parm1 = defineParam("fld_ID", "Unique ID field (integer)", "String", "Required", "Input")
      parm2 = defineParam("in_FlowDir", "Input flow direction raster", "GPRasterLayer", "Required", "Input")
      parm3 = defineParam("out_Buff", "Output flow distance buffers", "DEFeatureClass", "Required", "Output")
      parm4 = defineParam("maxDist", "Maximum distance", "GPDouble", "Required", "Input")
      parm4.value = 500
      parm5 = defineParam("out_Scratch", "Scratch geodatabase", "DEWorkspace", "Optional", "Input")
      parm5.filter.list = ["Local Database"]
      parms = [parm0, parm1, parm2, parm3, parm4, parm5]
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
      mDist = float(maxDist) # Convert string back to number

      if out_Scratch != 'None':
         scratchParm = out_Scratch 
      else:
         scratchParm = "in_memory" 
      
      delinFlowDistBuff(in_Feats, fld_ID, in_FlowDir, out_Buff, mDist, scratchParm)

      return out_Buff