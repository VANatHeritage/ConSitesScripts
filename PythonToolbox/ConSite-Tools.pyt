# ----------------------------------------------------------------------------------------
# ConSite-Tools.pyt
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2017-08-11
# Last Edit: 2017-08-15
# Creator:  Kirsten R. Hazler

# Summary:
# A toolbox for automatic delineation of Natural Heritage Conservation Sites

# TO DO:
#
# ----------------------------------------------------------------------------------------

import arcpy
import libConSiteFx, CreateSBBs
from libConSiteFx import *
from CreateSBBs import *

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

def setParams(parameters, topVal):
   '''Sets up parameters to be used in execute statement'''
   for i in range(topVal+1):
      name = str(parameters[i].name)
      value = str(parameters[i].valueAsText)
      locals()[name] = value
   return
   
class Toolbox(object):
   def __init__(self):
      """Define the toolbox (the name of the toolbox is the name of the
      .pyt file)."""
      self.label = "ConSite Toolbox"
      self.alias = "ConSite-Toolbox"

      # List of tool classes associated with this toolbox
      self.tools = [shrinkwrap]

class shrinkwrap(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "Shrinkwrap"
      self.description = ""
      self.canRunInBackground = True

   def getParameterInfo(self):
      """Define parameter definitions"""
      inFeats = arcpy.Parameter(
         displayName = "Input features",
         name = "inFeats",
         datatype = "GPFeatureLayer",
         parameterType = "Required",
         direction = "Input")

      dilDist = arcpy.Parameter(
         displayName = "Dilation distance",
         name = "dilDist",
         datatype = "GPLinearUnit",
         parameterType = "Required",
         direction = "Input")

      outFeats = arcpy.Parameter(
         displayName = "Output features",
         name = "outFeats",
         datatype = "DEFeatureClass",
         parameterType = "Required",
         direction = "Output")

      scratchGDB = arcpy.Parameter(
         displayName = "Scratch geodatabase",
         name = "scratchGDB",
         datatype = "DEWorkspace",
         parameterType = "Optional",
         direction = "Input")
      scratchGDB.filter.list = ["Local Database"]

      params = [inFeats, dilDist, outFeats, scratchGDB]
      return params

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
      inFeats = parameters[0].valueAsText
      dilDist = parameters[1].valueAsText
      outFeats = parameters[2].valueAsText
      scratchGDB = parameters[3].valueAsText

      if not scratchGDB:
         scratchGDB = "in_memory"

      ShrinkWrap(inFeats, dilDist, outFeats, scratchGDB)

      return outFeats

class sbb(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "Create Site Building Blocks"
      self.description = ""
      self.canRunInBackground = True

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm0 = defineParam('in_PF', "Input Procedural Features", "GPFeatureLayer", "Required", "Input")
      parm1 = defineParam('fld_SFID', "Source Feature ID field", "Field", "Required", "Input", 'SFID')
      parm2 = defineParam('fld_Rule', "SBB Rule field", "Field", "Required", "Input", 'RULE')
      parm3 = defineParam('fld_Buff', "SBB Buffer field", "Field", "Required", "Input", 'BUFFER')
      parm4 = defineParam('in_nwi5', "Input Rule 5 NWI Features", "GPFeatureLayer", "Required", "Input")
      parm5 = defineParam('in_nwi67', "Input Rule 6/7 NWI Features", "GPFeatureLayer", "Required", "Input")
      parm6 = defineParam('in_nwi9', "Input Rule 9 NWI Features", "GPFeatureLayer", "Required", "Input")
      parm7 = defineParam('out_SBB', "Output Site Building Blocks", "GPFeatureLayer", "Required", "Output")
      parm8 = defineParam('scratchGDB', "Output Site Building Blocks", "DEWorkspace", "Optional", "Output", 'in_memory')

      parms = ['parm %s' %num for num in range(8+1)]
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
         field_names = [f.name for f in arcpy.ListFields(fc)]
         for i in [1,2,3]:
            parameters[i].filter.list = field_names
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Get the parameter names and values
      setParams(parameters, 8)

      if not scratchGDB:
         scratchGDB = "in_memory"

      CreateSBBs(in_PF, fld_SFID, fld_Rule, fld_Buff, in_nwi5, in_nwi67, in_nwi9, out_SBB, scratchGDB)

      return out_SBB
      
# # For debugging...
# def main():
   # tbx = Toolbox()
   # tool = shrinkwrap()
   # tool.execute(tool.getParameterInfo(),None)

# if __name__ == '__main__':
   # main()