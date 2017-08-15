# ----------------------------------------------------------------------------------------
# CreateSBBs.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016-01-29
# Last Edit: 2017-08-15
# Creator:  Kirsten R. Hazler
#
# Summary:
#  Creates rule-specific Site Building Blocks (SBBs) from Procedural Features (PFs). 
# ----------------------------------------------------------------------------------------
# Import function library and settings
import libConSiteFx 
from libConSiteFx import tback, garbagePickup, createTmpWorkspace


# Define functions for generating warning messages
def warnings(rule):
   warnMsgs = arcpy.GetMessages(1)
   if warnMsgs:
      arcpy.AddWarning('Finished processing Rule %s, but there were some problems.' % str(rule))
      arcpy.AddWarning(warnMsgs)
   else:
      arcpy.AddMessage('Rule %s SBBs completed' % str(rule))

def PrepProcFeats(in_PF, tmpWorkspace):
   try:
      # Process: Copy Features
      tmpPF = tmpWorkspace + os.sep + 'tmpPF'
      arcpy.CopyFeatures_management(in_PF, tmpPF)

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
      expression2 = "string2float(!intRule!, !" + fld_Buff + "!)"
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
      return tmpPF
   except:
      arcpy.AddError('Unable to complete intitial pre-processing necessary for all further steps.')
      tback()
      quit()
      
def CreateStandardSBB(inPF, subPF, outSBB, buffField):
   try:
      # Process: Select (Defined Buffer Rules)
      selQry = "( intRule in (1,2,3,4,8,10,11,12,13,14)) AND ( fltBuffer <> 0)"
      arcpy.Select_analysis(tmpPF, subPF, selQry)
      
      # Process: Buffer
      arcpy.Buffer_analysis(subPF, outSBB, buffField, "FULL", "ROUND", "NONE", "", "PLANAR")
      arcpy.AddMessage('Simple buffer SBBs completed and stored in %s' % outSBB)
      return outSBB
   except:
      arcpy.AddWarning('Unable to process the simple buffer features')
      tback()
   
def CreateNoBuffSBB(inPF, outSBB):
   try:
      # Process: Select (No-Buffer Rules)
      selQry = "(intRule = 15) OR ((intRule = 13) and (fltBuffer = 0))"
      arcpy.Select_analysis(inPF, outSBB, selQry)
      arcpy.AddMessage('No-buffer SBBs completed and stored in %s' % outSBB)
      return outSBB
   except:
      arcpy.AddWarning('Unable to process the no-buffer features.')
      tback()
      
def CreateSBBs(in_PF, fld_SFID, fld_Rule, fld_Buff, in_nwi5, in_nwi67, in_nwi9, out_SBB, scratchGDB = "in_memory"):

   # Print helpful message to geoprocessing window
   getScratchMsg(scratchGDB)
   
   # Set up some variables
   tmpWorkspace = createTmpWorkspace()
   arcpy.AddMessage("Additional critical temporary products will be stored here: %s" % tmpWorkspace)
   subPF = scratchGDB + os.sep + 'subPF' # for storing PF subsets

   # Set up trashList for later garbage collection
   trashList = [subPF]
   
   # Prepare input procedural featuers
   arcpy.AddMessage('Prepping input procedural features')
   tmpPF = PrepProcFeats(in_PF, tmpWorkspace)

   # Make SBBs
   arcpy.AddMessage('Beginning SBB creation...')
   
   # Standard buffer SBBs
   arcpy.AddMessage('Processing the simple defined-buffer features...')
   SBB_StdBuff = tmpWorkspace + os.sep + 'SBB_StdBuff'
   CreateStandardSBB(tmpPF, subPF, SBB_StdBuff, 'fltBuffer')

   # No buffer SBBs
   arcpy.AddMessage('Processing the no-buffer features')
   SBB_NoBuff = tmpWorkspace + os.sep + 'SBB_NoBuff'
   CreateNoBuffSBB(tmpPF, SBB_NoBuff)

   # Rule 5 SBBs
   arcpy.AddMessage('Processing the Rule 5 features')
   try:
      # Process: Make Feature Layer (Rule 5)
      arcpy.MakeFeatureLayer_management(tmpPF, "tmpLyr", "intRule = 5")

      # Process: Create Rule 5 Site Building Blocks
      SBB_rule5 = scratchGDB + os.sep + 'SBB_rule5'
      arcpy.CreateWetlandSBB_consiteTools("tmpLyr", fld_SFID, in_nwi5, SBB_rule5)
      warnings(5)
   except:
      arcpy.AddWarning('Unable to process Rule 5 features')
      tback()

   arcpy.AddMessage('Processing the Rule 6 features')
   try:
      
      # Process: Make Feature Layer (Rule 6)
      arcpy.MakeFeatureLayer_management(tmpPF, "lyr_PF6", "intRule = 6")

      # Process: Create Rule 6 Site Building Blocks
      SBB_rule6 = scratchGDB + os.sep + 'SBB_rule6'
      arcpy.CreateWetlandSBB_consiteTools("lyr_PF6", fld_SFID, in_nwi67, SBB_rule6)
      warnings(6)
   except:
      arcpy.AddWarning('Unable to process Rule 6 features')
      tback()

   arcpy.AddMessage('Processing the Rule 7 features')
   try:      
      # Process: Make Feature Layer (Rule 7)
      arcpy.MakeFeatureLayer_management(tmpPF, "lyr_PF7", "intRule = 7")

      # Process: Create Rule 7 Site Building Blocks
      SBB_rule7 = scratchGDB + os.sep + 'SBB_rule7'
      arcpy.CreateWetlandSBB_consiteTools("lyr_PF7", fld_SFID, in_nwi67, SBB_rule7)
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

   arcpy.AddMessage('Processing the Rule 9 features')
   try:
      
      # Process: Make Feature Layer (Rule 9)
      arcpy.MakeFeatureLayer_management(tmpPF, "lyr_PF9", "intRule = 9")

      # Process: Create Rule 9 Site Building Blocks
      SBB_rule9 = scratchGDB + os.sep + 'SBB_rule9'
      arcpy.CreateWetlandSBB_consiteTools("lyr_PF9", fld_SFID, in_nwi9, SBB_rule9)
      warnings(9)
   except:
      arcpy.AddWarning('Unable to process Rule 9 features')
      tback()

   arcpy.AddMessage('Merging all the SBB features into one feature class')
   try:      
      # Process: Merge
      # Note:  If Rule 8 goes back to getting its own procedure, will need to add SBB_rule8 to inputs below
      inputs = [SBB_DefBuff, SBB_NoBuff, SBB_rule5, SBB_rule6, SBB_rule7, SBB_rule9]
      arcpy.Merge_management (inputs, out_SBB)

   except:
      arcpy.AddWarning('Unable to create final output')
      tback()

   return out_SBB
















