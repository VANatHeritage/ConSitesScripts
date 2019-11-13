# ----------------------------------------------------------------------------------------
# ConSite-Tools.pyt
# Toolbox version: 1.1.1
# ArcGIS version: 10.3.1
# Python version: 2.7.8
# Creation Date: 2017-08-11
# Last Edit: 2019-08-28
# Creator:  Kirsten R. Hazler

# Summary:
# A toolbox for automatic delineation and prioritization of Natural Heritage Conservation Sites

# Usage Notes:
# Some tools for SCU delineation are set to run in foreground only, otherwise service layers would not update in map. 

### Toolbox Version Notes:
# Version 1.1.1 (= ECS version 1): Site delineation process is the same as Version 1.1. Essential ConSites process is changed from original as follows:
# - Added new tool: Build Element Lists
# - Added new function and tool to produce BMI score, and generalized to work with any polygon feature class
# - Attribute Element Occurrences tool: 
# --- Eliminated need for EO_reps feature class by using input ProcFeats that include necessary EO-level attributes
# --- Eliminated need for SelOrder table by hard-coding the selection order values
# --- Selection order changed so that E ranks equally with C?, rather than with C
# --- Eliminated military exclusion
# --- For calculating intersection with military land, selects ALL military lands, not just those with BMI > 2 
# --- Upgraded protection target for G1 Elements from 5 to 10
# --- Incorporates new ScoreBMI function
# - Score Element Occurrences tool:
# --- Initial scoring based on [military]/eo rank/last obs year/[number of PFs]
# --- Set "fuzz" factor for last obs year to 5 instead of 3
# --- Makes use of military land for ranking an option the user can select (default) or not
# --- Makes use of number of PFs for ranking an option the user can select (default) or not
# - Build Portfolio tool:
# --- Changed point system for assigning site conservation value, incorporating values for both representation status (irreplaceable, essential, priority, choice, surplus) and rarity (G-ranks).
# --- added BMI tabulation and scoring to ConSites
# --- Sequence:
# ---- * Initial portfolio update: All Irreplaceable, Essential, and Priority EOs added to Portfolio, along with their sites; and bycatch Choice EOs also added to portfolio
# ---- * Rank remaining Choice EOs on conservation site value; update slots, portfolio, and bycatch
# ---- * Rank remaining Choice EOs on NAP and BMI; update slots, portfolio, and bycatch
# ---- * Rank remaining Choice EOs on EO size to fill remaining slots.

# Version 1.1: Delineation process for Terrestrial Conservation Sites and Anthropogenic Habitat Zones remains unchanged from previous version, except for a slight modification of the shrinkwrap function to correct an anomaly that can arise when the SBB is the same as the PF. In addition to that change, this version incorporates the following changes:
# - Added tools for delineating Stream Conservation Units
# - Added tools for processing NWI data (ported over from another old toolbox)
# - Changed some toolset names
# - Moved some tools from one toolset to another (without change in functionality)
# - Modified some tool parameter defaults, in part to fix a bug that manifests when a layer's link to its data source is broken
# - Added tool for flattening Conservation Lands (prep for Essential ConSites input)
# - Added tool to dissolve procedural features to create "site-worthy" EOs
# - Added tool to automate B-ranking of sites

# Version 1.0: This was the version used for the first major overhaul/replacement of Terrestrial Conservation Sites and Anthropomorphic Habitat Zones, starting in 2018. Also includes tools for Essential Conservation Sites protocol, version 1.
# ----------------------------------------------------------------------------------------

import Helper
from Helper import *
from libConSiteFx import *
from CreateSBBs import *
from CreateConSites import *
from ReviewConSites import *
from CreateSCU import *
from PrioritizeConSites import *
from ProcNWI import *
from ProcConsLands import *

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
      self.tools = [coalesceFeats, shrinkwrapFeats, extract_biotics, dissolve_procfeats, create_sbb, expand_sbb, parse_sbb, create_consite, review_consite, assign_brank, ServLyrs_scu, NtwrkPts_scu, Lines_scu, Polys_scu, FlowBuffers_scu, Finalize_scu, attribute_eo, score_eo, build_portfolio, build_element_lists, tabparse_nwi, sbb2nwi, subset_nwi, flat_conslands, calc_bmi]

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

