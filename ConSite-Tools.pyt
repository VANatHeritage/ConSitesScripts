# ----------------------------------------------------------------------------------------
# ConSite-Tools.pyt
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2017-08-11
# Last Edit: 2018-11-26
# Creator:  Kirsten R. Hazler

# Summary:
# A toolbox for automatic delineation and prioritization of Natural Heritage Conservation Sites
# ----------------------------------------------------------------------------------------

import Helper
from Helper import *
from libConSiteFx import *
from CreateSBBs import *
from CreateConSites import *
from ReviewConSites import *
from CreateSCU import *
from EssentialConSites import *

# First define some handy functions
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
      """Define the toolbox (the name of the toolbox is the name of the
      .pyt file)."""
      self.label = "ConSite Toolbox"
      self.alias = "ConSite-Toolbox"

      # List of tool classes associated with this toolbox
      self.tools = [coalesceFeats, shrinkwrap, extract_biotics, create_sbb, expand_sbb, parse_sbb, create_consite, review_consite, ServLyrs_scu, NtwrkPts_scu, Lines_scu, Polys_scu, attribute_eo, score_eo, build_portfolio]

# Define the tools
class coalesceFeats(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "Coalesce"
      self.description = 'If a positive number is entered for the dilation distance, features are expanded outward by the specified distance, then shrunk back in by the same distance. This causes nearby features to coalesce. If a negative number is entered for the dilation distance, features are first shrunk, then expanded. This eliminates narrow portions of existing features, thereby simplifying them. It can also break narrow "bridges" between features that were formerly coalesced.'
      self.canRunInBackground = True
      self.category = "Subroutines"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_Feats", "Input features", "GPFeatureLayer", "Required", "Input")
      parm1 = defineParam("dil_Dist", "Dilation distance", "GPLinearUnit", "Required", "Input")
      parm2 = defineParam("out_Feats", "Output features", "DEFeatureClass", "Required", "Output")
      parm3 = defineParam("scratch_GDB", "Scratch geodatabase", "DEWorkspace", "Optional", "Input")
      
      parm3.filter.list = ["Local Database"]
      parms = [parm0, parm1, parm2, parm3]
      return parms

      return 

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

      if scratch_GDB != 'None':
         scratchParm = scratch_GDB 
      else:
         scratchParm = "in_memory" 

      Coalesce(in_Feats, dil_Dist, out_Feats, scratchParm)
      
      return out_Feats

class shrinkwrap(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "Shrinkwrap"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Subroutines"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_Feats", "Input features", "GPFeatureLayer", "Required", "Input")
      parm1 = defineParam("dil_Dist", "Dilation distance", "GPLinearUnit", "Required", "Input")
      parm2 = defineParam("out_Feats", "Output features", "DEFeatureClass", "Required", "Output")
      parm3 = defineParam("smthMulti", "Smoothing multiplier", "GPDouble", "Optional", "Input", 8)
      parm4 = defineParam("scratch_GDB", "Scratch geodatabase", "DEWorkspace", "Optional", "Input")
      
      parm4.filter.list = ["Local Database"]
      parms = [parm0, parm1, parm2, parm3, parm4]
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

      if scratch_GDB != 'None':
         scratchParm = scratch_GDB 
      else:
         scratchParm = "in_memory" 
         
      if smthMulti != 'None':
         multiParm = smthMulti
      else:
         multiParm = 8
      
      ShrinkWrap(in_Feats, dil_Dist, out_Feats, multiParm, scratchParm)

      return out_Feats

class extract_biotics(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "0: Extract Biotics data"
      self.description = ""
      self.canRunInBackground = False
      # For some reason, this tool fails if run in the background.
      self.category = "Standard Site Delineation Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm0 = defineParam('BioticsPF', "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input", "BIOTICS_DLINK.ProcFeats")
      parm1 = defineParam('BioticsCS', "Input Conservation Sites", "GPFeatureLayer", "Required", "Input", "BIOTICS_DLINK.all_consite_types")
      parm2 = defineParam('outGDB', "Output Geodatabase", "DEWorkspace", "Required", "Input")

      parms = [parm0, parm1, parm2]
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
      ExtractBiotics(BioticsPF, BioticsCS, outGDB)

      return

class create_sbb(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "1: Create Site Building Blocks (SBBs)"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Standard Site Delineation Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm0 = defineParam('in_PF', "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input", "Biotics_ProcFeats")
      parm1 = defineParam('fld_SFID', "Source Feature ID field", "String", "Required", "Input", 'SFID')
      parm2 = defineParam('fld_Rule', "SBB Rule field", "String", "Required", "Input", 'RULE')
      parm3 = defineParam('fld_Buff', "SBB Buffer field", "String", "Required", "Input", 'BUFFER')
      parm4 = defineParam('in_nwi5', "Input Rule 5 NWI Features", "GPFeatureLayer", "Required", "Input", "VA_Wetlands_Rule5")
      parm5 = defineParam('in_nwi67', "Input Rule 67 NWI Features", "GPFeatureLayer", "Required", "Input", "VA_Wetlands_Rule67")
      parm6 = defineParam('in_nwi9', "Input Rule 9 NWI Features", "GPFeatureLayer", "Required", "Input", "VA_Wetlands_Rule9")
      parm7 = defineParam('out_SBB', "Output Site Building Blocks (SBBs)", "DEFeatureClass", "Required", "Output")
      parm8 = defineParam('scratch_GDB', "Scratch Geodatabase", "DEWorkspace", "Optional", "Output")

      parms = [parm0, parm1, parm2, parm3, parm4, parm5, parm6, parm7, parm8]
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
      # Set up parameter names and values
      declareParams(parameters)

      if scratch_GDB != 'None':
         scratchParm = scratch_GDB 
      else:
         scratchParm = "in_memory" 

      CreateSBBs(in_PF, fld_SFID, fld_Rule, fld_Buff, in_nwi5, in_nwi67, in_nwi9, out_SBB, scratchParm)
      arcpy.MakeFeatureLayer_management (out_SBB, "SBB_lyr")

      return out_SBB
      
class expand_sbb(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "2: Expand SBBs with Core Area"
      self.description = "Expands SBBs by adding core area."
      self.canRunInBackground = True
      self.category = "Standard Site Delineation Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm0 = defineParam('in_Cores', "Input Cores", "GPFeatureLayer", "Required", "Input", "Cores123\Cores123")
      parm1 = defineParam('in_SBB', "Input Site Building Blocks (SBBs)", "GPFeatureLayer", "Required", "Input")
      parm2 = defineParam('in_PF', "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input", "Biotics_ProcFeats")
      parm3 = defineParam('joinFld', "Source Feature ID field", "String", "Required", "Input", 'SFID')
      parm4 = defineParam('out_SBB', "Output Expanded Site Building Blocks", "DEFeatureClass", "Required", "Output")
      parm5 = defineParam('scratch_GDB', "Scratch Geodatabase", "DEWorkspace", "Optional", "Output")

      parms = [parm0, parm1, parm2, parm3, parm4, parm5]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      if parameters[1].altered:
         fc = parameters[1].valueAsText
         field_names = [f.name for f in arcpy.ListFields(fc)]
         parameters[3].filter.list = field_names
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)

      if scratch_GDB != 'None':
         scratchParm = scratch_GDB 
      else:
         scratchParm = "in_memory" 

      ExpandSBBs(in_Cores, in_SBB, in_PF, joinFld, out_SBB, scratchParm)
      arcpy.MakeFeatureLayer_management (out_SBB, "SBB_lyr")
      
      return out_SBB
      
class parse_sbb(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "3: Parse SBBs by Type"
      self.description = "Splits SBB feature class into AHZ and non-AHZ features."
      self.canRunInBackground = True
      self.category = "Standard Site Delineation Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm0 = defineParam('in_SBB', "Input Site Building Blocks", "GPFeatureLayer", "Required", "Input")
      parm1 = defineParam('out_terrSBB', "Output Standard Terrestrial Site Building Blocks", "DEFeatureClass", "Required", "Output")
      parm2 = defineParam('out_ahzSBB', "Output Anthropogenic Habitat Zone Site Building Blocks", "DEFeatureClass", "Required", "Output")

      parms = [parm0, parm1, parm2]
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

      ParseSBBs(in_SBB, out_terrSBB, out_ahzSBB)
      arcpy.MakeFeatureLayer_management (out_terrSBB, "terrSBB_lyr")
      arcpy.MakeFeatureLayer_management (out_ahzSBB, "ahzSBB_lyr")
      
      return (out_terrSBB, out_ahzSBB)
            
class create_consite(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "4: Create Conservation Sites"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Standard Site Delineation Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm00 = defineParam("in_SBB", "Input Site Building Blocks (SBBs)", "GPFeatureLayer", "Required", "Input")
      parm01 = defineParam("ysn_Expand", "Expand SBB Selection?", "GPBoolean", "Required", "Input", "false")
      parm02 = defineParam("in_PF", "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input", "Biotics_ProcFeats")
      parm03 = defineParam("joinFld", "Source Feature ID field", "String", "Required", "Input", "SFID")
      parm04 = defineParam("in_ConSites", "Input Current Conservation Sites", "GPFeatureLayer", "Required", "Input", "Biotics_ConSites")
      parm05 = defineParam("out_ConSites", "Output Updated Conservation Sites", "DEFeatureClass", "Required", "Output")
      parm06 = defineParam("site_Type", "Site Type", "String", "Required", "Input")
      parm06.filter.list = ["TERRESTRIAL", "AHZ"]
      parm07 = defineParam("in_Hydro", "Input Hydro Features", "GPFeatureLayer", "Required", "Input", "HydrographicFeatures")
      parm08 = defineParam("in_TranSurf", "Input Transportation Surfaces", "GPValueTable", "Optional", "Input")
      parm08.columns = [["GPFeatureLayer","Transportation Layers"]]
      parm08.values = [["VirginiaRailSurfaces"], ["VirginiaRoadSurfaces"]]
      parm08.enabled = False
      parm09 = defineParam("in_Exclude", "Input Exclusion Features", "GPFeatureLayer", "Optional", "Input", "ExclusionFeatures")
      parm09.enabled = False
      parm10 = defineParam("scratch_GDB", "Scratch Geodatabase", "DEWorkspace", "Optional", "Input")
      
      parms = [parm00, parm01, parm02, parm03, parm04, parm05, parm06, parm07, parm08, parm09, parm10]
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
         parameters[3].filter.list = field_names
      
      if parameters[6].altered:
         type = parameters[6].value 
         if type == "TERRESTRIAL":
            parameters[8].enabled = 1
            parameters[8].parameterType = "Required"
            parameters[9].enabled = 1
            parameters[9].parameterType = "Required"
         else:
            parameters[8].enabled = 0
            parameters[8].parameterType = "Optional"
            parameters[9].enabled = 0
            parameters[9].parameterType = "Optional"
            
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      if parameters[6].value == "TERRESTRIAL":
         if parameters[8].value == None:
            parameters[8].SetErrorMessage("Input Transportation Surfaces: Value is required for TERRESTRIAL sites")
         if parameters[9].value == None:
            parameters[9].SetErrorMessage("Input Exclusion Features: Value is required for TERRESTRIAL sites")
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)

      if scratch_GDB != 'None':
         scratchParm = scratch_GDB 
      else:
         scratchParm = "in_memory" 
      CreateConSites(in_SBB, ysn_Expand, in_PF, joinFld, in_ConSites, out_ConSites, site_Type, in_Hydro, in_TranSurf, in_Exclude, scratchParm)

      return out_ConSites
      
class review_consite(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "5: Review Conservation Sites"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Standard Site Delineation Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm00 = defineParam("auto_CS", "Input NEW Conservation Sites", "GPFeatureLayer", "Required", "Input")
      parm01 = defineParam("orig_CS", "Input OLD Conservation Sites", "GPFeatureLayer", "Required", "Input")
      parm02 = defineParam("cutVal", "Cutoff value (percent)", "GPDouble", "Required", "Input")
      parm03 = defineParam("out_Sites", "Output new Conservation Sites feature class with QC fields", "GPFeatureLayer", "Required", "Output")
      parm04 = defineParam("fld_SiteID", "Conservation Site ID field", "String", "Required", "Input", "SITEID")
      parm05 = defineParam("scratch_GDB", "Scratch Geodatabase", "DEWorkspace", "Optional", "Input")

      parms = [parm00, parm01, parm02, parm03, parm04, parm05]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      if parameters[1].altered:
         fc = parameters[1].valueAsText
         field_names = [f.name for f in arcpy.ListFields(fc)]
         parameters[4].filter.list = field_names
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)

      if scratch_GDB != 'None':
         scratchParm = scratch_GDB
      else:
         scratchParm = arcpy.env.scratchWorkspace 

      ReviewConSites(auto_CS, orig_CS, cutVal, out_Sites, fld_SiteID, scratchParm)

      return out_Sites
      
class ServLyrs_scu(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "0: Make Network Analyst Service Layers"
      self.description = 'Make two service layers needed for distance analysis along hydro network.'
      self.canRunInBackground = True
      self.category = "Stream Conservation Unit Delineation Tools"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_hydroGDB", "Input HydroNet geodatabase", "DEWorkspace", "Required", "Input")
      parm0.filter.list = ["Local Database"]
      
      parms = [parm0]
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
      
      # Run the function
      MakeServiceLayers_scu(in_hydroGDB)
      
      return
      
class NtwrkPts_scu(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "1: Make Network Points from Procedural Features"
      self.description = 'Given SCU-worthy procedural features, creates points along the hydro network, then loads them into service layers.'
      self.canRunInBackground = True
      self.category = "Stream Conservation Unit Delineation Tools"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam('in_PF', "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input", "Biotics_ProcFeats")
      parm1 = defineParam('out_Points', "Output Network Points", "DEFeatureClass", "Required", "Output")
      parm2 = defineParam('fld_SFID', "Source Feature ID field", "String", "Required", "Input", 'SFID')
      parm3 = defineParam('in_downTrace', "Downstream Service Layer", "GPNALayer", "Required", "Input", 'naDownTrace')
      parm4 = defineParam('in_upTrace', "Upstream Service Layer", "GPNALayer", "Required", "Input", 'naUpTrace')
      parm5 = defineParam('out_Scratch', "Scratch Geodatabase", "DEWorkspace", "Optional", "Output")

      parms = [parm0, parm1, parm2, parm3, parm4, parm5]
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
      
      if out_Scratch != 'None':
         scratchParm = out_Scratch 
      else:
         scratchParm = "in_memory" 
      
      # Run the function
      MakeNetworkPts_scu(in_PF, out_Points, fld_SFID, in_downTrace, in_upTrace, scratchParm)
      
      return
      
class Lines_scu(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "2: Generate Linear SCUs"
      self.description = 'Solves the upstream and downstream service layers, and combines segments to create linear SCUs'
      self.canRunInBackground = True
      self.category = "Stream Conservation Unit Delineation Tools"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam('out_Lines', "Output Linear SCUs", "DEFeatureClass", "Required", "Output")
      parm1 = defineParam('in_downTrace', "Downstream Service Layer", "GPNALayer", "Required", "Input", 'naDownTrace')
      parm2 = defineParam('in_upTrace', "Upstream Service Layer", "GPNALayer", "Required", "Input", 'naUpTrace')
      parm3 = defineParam('out_Scratch', "Scratch Geodatabase", "DEWorkspace", "Optional", "Output")

      parms = [parm0, parm1, parm2, parm3]
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
      
      if out_Scratch != 'None':
         scratchParm = out_Scratch 
      else:
         scratchParm = arcpy.env.scratchGDB 
      
      # Run the function
      CreateLines_scu(out_Lines, in_downTrace, in_upTrace, scratchParm)
      
      return

class Polys_scu(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "3: Generate SCU Polygons"
      self.description = 'Given input linear SCUs, and NHD data, generates SCU polygons'
      self.canRunInBackground = True
      self.category = "Stream Conservation Unit Delineation Tools"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam('in_scuLines', "Input Linear SCUs", "GPFeatureLayer", "Required", "Input", "Biotics_ProcFeats")
      parm1 = defineParam("in_hydroGDB", "Input HydroNet geodatabase", "DEWorkspace", "Required", "Input")
      parm1.filter.list = ["Local Database"]
      parm2 = defineParam('out_Polys', "Output SCU Polygons", "DEFeatureClass", "Required", "Output")
      parm3 = defineParam('out_Scratch', "Scratch Geodatabase", "DEWorkspace", "Optional", "Output")

      parms = [parm0, parm1, parm2, parm3]
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
      
      if out_Scratch != 'None':
         scratchParm = out_Scratch 
      else:
         scratchParm = arcpy.env.scratchGDB 
      
      # Run the function
      CreatePolys_scu(in_scuLines, in_hydroGDB, out_Polys, scratchParm)
      
      return
      
class attribute_eo(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "1: Attribute Element Occurrences"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Site Prioritization Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm00 = defineParam("in_ProcFeats", "Input Procedural Features", "GPFeatureLayer", "Required", "Input")
      parm01 = defineParam("in_eoReps", "Input Element Occurrences (EOs)", "GPFeatureLayer", "Required", "Input")
      parm02 = defineParam("in_sppExcl", "Input Species Exclusion Table", "GPTableView", "Required", "Input")
      parm03 = defineParam("in_eoSelOrder", "Input EO Selection Order Table", "GPTableView", "Required", "Input")
      parm04 = defineParam("in_consLands", "Input Conservation Lands", "GPFeatureLayer", "Required", "Input")
      parm05 = defineParam("in_consLands_flat", "Input Flattened Conservation Lands", "GPFeatureLayer", "Required", "Input")
      parm06 = defineParam("out_procEOs", "Output Attributed EOs", "DEFeatureClass", "Required", "Output")
      parm07 = defineParam("out_sumTab", "Output Element Portfolio Summary Table", "DETable", "Required", "Output")

      parms = [parm00, parm01, parm02, parm03, parm04, parm05, parm06, parm07]
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

      AttributeEOs(in_ProcFeats, in_eoReps, in_sppExcl, in_eoSelOrder, in_consLands, in_consLands_flat, out_procEOs, out_sumTab)

      return (out_procEOs, out_sumTab)
      
class score_eo(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "2: Score Element Occurrences"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Site Prioritization Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm00 = defineParam("in_procEOs", "Input Attributed Element Occurrences (EOs)", "GPFeatureLayer", "Required", "Input")
      parm01 = defineParam("in_sumTab", "Input Element Portfolio Summary Table", "GPTableView", "Required", "Input")
      parm02 = defineParam("out_sortedEOs", "Output Scored EOs", "DEFeatureClass", "Required", "Output")

      parms = [parm00, parm01, parm02]
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
      
      # Run function
      ScoreEOs(in_procEOs, in_sumTab, out_sortedEOs)

      return (out_sortedEOs)
      
class build_portfolio(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "3: Build Conservation Portfolio"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Site Prioritization Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm00 = defineParam("in_sortedEOs", "Input Scored Element Occurrences (EOs)", "GPFeatureLayer", "Required", "Input")
      parm01 = defineParam("out_sortedEOs", "Output Prioritized Element Occurrences (EOs)", "GPFeatureLayer", "Required", "Output")
      parm02 = defineParam("in_sumTab", "Input Element Portfolio Summary Table", "GPTableView", "Required", "Input")
      parm03 = defineParam("out_sumTab", "Output Updated Element Portfolio Summary Table", "GPTableView", "Required", "Output")
      parm04 = defineParam("in_ConSites", "Input Conservation Sites", "GPFeatureLayer", "Required", "Input")
      parm05 = defineParam("out_ConSites", "Output Prioritized Conservation Sites", "GPFeatureLayer", "Required", "Output")
      parm06 = defineParam("build", "Portfolio Build Option", "String", "Required", "Input", "NEW")
      parm06.filter.list = ["NEW", "NEW_EO", "NEW_CS", "UPDATE"]

      parms = [parm00, parm01, parm02, parm03, parm04, parm05, parm06]
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

      # Run function
      BuildPortfolio(in_sortedEOs, out_sortedEOs, in_sumTab, out_sumTab, in_ConSites, out_ConSites, build)
      
      return (out_sortedEOs, out_sumTab, out_ConSites)      