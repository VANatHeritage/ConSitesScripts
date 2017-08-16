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
# Import function libraries and settings
import libConSiteFx
from libConSiteFx import *
from CreateStandardWetlandSBB import CreateWetlandSBB

# Define various functions
def warnings(rule):
   '''Generates warning messages specific to SBB rules'''
   warnMsgs = arcpy.GetMessages(1)
   if warnMsgs:
      arcpy.AddWarning('Finished processing Rule %s, but there were some problems.' % str(rule))
      arcpy.AddWarning(warnMsgs)
   else:
      arcpy.AddMessage('Rule %s SBBs completed' % str(rule))

def PrepProcFeats(in_PF, tmpWorkspace):
   '''Makes a copy of the Procedural Features, preps them for SBB processing'''
   try:
      # Process: Copy Features
      tmp_PF = tmpWorkspace + os.sep + 'tmp_PF'
      arcpy.CopyFeatures_management(in_PF, tmp_PF)

      # Process: Add Field (fltBuffer)
      arcpy.AddField_management(tmp_PF, "fltBuffer", "FLOAT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

      # Process: Add Field (intRule)
      arcpy.AddField_management(tmp_PF, "intRule", "SHORT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

      # Process: Calculate Field (intRule)
      expression1 = "string2int(!" + fld_Rule + "!)"
      codeblock1 = """def string2int(RuleString):
         try:
            RuleInteger = int(RuleString)
         except:
            RuleInteger = 0
         return RuleInteger"""
      arcpy.CalculateField_management(tmp_PF, "intRule", expression1, "PYTHON", codeblock1)

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
      arcpy.CalculateField_management(tmp_PF, "fltBuffer", expression2, "PYTHON", codeblock2)

      return tmp_PF
   except:
      arcpy.AddError('Unable to complete intitial pre-processing necessary for all further steps.')
      tback()
      quit()

def CreateStandardSBB(in_PF, out_SBB, fld_Buff, scratchGDB = "in_memory"):
   '''Creates standard buffer SBBs for specified subset of PFs'''
   try:
      # Process: Select (Defined Buffer Rules)
      selQry = "(intRule in (1,2,3,4,8,10,11,12,13,14)) AND ( fltBuffer <> 0)"
      arcpy.MakeFeatureLayer_management(in_PF, "tmpLyr", selQry)

      # Count records and proceed accordingly
      count = getCount("tmpLyr")
      if count > 0:
         # Process: Buffer
         tmpSBB = scratchGDB + os.sep + 'tmpSBB'
         arcpy.Buffer_analysis("tmpLyr", tmpSBB, fld_Buff, "FULL", "ROUND", "NONE", "", "PLANAR")
         # Append to output and cleanup
         arcpy.Append_management (tmpSBB, out_SBB, "NO_TEST")
         arcpy.AddMessage('Simple buffer SBBs completed')
         garbagePickup([tmpSBB])
      else:
         arcpyAddMessage('There are no PFs using the simple buffer rules')
   except:
      arcpy.AddWarning('Unable to process the simple buffer features')
      tback()

def CreateNoBuffSBB(in_PF, out_SBB):
   '''Creates SBBs that are simple copies of PFs for specified subset'''
   try:
      # Process: Select (No-Buffer Rules)
      selQry = "(intRule = 15) OR ((intRule = 13) and (fltBuffer = 0))"
      arcpy.MakeFeatureLayer_management(in_PF, "tmpLyr", selQry)

      # Count records and proceed accordingly
      count = getCount("tmpLyr")
      if count > 0:
         # Append to output and cleanup
         arcpy.Append_management ("tmpLyr", out_SBB, "NO_TEST")
         arcpy.AddMessage('No-buffer SBBs completed')
         garbagePickup([tmpSBB])
      else:
         arcpyAddMessage('There are no PFs using the no-buffer rules')
   except:
      arcpy.AddWarning('Unable to process the no-buffer features.')
      tback()

def CreateSBBs(in_PF, fld_SFID, fld_Rule, fld_Buff, in_nwi5, in_nwi67, in_nwi9, out_SBB, scratchGDB = "in_memory"):
   '''Creates SBBs for all input PFs, subsetting and applying rules as needed'''

   # Print helpful message to geoprocessing window
   getScratchMsg(scratchGDB)

   # Set up some variables
   tmpWorkspace = createTmpWorkspace()
   sr = arcpy.Describe(in_PF).spatialReference
   arcpy.AddMessage("Additional critical temporary products will be stored here: %s" % tmpWorkspace)
   sub_PF = scratchGDB + os.sep + 'sub_PF' # for storing PF subsets

   # Set up trashList for later garbage collection
   trashList = [sub_PF]

   # Prepare input procedural featuers
   arcpy.AddMessage('Prepping input procedural features')
   tmp_PF = PrepProcFeats(in_PF, tmpWorkspace)
   trashList.append(tmp_PF)

   arcpy.AddMessage('Beginning SBB creation...')

   # Create empty feature class to store SBBs
   arcpy.CreateFeatureclass_management (tmpWorkspace, out_SBB, "POLYGON", tmp_PF, '', '', sr)

   # Standard buffer SBBs
   arcpy.AddMessage('Processing the simple defined-buffer features...')
   CreateStandardSBB(tmp_PF, out_SBB, 'fltBuffer')

   # No buffer SBBs
   arcpy.AddMessage('Processing the no-buffer features')
   CreateNoBuffSBB(tmp_PF, out_SBB)

   # Rule 5 SBBs
   arcpy.AddMessage('Processing the Rule 5 features')
   selQry = "intRule = 5"
   in_NWI = in_nwi5
   try:
      CreateWetlandSBB(tmp_PF, fld_SFID, selQry, in_NWI, out_SBB, tmpWorkspace, "in_memory")
      warnings(5)
   except:
      arcpy.AddWarning('Unable to process Rule 5 features')
      tback()

   # Rule 6 SBBs
   arcpy.AddMessage('Processing the Rule 6 features')
   selQry = "intRule = 6"
   in_NWI = in_nwi67
   try:
      CreateWetlandSBB(tmp_PF, fld_SFID, selQry, in_NWI, out_SBB, tmpWorkspace, "in_memory")
      warnings(6)
   except:
      arcpy.AddWarning('Unable to process Rule 6 features')
      tback()

   # Rule 7 SBBs
   arcpy.AddMessage('Processing the Rule 7 features')
   selQry = "intRule = 7"
   in_NWI = in_nwi67
   try:
      CreateWetlandSBB(tmp_PF, fld_SFID, selQry, in_NWI, out_SBB, tmpWorkspace, "in_memory")
      warnings(7)
   except:
      arcpy.AddWarning('Unable to process Rule 7 features')
      tback()

   # Rule 9 SBBs
   arcpy.AddMessage('Processing the Rule 9 features')
   selQry = "intRule = 9"
   in_NWI = in_nwi9
   try:
      CreateWetlandSBB(tmp_PF, fld_SFID, selQry, in_NWI, out_SBB, tmpWorkspace, "in_memory")
      warnings(9)
   except:
      arcpy.AddWarning('Unable to process Rule 9 features')
      tback()

   arcpyAddMessage('SBB processing complete')
   return out_SBB