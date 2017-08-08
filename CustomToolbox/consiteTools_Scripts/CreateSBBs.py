# ----------------------------------------------------------------------------------------
# CreateSBBs.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016-01-29
# Last Edit: 2016-09-16
# Creator:  Kirsten R. Hazler
#
# Summary:
#  Creates rule-specific Site Building Blocks (SBBs) from Procedural Features (PFs). 
# ----------------------------------------------------------------------------------------
ScriptDate = '2016-09-16' # Used for informative message down below

# Import necessary modules
import arcpy, os, sys, traceback

# Get path to toolbox, then import it
# Scenario 1:  script is in separate folder within folder holding toolbox
tbx1 = os.path.abspath(os.path.join(sys.argv[0],"../..", "consiteTools.tbx"))
# Scenario 2:  script is embedded in tool
tbx2 = os.path.abspath(os.path.join(sys.argv[0],"..", "consiteTools.tbx"))
if os.path.isfile(tbx1):
   arcpy.ImportToolbox(tbx1)
elif os.path.isfile(tbx2):
   arcpy.ImportToolbox(tbx2)
else:
   arcpy.AddError('Required toolbox not found.  Check script for errors.')

# Script arguments to be input by user...
Input_PF = arcpy.GetParameterAsText(0) 
   # An input feature class or feature layer representing Procedural Features
fld_SFID = arcpy.GetParameterAsText(1) 
   # The name of the field containing the unique source feature ID
fld_Rule = arcpy.GetParameterAsText(2) 
   # The name of the field containing the SBB fule to apply
fld_Buffer = arcpy.GetParameterAsText(3) 
   # The name of the field containing the buffer distance to apply, where applicable
Input_NWI5 = arcpy.GetParameterAsText(4) 
   # An input feature class or feature layer representing National Wetlands Inventory
   # This must be a subset containing features applicable to rule 5 only, with boundaries 
   # of adjacent polygons dissolved
Input_NWI67 = arcpy.GetParameterAsText(5) 
   # An input feature class or feature layer representing National Wetlands Inventory
   # This must be a subset containing features applicable to rules 6 and 7 only, with 
   # boundaries of adjacent polygons dissolved
Input_NWI9 = arcpy.GetParameterAsText(6) 
   # An input feature class or feature layer representing National Wetlands Inventory
   # This must be a subset containing features applicable to rule 9 only, with boundaries 
   # of adjacent polygons dissolved
scratchGDB = arcpy.GetParameterAsText(7) 
   # A geodatabase for storing intermediate/scratch products
Output_SBB = arcpy.GetParameterAsText(8) 
   # An output feature class representing Site Building Blocks

# Set overwrite option so that existing data may be overwritten
arcpy.env.overwriteOutput = True 
   
# Define functions for generating warning messages
def warnings(rule):
   warnMsgs = arcpy.GetMessages(1)
   if warnMsgs:
      arcpy.AddWarning('Finished processing Rule %s, but there were some problems.' % str(rule))
      arcpy.AddWarning(warnMsgs)
   else:
      arcpy.AddMessage('Rule %s SBBs completed' % str(rule))
      
def tback():
   tb = sys.exc_info()[2]
   tbinfo = traceback.format_tb(tb)[0]
   pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
   msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

   arcpy.AddError(msgs)
   arcpy.AddError(pymsg)
   arcpy.AddMessage(arcpy.GetMessages(1))

# Make a stupid joke   
arcpy.AddMessage('Why did the programmer cross the road?')
arcpy.AddMessage('To get away from the Python.')
arcpy.AddMessage('Ha ha ha.')
      
# Print helpful messages to geoprocessing window
arcpy.AddMessage("Your input feature class is: \n %s" % Input_PF)
arcpy.AddMessage("Your Rule 5 wetlands are:")
arcpy.AddMessage(Input_NWI5)
arcpy.AddMessage("Your Rule 6/7 wetlands are:")
arcpy.AddMessage(Input_NWI67)
arcpy.AddMessage("Your Rule 9 wetlands are:")
arcpy.AddMessage(Input_NWI9)
arcpy.AddMessage("Your output dataset is:")
arcpy.AddMessage(Output_SBB)
arcpy.AddMessage("Some scratch products, including rule-specific groups of SBBs, will be stored here:")
arcpy.AddMessage(scratchGDB)
arcpy.AddMessage("The running script was last edited %s" % ScriptDate)

