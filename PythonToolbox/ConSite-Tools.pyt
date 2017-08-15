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
import libConSiteFx
from libConSiteFx import *

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

# # For debugging...
# def main():
   # tbx = Toolbox()
   # tool = shrinkwrap()
   # tool.execute(tool.getParameterInfo(),None)

# if __name__ == '__main__':
   # main()