class shrinkwrapFeats(object):
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
      self.label = "Extract Biotics data"
      self.description = ""
      self.canRunInBackground = False
      # For some reason, this tool fails if run in the background.
      self.category = "Preparation and Review Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm0 = defineParam('BioticsPF', "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      try:
         parm0.value = "BIOTICS_DLINK.ProcFeats"
      except:
         pass
      parm1 = defineParam('BioticsCS', "Input Conservation Sites", "GPFeatureLayer", "Required", "Input")
      try:
         parm1.value = "BIOTICS_DLINK.ConSites"
      except:
         pass
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

class dissolve_procfeats(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "Dissolve Procedural Features by EO ID"
      self.description = "Dissolves input procedural features on EO-specific fields to create 'site-worthy' EOs for the purpose of ConSite prioritization, where EOs rather than PFs are needed."
      self.canRunInBackground = True
      self.category = "Preparation and Review Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm0 = defineParam("procFeats", "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      parm1 = defineParam("procEOs", "Output Site-worthy EOs", "DEFeatureClass", "Required", "Output")
      parm2 = defineParam("site_Type", "Site Type Association", "String", "Required", "Input")
      parm2.filter.list = ["TCS", "AHZ", "SCU", "KCS", "MACS"]
      
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
      dissolvePF (procFeats, procEOs, site_Type)

      return
      
class create_sbb(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "1: Create Site Building Blocks (SBBs)"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Site Delineation Tools: TCS/AHZ"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm0 = defineParam('in_PF', "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      try:
         parm0.value = "Biotics_ProcFeats"
      except:
         pass
      parm1 = defineParam('fld_SFID', "Source Feature ID field", "String", "Required", "Input", 'SFID')
      parm2 = defineParam('fld_Rule', "SBB Rule field", "String", "Required", "Input", 'RULE')
      parm3 = defineParam('fld_Buff', "SBB Buffer field", "String", "Required", "Input", 'BUFFER')
      parm4 = defineParam('in_nwi5', "Input Rule 5 NWI Features", "GPFeatureLayer", "Required", "Input")
      try:
         parm4.value = "VA_Wetlands_Rule5"
      except:
         pass
      parm5 = defineParam('in_nwi67', "Input Rule 67 NWI Features", "GPFeatureLayer", "Required", "Input")
      try:
         parm5.value = "VA_Wetlands_Rule67"
      except:
         pass
      parm6 = defineParam('in_nwi9', "Input Rule 9 NWI Features", "GPFeatureLayer", "Required", "Input")
      try:
         parm6.value = "VA_Wetlands_Rule9"
      except:
         pass
      parm7 = defineParam('out_SBB', "Output Site Building Blocks (SBBs)", "DEFeatureClass", "Required", "Output", "sbb")
      parm8 = defineParam('scratch_GDB', "Scratch Geodatabase", "DEWorkspace", "Optional", "Input")

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
      self.category = "Site Delineation Tools: TCS/AHZ"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm0 = defineParam('in_Cores', "Input Cores", "GPFeatureLayer", "Required", "Input")
      try:
         parm0.value = "Cores123\Cores123"
      except:
         pass
      parm1 = defineParam('in_SBB', "Input Site Building Blocks (SBBs)", "GPFeatureLayer", "Required", "Input")
      try: 
         parm1.value = "sbb"
      except:
         pass
      parm2 = defineParam('in_PF', "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      try:
         parm2.value = "Biotics_ProcFeats"
      except:
         pass
      parm3 = defineParam('joinFld', "Source Feature ID field", "String", "Required", "Input", 'SFID')
      parm4 = defineParam('out_SBB', "Output Expanded Site Building Blocks", "DEFeatureClass", "Required", "Output", "expanded_sbb")
      parm5 = defineParam('scratch_GDB', "Scratch Geodatabase", "DEWorkspace", "Optional", "Input")

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
      self.category = "Site Delineation Tools: TCS/AHZ"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm0 = defineParam('in_SBB', "Input Site Building Blocks", "GPFeatureLayer", "Required", "Input")
      try:
         parm0.value = "sbb"
      except:
         pass
      parm1 = defineParam('out_terrSBB', "Output Standard Terrestrial Site Building Blocks", "DEFeatureClass", "Required", "Output", "tcs_sbb")
      parm2 = defineParam('out_ahzSBB', "Output Anthropogenic Habitat Zone Site Building Blocks", "DEFeatureClass", "Required", "Output", "ahz_sbb")

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
      self.category = "Site Delineation Tools: TCS/AHZ"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm00 = defineParam("in_SBB", "Input Site Building Blocks (SBBs)", "GPFeatureLayer", "Required", "Input")
      parm01 = defineParam("ysn_Expand", "Expand SBB Selection?", "GPBoolean", "Required", "Input", "false")
      parm02 = defineParam("in_PF", "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      try:
         parm02.value = "Biotics_ProcFeats"
      except:
         pass
      parm03 = defineParam("joinFld", "Source Feature ID field", "String", "Required", "Input", "SFID")
      parm04 = defineParam("in_ConSites", "Input Current Conservation Sites", "GPFeatureLayer", "Required", "Input")
      try:
         parm04.value = "Biotics_ConSites"
      except:
         pass
      parm05 = defineParam("out_ConSites", "Output Updated Conservation Sites", "DEFeatureClass", "Required", "Output")
      parm06 = defineParam("site_Type", "Site Type", "String", "Required", "Input")
      parm06.filter.list = ["TERRESTRIAL", "AHZ"]
      parm07 = defineParam("in_Hydro", "Input Hydro Features", "GPFeatureLayer", "Required", "Input")
      try:
         parm07.value = "HydrographicFeatures"
      except:
         pass
      parm08 = defineParam("in_TranSurf", "Input Transportation Surfaces", "GPValueTable", "Optional", "Input")
      parm08.columns = [["GPFeatureLayer","Transportation Layers"]]
      try:
         parm08.values = [["VirginiaRailSurfaces"], ["VirginiaRoadSurfaces"]]
      except:
         pass
      parm08.enabled = False
      parm09 = defineParam("in_Exclude", "Input Exclusion Features", "GPFeatureLayer", "Optional", "Input")
      try:
         parm09.value = "ExclusionFeatures"
      except:
         pass
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
      self.label = "Review Conservation Sites"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Preparation and Review Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm00 = defineParam("auto_CS", "Input NEW Conservation Sites", "GPFeatureLayer", "Required", "Input")
      parm01 = defineParam("orig_CS", "Input OLD Conservation Sites", "GPFeatureLayer", "Required", "Input")
      parm02 = defineParam("cutVal", "Cutoff value (percent)", "GPDouble", "Required", "Input")
      parm03 = defineParam("out_Sites", "Output new Conservation Sites feature class with QC fields", "GPFeatureLayer", "Required", "Output", "ConSites_QC")
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

class assign_brank(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "Calculate biodiversity rank"
      self.description = ""
      self.canRunInBackground = False
      # Must run in foreground, otherwise table attribute fields don't refresh
      self.category = "Preparation and Review Tools"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_EO", "Input site-worthy EOs", "GPFeatureLayer", "Required", "Input")
      parm1 = defineParam("in_CS", "Input Conservation Sites", "GPFeatureLayer", "Required", "Input")

      parms = [parm0, parm1]
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
      
      getBRANK(in_EO, in_CS)

      return (in_EO, in_CS)
      
class ServLyrs_scu(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "Make Network Analyst Service Layers"
      self.description = 'Make two service layers needed for distance analysis along hydro network.'
      self.canRunInBackground = False
      self.category = "Preparation and Review Tools"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_hydroNet", "Input Hydro Network Dataset", "GPNetworkDatasetLayer", "Required", "Input")
      try:
         parm0.value = "HydroNet_ND"
      except:
         pass
      parm1 = defineParam("out_lyrDown", "Output Downstream Layer", "DELayer", "Derived", "Output")
      parm2 = defineParam("out_lyrUp", "Output Upstream Layer", "DELayer", "Derived", "Output")
      
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
      
      # Run the function
      (lyrDownTrace, lyrUpTrace) = MakeServiceLayers_scu(in_hydroNet)

      # Update the derived parameters.
      # This enables layers to be displayed automatically if running tool from ArcMap.
      parameters[1].value = lyrDownTrace
      parameters[2].value = lyrUpTrace
      
      return 
      
class NtwrkPts_scu(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "1: Make Network Points from Procedural Features"
      self.description = 'Given SCU-worthy procedural features, creates points along the hydro network, then loads them into service layers.'
      self.canRunInBackground = True
      self.category = "Site Delineation Tools: SCU"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_hydroNet", "Input Hydro Network Dataset", "GPNetworkDatasetLayer", "Required", "Input")
      try:
         parm0.value = "HydroNet_ND"
      except:
         pass
      parm1 = defineParam("in_PF", "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      try:
         parm1.value = "Biotics_ProcFeats"
      except:
         pass
      parm2 = defineParam("out_Points", "Output Network Points", "DEFeatureClass", "Required", "Output", "scuPoints")
      parm3 = defineParam("fld_SFID", "Source Feature ID field", "String", "Required", "Input", "SFID")
      parm4 = defineParam("out_Scratch", "Scratch Geodatabase", "DEWorkspace", "Optional", "Input")

      parms = [parm0, parm1, parm2, parm3, parm4]
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
      
      if out_Scratch != 'None':
         scratchParm = out_Scratch 
      else:
         scratchParm = "in_memory" 
      
      # Run the function
      scuPoints = MakeNetworkPts_scu(in_hydroNet, in_PF, out_Points, fld_SFID, scratchParm)
      
      return
      
class Lines_scu(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "2: Generate Linear SCUs"
      self.description = 'Solves the upstream and downstream service layers, and combines segments to create linear SCUs'
      self.canRunInBackground = True
      self.category = "Site Delineation Tools: SCU"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("out_Lines", "Output Linear SCUs", "DEFeatureClass", "Required", "Output", "scuLines")
      parm1 = defineParam("in_PF", "Input Procedural Features (PFs)", "GPFeatureLayer", "Required", "Input")
      try:
         parm1.value = "Biotics_ProcFeats"
      except:
         pass
      parm2 = defineParam("in_Points", "Input SCU Points", "GPFeatureLayer", "Required", "Input")
      try:
         parm2.value = "scuPoints"
      except:
         pass
      parm3 = defineParam("in_downTrace", "Downstream Service Layer", "GPNALayer", "Required", "Input")
      try:
         parm3.value = "naDownTrace"
      except:
         pass
      parm4 = defineParam("in_upTrace", "Upstream Service Layer", "GPNALayer", "Required", "Input")
      try:
         parm4.value = "naUpTrace"
      except:
         pass
      parm5 = defineParam("out_Scratch", "Scratch Geodatabase", "DEWorkspace", "Optional", "Input")

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
         scratchParm = arcpy.env.scratchGDB 
      
      # Run the function
      (scuLines, lyrDownTrace, lyrUpTrace) = CreateLines_scu(out_Lines, in_PF, in_Points, in_downTrace, in_upTrace, scratchParm)
          
      # Update the derived parameters.
      # This enables layers to be displayed automatically if running tool from ArcMap.
      parameters[3].value = lyrDownTrace
      parameters[4].value = lyrUpTrace
      
      return

class Polys_scu(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "3: Generate SCU Polygons"
      self.description = 'Given input linear SCUs, and NHD data, generates SCU polygons'
      self.canRunInBackground = True
      self.category = "Site Delineation Tools: SCU"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam('in_scuLines', "Input Linear SCUs", "GPFeatureLayer", "Required", "Input")
      try:
         parm0.value = "scuLines"
      except:
         pass
      parm1 = defineParam("in_hydroNet", "Input Hydro Network Dataset", "GPNetworkDatasetLayer", "Required", "Input")
      try:
         parm1.value = "HydroNet_ND"
      except:   
         pass
      parm2 = defineParam('out_Polys', "Output SCU Polygons", "DEFeatureClass", "Required", "Output", "scuPolys")
      parm3 = defineParam('out_Scratch', "Scratch Geodatabase", "DEWorkspace", "Optional", "Input")

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
      CreatePolys_scu(in_scuLines, in_hydroNet, out_Polys, scratchParm)
      
      return

class FlowBuffers_scu(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "4: Buffer SCU Polygons"
      self.description = 'Delineates buffers around polygon SCUs based on flow distance down to features (rather than straight distance)'
      self.canRunInBackground = True
      self.category = "Site Delineation Tools: SCU"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam('in_Polys', "Input Polygon SCUs", "GPFeatureLayer", "Required", "Input")
      try:
         parm0.value = "scuPolys"
      except:
         pass
      parm1 = defineParam("fld_ID", "Polygon ID field", "String", "Required", "Input", "OBJECTID")
      parm2 = defineParam("in_FlowDir", "Input Flow Direction Raster", "GPRasterLayer", "Required", "Input")
      try:
         parm2.value = "fdir_VA"
      except:
         pass
      parm3 = defineParam("out_Polys", "Output SCU Polygons", "DEFeatureClass", "Required", "Output")
      try:
         parm3.value = "scuFlowBuffers"
      except:
         pass
      parm4 = defineParam("maxDist", "Maximum Buffer Distance", "GPLinearUnit", "Required", "Input", "500 METERS")
      parm5 = defineParam('out_Scratch', "Scratch Geodatabase", "DEWorkspace", "Optional", "Input")

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
         field_names = [f.name for f in arcpy.ListFields(fc)]
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
      
      if out_Scratch != 'None':
         scratchParm = out_Scratch 
      else:
         scratchParm = arcpy.env.scratchGDB 
         
      # Run the function
      flowBuffs = CreateFlowBuffers_scu(in_Polys, fld_ID, in_FlowDir, out_Polys, maxDist, scratchParm)
      
      return

class Finalize_scu(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "5: Finalize Stream Conservation Sites"
      self.description = "Aggregates and smoothes buffered Stream Conservation Units to produce final output Stream Conservation Sites"
      self.canRunInBackground = True
      self.category = "Site Delineation Tools: SCU"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_Feats", "Input buffered SCU polygons", "GPFeatureLayer", "Required", "Input")
      try:
         parm0.value = "scuFlowBuffers"
      except: 
         pass
      parm1 = defineParam("dil_Dist", "Dilation distance", "GPLinearUnit", "Required", "Input", "10 METERS")
      parm2 = defineParam("out_Feats", "Output final Stream Conservation Sites", "DEFeatureClass", "Required", "Output")
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
      
class attribute_eo(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "1: Attribute Element Occurrences"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Conservation Portfolio Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm00 = defineParam("in_ProcFeats", "Input Procedural Features", "GPFeatureLayer", "Required", "Input")
      parm01 = defineParam("in_sppExcl", "Input Elements Exclusion Table", "GPTableView", "Required", "Input")
      parm02 = defineParam("in_consLands", "Input Conservation Lands", "GPFeatureLayer", "Required", "Input")
      parm03 = defineParam("in_consLands_flat", "Input Flattened Conservation Lands", "GPFeatureLayer", "Required", "Input")
      parm04 = defineParam("in_ecoReg", "Input Ecoregions", "GPFeatureLayer", "Required", "Input")
      parm05 = defineParam("fld_RegCode", "Ecoregion ID field", "String", "Required", "Input")
      parm06 = defineParam("cutYear", "Cutoff observation year", "GPLong", "Required", "Input", "1994")
      parm07 = defineParam("out_procEOs", "Output Attributed EOs", "DEFeatureClass", "Required", "Output", "attribEOs")
      parm08 = defineParam("out_sumTab", "Output Element Portfolio Summary Table", "DETable", "Required", "Output", "sumTab")

      parms = [parm00, parm01, parm02, parm03, parm04, parm05, parm06, parm07, parm08]
      return parms

   def isLicensed(self):
      """Set whether tool is licensed to execute."""
      return True

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed."""
      if parameters[4].altered:
         fc = parameters[4].valueAsText
         field_names = [f.name for f in arcpy.ListFields(fc)]
         parameters[5].filter.list = field_names
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""
      # Set up parameter names and values
      declareParams(parameters)

      AttributeEOs(in_ProcFeats, in_sppExcl, in_consLands, in_consLands_flat, in_ecoReg, fld_RegCode, cutYear, out_procEOs, out_sumTab)

      return (out_procEOs, out_sumTab)
      
class score_eo(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "2: Score Element Occurrences"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Conservation Portfolio Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm00 = defineParam("in_procEOs", "Input Attributed Element Occurrences (EOs)", "GPFeatureLayer", "Required", "Input")
      try:
         parm00.value = "attribEOs"
      except:
         pass
      parm01 = defineParam("in_sumTab", "Input Element Portfolio Summary Table", "GPTableView", "Required", "Input")
      try:  
         parm01.value = "sumTab"
      except:
         pass
      parm02 = defineParam("out_sortedEOs", "Output Scored EOs", "DEFeatureClass", "Required", "Output", "scoredEOs")
      parm03 = defineParam("ysnMil", "Use military land as ranking factor?", "GPBoolean", "Required", "Input", "true")
      parm04 = defineParam("ysnYear", "Use observation year as ranking factor?", "GPBoolean", "Required", "Input", "false")

      parms = [parm00, parm01, parm02, parm03, parm04]
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
      ScoreEOs(in_procEOs, in_sumTab, out_sortedEOs, ysnMil, ysnYear)

      return (out_sortedEOs)
      
class build_portfolio(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "3: Build Conservation Portfolio"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Conservation Portfolio Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm00 = defineParam("build", "Portfolio Build Option", "String", "Required", "Input", "NEW")
      parm00.filter.list = ["NEW", "NEW_EO", "NEW_CS", "UPDATE"]
      parm01 = defineParam("in_sortedEOs", "Input Scored Element Occurrences (EOs)", "GPFeatureLayer", "Required", "Input")
      try:
         parm01.value = "scoredEOs"
      except:
         pass
      parm02 = defineParam("out_sortedEOs", "Output Prioritized Element Occurrences (EOs)", "DEFeatureClass", "Required", "Output", "priorEOs")
      parm03 = defineParam("in_sumTab", "Input Element Portfolio Summary Table", "GPTableView", "Required", "Input")
      try:
         parm03.value = "sumTab"
      except:
         pass
      parm04 = defineParam("out_sumTab", "Output Updated Element Portfolio Summary Table", "DETable", "Required", "Output", "sumTab_upd")
      parm05 = defineParam("in_ConSites", "Input Conservation Sites", "GPFeatureLayer", "Required", "Input")
      parm06 = defineParam("out_ConSites", "Output Prioritized Conservation Sites", "DEFeatureClass", "Required", "Output", "priorConSites")
      parm07 = defineParam("in_consLands_flat", "Input Flattened Conservation Lands", "GPFeatureLayer", "Required", "Input")

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

      # Run function
      BuildPortfolio(in_sortedEOs, out_sortedEOs, in_sumTab, out_sumTab, in_ConSites, out_ConSites, in_consLands_flat, build)
      
      return (out_sortedEOs, out_sumTab, out_ConSites)      
      
class build_element_lists(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "4: Build Element Lists"
      self.description = ""
      self.canRunInBackground = True
      self.category = "Conservation Portfolio Tools"

   def getParameterInfo(self):
      """Define parameter definitions"""
      parm00 = defineParam("in_Bounds", "Input Boundary Polygons", "GPFeatureLayer", "Required", "Input")
      parm01 = defineParam("fld_ID", "Boundary ID field", "String", "Required", "Input")
      parm02 = defineParam("in_procEOs", "Input Prioritized EOs", "GPFeatureLayer", "Required", "Input")
      try:
         parm02.value = "priorEOs"
      except:
         pass
      parm03 = defineParam("in_elementTab", "Input Element Portfolio Summary Table", "GPTableView", "Required", "Input")
      try:
         parm03.value = "sumTab_upd"
      except:
         pass
      parm04 = defineParam("out_Tab", "Output Element-Boundary Summary", "DETable", "Required", "Output")
      parm05 = defineParam("out_Excel", "Output Excel File", "DEFile", "Optional", "Output")

      parms = [parm00, parm01, parm02, parm03, parm04, parm05]
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
         parameters[1].filter.list = field_names
      if parameters[5].valueAsText is not None:
         if not parameters[5].valueAsText.endswith('xls'):
            parameters[5].value = parameters[5].valueAsText.split('.')[0] + '.xls'
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
      BuildElementLists(in_Bounds, fld_ID, in_procEOs, in_elementTab, out_Tab, out_Excel)
      
      return (out_Tab)      
 
class tabparse_nwi(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "1: Parse NWI codes"
      self.description = 'Tabulates unique NWI codes, then parses them into user-friendly attribute fields.'
      self.canRunInBackground = True
      self.category = "NWI Processing Tools"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_NWI", "Input NWI polygons", "GPFeatureLayer", "Required", "Input", "VA_Wetlands")
      parm1 = defineParam("out_Tab", "Output code table", "DETable", "Required", "Output", "[yourpath]\VA_Wetlands_Codes")
      parms = [parm0, parm1]
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

      TabParseNWI(in_NWI, out_Tab)
      
      return out_Tab
      
class sbb2nwi(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "2: Assign SBB rules to NWI"
      self.description = 'Assigns SBB rules 5, 6, 7, and 9 to applicable NWI codes'
      self.canRunInBackground = True
      self.category = "NWI Processing Tools"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_Tab", "Input NWI code table", "GPTableView", "Required", "Input", "VA_Wetlands_Codes")
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

      SbbToNWI(in_Tab)
      
      return in_Tab      
      
class subset_nwi(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "3: Create NWI subsets"
      self.description = 'Creates NWI subsets applicable to SBB rules 5, 6, 7, and 9'
      self.canRunInBackground = True
      self.category = "NWI Processing Tools"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_NWI", "Input NWI polygons", "GPFeatureLayer", "Required", "Input", "VA_Wetlands")
      parm1 = defineParam("in_Tab", "Input NWI code table", "GPTableView", "Required", "Input", "VA_Wetlands_Codes")
      parm2 = defineParam('in_GDB', "Geodatabase for storing outputs", "DEWorkspace", "Required", "Input")
      parm2.filter.list = ["Local Database"]
      
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

      SubsetNWI(in_NWI, in_Tab, in_GDB)
      
      return in_Tab  
      
class flat_conslands(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "Flatten Conservation Lands"
      self.description = 'Removes overlaps in Conservation Lands, dissolving and updating based on BMI field'
      self.canRunInBackground = True
      self.category = "Preparation and Review Tools"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_CL", "Input Conservation Lands polygons", "GPFeatureLayer", "Required", "Input")
      parm1 = defineParam("out_CL", "Output flattened Conservaton Lands", "DEFeatureClass", "Required", "Output")
      parm2 = defineParam('scratch_GDB', "Geodatabase for storing scratch outputs", "DEWorkspace", "Optional", "Input")
      parm2.filter.list = ["Local Database"]
      
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
      
      if scratch_GDB != 'None':
         scratchParm = scratch_GDB 
      else:
         scratchParm = arcpy.env.scratchGDB

      bmiFlatten(in_CL, out_CL, scratchParm)
      
      return out_CL  
      
class calc_bmi(object):
   def __init__(self):
      """Define the tool (tool name is the name of the class)."""
      self.label = "Calculate BMI Score"
      self.description = 'For any input polygons, calculates a score for Biological Management Intent'
      self.canRunInBackground = False
      self.category = "Preparation and Review Tools"

   def getParameterInfo(self):
      """Define parameters"""
      parm0 = defineParam("in_Feats", "Input polygon features", "GPFeatureLayer", "Required", "Input")
      parm1 = defineParam("fld_ID", "Polygon ID field", "String", "Required", "Input")
      parm2 = defineParam("in_BMI", "Input BMI Polygons", "GPFeatureLayer", "Required", "Input")
      parm3 = defineParam("fld_Basename", "Base name for output fields", "String", "Required", "Input", "PERCENT_BMI_")
      
      parms = [parm0, parm1, parm2, parm3]
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
      
      ScoreBMI(in_Feats, fld_ID, in_BMI, fld_Basename)
      
      return in_Feats  