try:
   arcpy.AddMessage('Prepping input procedural features')
   # Process: Copy Features
   tmpPF = scratchGDB + os.sep + 'tmpPF'
   arcpy.CopyFeatures_management(Input_PF, tmpPF, "", "0", "0", "0")

   # Process: Add Field (fltBuffer)
   arcpy.AddField_management(tmpPF, "fltBuffer", "FLOAT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

   # Process: Add Field (intRule)
   arcpy.AddField_management(tmpPF, "intRule", "SHORT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

   # Process: Calculate Field (intRule)
   expression1 = "string2int(!" + fld_Rule + "!)"
   codeblock1 = """def string2int(RuleString):
      try:
         RuleInteger = int(RuleString)
      except:
         RuleInteger = 0
      return RuleInteger"""
   arcpy.CalculateField_management(tmpPF, "intRule", expression1, "PYTHON", codeblock1)

   # Process: Calculate Field (fltBuffer)
	# Note that code here will have to change if changes are made to buffer standards
   expression2 = "string2float(!intRule!, !" + fld_Buffer + "!)"
   codeblock2 = """def string2float(RuleInteger, BufferString):  
		if RuleInteger == 1:
			BufferFloat = 150
		elif RuleInteger in (2,3,4,8,14):
			BufferFloat = 250
		elif RuleInteger in (11,12):
			BufferFloat = 450
		else:
			try:
				BufferFloat = float(BufferString)
			except:
				BufferFloat = 0
		return BufferFloat"""
   arcpy.CalculateField_management(tmpPF, "fltBuffer", expression2, "PYTHON", codeblock2)

except:
   arcpy.AddError('Unable to complete intitial pre-processing necessary for all further steps.')
   tback()
   quit()

arcpy.AddMessage('Beginning SBB creation.')
try:
   arcpy.AddMessage('Processing the simple defined-buffer features')
   # Process: Select (Defined Buffer Rules)
   PF_DefBuff = scratchGDB + os.sep + 'PF_DefBuff'
   arcpy.Select_analysis(tmpPF, PF_DefBuff, "( intRule in (1,2,3,4,8,10,11,12,13,14)) AND ( fltBuffer <> 0)")

   # Process: Buffer
   SBB_DefBuff = scratchGDB + os.sep + 'SBB_DefBuff'
   arcpy.Buffer_analysis(PF_DefBuff, SBB_DefBuff, "fltBuffer", "FULL", "ROUND", "NONE", "", "PLANAR")
   arcpy.AddMessage('Simple buffer SBBs completed')
except:
   arcpy.AddWarning('Unable to process the simple buffer features')
   tback()

try:
   arcpy.AddMessage('Processing the no-buffer features')
   # Process: Select (No-Buffer Rules)
   SBB_NoBuff = scratchGDB + os.sep + 'SBB_NoBuff'
   arcpy.Select_analysis(tmpPF, SBB_NoBuff, "(intRule = 15) OR ((intRule = 13) and (fltBuffer = 0))")
   arcpy.AddMessage('No-buffer SBBs completed')
except:
   arcpy.AddWarning('Unable to process the no-buffer features.')
   tback()

try:
   arcpy.AddMessage('Processing the Rule 5 features')
   # Process: Make Feature Layer (Rule 5)
   arcpy.MakeFeatureLayer_management(tmpPF, "lyr_PF5", "intRule = 5")

   # Process: Create Rule 5 Site Building Blocks
   SBB_rule5 = scratchGDB + os.sep + 'SBB_rule5'
   arcpy.CreateWetlandSBB_consiteTools("lyr_PF5", fld_SFID, Input_NWI5, SBB_rule5)
   warnings(5)
except:
   arcpy.AddWarning('Unable to process Rule 5 features')
   tback()

try:
   arcpy.AddMessage('Processing the Rule 6 features')
   # Process: Make Feature Layer (Rule 6)
   arcpy.MakeFeatureLayer_management(tmpPF, "lyr_PF6", "intRule = 6")

   # Process: Create Rule 6 Site Building Blocks
   SBB_rule6 = scratchGDB + os.sep + 'SBB_rule6'
   arcpy.CreateWetlandSBB_consiteTools("lyr_PF6", fld_SFID, Input_NWI67, SBB_rule6)
   warnings(6)
except:
   arcpy.AddWarning('Unable to process Rule 6 features')
   tback()

try:
   arcpy.AddMessage('Processing the Rule 7 features')
   # Process: Make Feature Layer (Rule 7)
   arcpy.MakeFeatureLayer_management(tmpPF, "lyr_PF7", "intRule = 7")

   # Process: Create Rule 7 Site Building Blocks
   SBB_rule7 = scratchGDB + os.sep + 'SBB_rule7'
   arcpy.CreateWetlandSBB_consiteTools("lyr_PF7", fld_SFID, Input_NWI67, SBB_rule7)
   warnings(7)
except:
   arcpy.AddWarning('Unable to process Rule 7 features')
   tback()

# Rule 8 is now treated as a simple defined-buffer rule.  
# This part can be uncommented if there is a new Rule 8 routine to incorporate in the future.
# try:
   # arcpy.AddMessage('Processing the Rule 8 features')
   # # Process: Make Feature Layer (Rule 8)
   # arcpy.MakeFeatureLayer_management(tmpPF, "lyr_PF8", "intRule = 8")

   # # Process: Create Rule 8 Site Building Blocks
   # SBB_rule8 = scratchGDB + os.sep + 'SBB_rule8'
   # arcpy.CreateRule8SBB_consiteTools("lyr_PF8", fld_SFID, SBB_rule8)
   # warnings(8)
# except:
   # arcpy.AddWarning('Unable to process Rule 8 features')
   # tback()

try:
   arcpy.AddMessage('Processing the Rule 9 features')
   # Process: Make Feature Layer (Rule 9)
   arcpy.MakeFeatureLayer_management(tmpPF, "lyr_PF9", "intRule = 9")

   # Process: Create Rule 9 Site Building Blocks
   SBB_rule9 = scratchGDB + os.sep + 'SBB_rule9'
   arcpy.CreateWetlandSBB_consiteTools("lyr_PF9", fld_SFID, Input_NWI9, SBB_rule9)
   warnings(9)
except:
   arcpy.AddWarning('Unable to process Rule 9 features')
   tback()

try:
   arcpy.AddMessage('Merging all the SBB features into one feature class')
   # Process: Merge
	# Note:  If Rule 8 goes back to getting its own procedure, will need to add SBB_rule8 to inputs below
   inputs = [SBB_DefBuff, SBB_NoBuff, SBB_rule5, SBB_rule6, SBB_rule7, SBB_rule9]
   arcpy.Merge_management (inputs, Output_SBB)

except:
   arcpy.AddWarning('Unable to create final output')
   tback()




























