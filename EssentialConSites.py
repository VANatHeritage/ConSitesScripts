# ---------------------------------------------------------------------------
# EssentialConSites.py
# Version:  ArcGIS 10.3 / Python 2.7
# Creation Date: 2018-02-21
# Last Edit: 2018-04-23
# Creator:  Roy Gilb and Kirsten R. Hazler
# ---------------------------------------------------------------------------

# Import arcpy module
print "Importing modules..."
import arcpy, os

# Set environment options
arcpy.env.overwriteOutput = True
scratchGDB = arcpy.env.scratchGDB

# STILL TO DO:
# - Prioritize ConSites based on EO priorities, using Marxan or Zonation or something like that - KRH

# Junk below can ultimately be deleted but keeping for notes for now - KRH
# in_dodExcl: Input table designating EOs to be excluded from the process based on proximity to DOD lands, e.g., DOD_EOs.dbf
# Need to generate this with function code

# in_sppExcl: Input table designating elements to be excluded from the process, e.g., EO_Exclusions.dbf
# Need to generate this with function code

# eoSumTab: Input table giving total count per ELCODE, e.g., SUM_ALL_EOs.dbf
# Need to generate this with code rather than taking as input
# End of junk that can eventually be deleted. - KRH

def printMsg(msg):
   arcpy.AddMessage(msg)
   print msg

def printWrng(msg):
   arcpy.AddWarning(msg)
   print 'Warning: ' + msg

def unique_values(table, field):
   '''This function was obtained from:
   https://arcpy.wordpress.com/2012/02/01/create-a-list-of-unique-field-values/'''
   with arcpy.da.SearchCursor(table, [field]) as cursor:
      return sorted({row[0] for row in cursor})

def addRanks(table, sort_field, order, rank_field='RANK', thresh = 5, threshtype = "ABS"):
   valList = unique_values(table, sort_field)
   if order == "DESC":
      valList.reverse()
   #printMsg('Values in order are: %s' % str(valList))
   rankDict = {}
   rank = 1
   sortVal = valList[0]
   
   printMsg('Setting up ranking dictionary...')
   for v in valList:
      if threshtype == "PER":
         diff = 100*abs(v - sortVal/sortVal)
      else:
         diff = abs(v-sortVal)
      if diff > thresh:
         #printMsg('Difference is greater than threshold, so updating values.')
         sortVal = v
         rank += 1
      else:
         #printMsg('Difference is less than or equal to threshold, so maintaining values.')
      rankDict[v] = rank
   printMsg('Ranking dictionary (value:rank) is as follows: %s' %str(rankDict))
   
   printMsg('Writing ranks to table...')
   if not arcpy.ListFields(table, rank_field):
      arcpy.AddField_management(table, rank_field, "SHORT")
   codeblock = '''def rankVals(val, rankDict):
      rank = rankDict[val]
      return rank
   '''
   expression = "rankVals(!%s!, %s)" %(sort_field, rankDict)
   arcpy.CalculateField_management(table, rank_field, expression, "PYTHON_9.3", codeblock)
   printMsg('Finished ranking.')
   return
      
# Original AddRanks function obtained from: https://arcpy.wordpress.com/2013/08/02/ranking-field-values/
# Modified by KRH
def CrappyaddRanks(table, sort_field, category_field, rank_field='RANK', thresh = 5, threshtype = "ABS"):
   """Use sort_fields and category_field to apply a ranking to the table.

   Parameters:
      table: string
      sort_field: string
         The field on which the table will be sorted.
         KRH edit: Add DESC after field name if you want it sorted descending
      category_field: string
         The field indicating group or category membership
         All records with a common value in the category_field will be ranked relative to each other.
      rank_field: string
         The new rank field name to be added.
      thresh: double
         The difference between neighboring values to be considered "significant"
      threshtype: string [ABS | PER]
         Threshold type: absolute or percentage difference
         
   NOTE: This function ended up not working consistently, so it's heading for the trash heap.
   """
 
   # add rank field if it does not already exist
   if not arcpy.ListFields(table, rank_field):
      arcpy.AddField_management(table, rank_field, "SHORT")

   #sort_sql = ', '.join(['ORDER BY ' + category_field + ',' + sort_field])
   sort_sql = 'ORDER BY %s, %s' %(category_field, sort_field)
   printMsg('This is the SQL: %s' %sort_sql)
   
   clean_sortfield = sort_field.replace(' DESC', '')
   
   query_fields = [category_field, rank_field, clean_sortfield]
   #query_fields = "category_field; rank_field; clean_sortfield"
   printMsg('The query fields are %s' %str(query_fields))
   #sort_fields = "%s; %s" % (category_field, sort_field)

   with arcpy.da.UpdateCursor(table, query_fields, sql_clause=(None, None)) as cur:
   #with arcpy.UpdateCursor(table, "", "", query_fields, sort_fields) as cur:
      category_field_val = None
      i = 0
      printMsg('Rank initially set to zero')
      for row in cur:
         if category_field_val == row[0]:
            printMsg('Still in same category...')
            printMsg('Sort value for comparison is %s' %str(sortVal))
            if threshtype == 'PER':
               diff = 100*abs((row[2] - sortVal)/sortVal)
               printMsg('Percentage difference is %s' %str(diff))
            else:
               diff = abs(row[2] - sortVal)
               printMsg('Absolute difference is %s' %str(diff))
            if diff > thresh:
               printMsg('Difference is greater than threshold, so updating values.')
               sortVal = row[2]
               i += 1
            else:
               printMsg('Difference is less than or equal to threshold, so maintaining values.')
         else:
            category_field_val = row[0]
            sortVal = row[2]
            i = 1
            printMsg('Current category is %s' % row[0])
            printMsg('Current sort value is %s' % str(row[2]))
            printMsg('Current rank is %s' % str(i))
         #print sortVal
         row[1] = i
         cur.updateRow(row)

def TabToDict(inTab, fldKey, fldValue):
   '''Converts two fields in a table to a dictionary'''
   codeDict = {}
   with arcpy.da.SearchCursor(inTab, [fldKey, fldValue]) as sc:
      for row in sc:
         key = sc[0]
         val = sc[1]
         codeDict[key] = val
   return codeDict 

def countFeatures(features):
   '''Gets count of features'''
   count = int((arcpy.GetCount_management(features)).getOutput(0))
   return count

def updateTiers(in_procEOs, elcode, availSlots, rankFld):
   r = 1
   while availSlots > 0:
      where_clause1 = '"ELCODE" = \'%s\' AND "TIER" = \'Choice\' AND "%s" <= %s' %(elcode, rankFld, str(r))
      where_clause2 = '"ELCODE" = \'%s\' AND "TIER" = \'Choice\' AND "%s" > %s' %(elcode, rankFld, str(r))
      arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_choiceEO", where_clause1)
      c = countFeatures("lyr_choiceEO")
      printMsg('Current rank: %s' % str(r))
      printMsg('Available slots: %s' % str(availSlots))
      printMsg('Features counted: %s' % str(c))
      if c == 0:
         print "Nothing to work with here. Moving on."
         break
      elif c < availSlots:
         printMsg('Filling some slots')
         arcpy.CalculateField_management("lyr_choiceEO", "TIER", "'Priority'", "PYTHON")
         availSlots -= c
         r += 1
      elif c == availSlots:
         printMsg('Filling all slots')
         arcpy.CalculateField_management("lyr_choiceEO", "TIER", "'Priority'", "PYTHON")
         arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_surplusEO", where_clause2)
         arcpy.CalculateField_management("lyr_surplusEO", "TIER", "'Surplus'", "PYTHON")
         availSlots -= c
         break
      else:
         printMsg('Unable to differentiate; moving on to next criteria.')
         arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_surplusEO", where_clause2)
         arcpy.CalculateField_management("lyr_surplusEO", "TIER", "'Surplus'", "PYTHON")
         break
   return availSlots
   
def AttributeEOs(in_ProcFeats, in_eoReps, in_sppExcl, in_eoSelOrder, in_consLands, in_consLands_flat, out_procEOs, out_sumTab):
   '''Scores EOs based on a number of factors. 
   Inputs:
   in_ProcFeats: Input feature class with "site-worthy" procedural features
   in_eoReps: Input feature class or table with EO reps, e.g., EO_Reps_All.shp
   in_sppExcl: Input table containing list of elements to be excluded from the process, e.g., EO_Exclusions.dbf
   in_eoSelOrder: Input table designating selection order for different EO rank codes, e.g., EORANKNUM.dbf
   in_consLands: Input feature class with conservation lands (managed areas), e.g., MAs.shp
   out_procEOs: Output EOs with TIER scores
   out_sumTab: Output table summarizing number of included EOs per element'''
   
   # Dissolve procedural features on EO_ID
   printMsg("Dissolving procedural features by EO...")
   arcpy.Dissolve_management(in_ProcFeats, out_procEOs, ["SF_EOID", "ELCODE", "SNAME"], [["SFID", "COUNT"]], "MULTI_PART")
   
   # Make EO_ID into string to match EO reps - FFS why do I have to do this??
   arcpy.AddField_management(out_procEOs, "EO_ID", "TEXT", "", "", 20)
   arcpy.CalculateField_management(out_procEOs, "EO_ID", "!SF_EOID!", "PYTHON")
   
   # Join some fields
   printMsg("Joining fields from EO reps...")
   arcpy.JoinField_management(out_procEOs, "EO_ID", in_eoReps, "EO_ID", ["EORANK", "RND_GRANK", "LASTOBS"])
   arcpy.JoinField_management(out_procEOs, "EORANK", in_eoSelOrder, "EORANK", "SEL_ORDER")
      
   # Add and calculate some fields
   
   # Field: OBSYEAR
   printMsg("Calculating OBSYEAR field...")
   arcpy.AddField_management(out_procEOs, "OBSYEAR", "SHORT")
   codeblock = '''def truncDate(lastobs):
      try:
         year = int(lastobs[:4])
      except:
         year = 0
      return year'''
   expression = "truncDate(!LASTOBS!)"
   arcpy.CalculateField_management(out_procEOs, "OBSYEAR", expression, "PYTHON_9.3", codeblock)
   
   # Field: NEW_GRANK
   printMsg("Calculating NEW_GRANK field...")
   arcpy.AddField_management(out_procEOs, "NEW_GRANK", "TEXT", "", "", 2)
   codeblock = '''def reclass(granks):
      if (granks == "T1"):
         return "G1"
      elif granks == "T2":
         return "G2"
      elif granks == "T3":
         return "G3"
      elif granks == "T4":
         return "G4"
      elif granks in ("T5","GH","GNA","GNR","GU","TNR","TX","") or granks == None:
         return "G5"
      else:
         return granks'''
   expression = "reclass(!RND_GRANK!)"
   arcpy.CalculateField_management(out_procEOs, "NEW_GRANK", expression, "PYTHON_9.3", codeblock)
   
   # Field: EXCLUSION
   arcpy.AddField_management(out_procEOs, "EXCLUSION", "TEXT", "", "", 20) # This will be calculated below by groups
   
   # Set EXCLUSION value for low EO ranks
   codeblock = '''def reclass(order):
      if order == 0 or order == None:
         return "Low EO Rank"
      else:
         return "Keep"'''
   expression = "reclass(!SEL_ORDER!)"
   arcpy.CalculateField_management(out_procEOs, "EXCLUSION", expression, "PYTHON_9.3", codeblock)

   # Set EXCLUSION value for species exclusions
   printMsg("Excluding certain species...")
   arcpy.MakeFeatureLayer_management (out_procEOs, "lyr_EO")
   arcpy.AddJoin_management ("lyr_EO", "ELCODE", in_sppExcl, "ELCODE", "KEEP_COMMON")
   arcpy.CalculateField_management("lyr_EO", "EXCLUSION", "'Species Exclusion'", "PYTHON")

   # Tabulate intersection of EOs with military land where BMI > '2'
   printMsg("Tabulating intersection of EOs with military lands...")
   where_clause = '"MATYPE" IN (\'Military Installation\', \'Military Recreation Area\', \'NASA Facility\', \'sold - Military Installation\', \'surplus - Military Installation\') AND "BMI" > \'2\''
   arcpy.MakeFeatureLayer_management (in_consLands, "lyr_Military", where_clause)
   TabInter_mil = scratchGDB + os.sep + "TabInter_mil"
   arcpy.TabulateIntersection_analysis (out_procEOs, "EO_ID", "lyr_Military", TabInter_mil)
   
   # Field: PERCENT_MIL
   arcpy.AddField_management(TabInter_mil, "PERCENT_MIL", "DOUBLE")
   arcpy.CalculateField_management(TabInter_mil, "PERCENT_MIL", "!PERCENTAGE!", "PYTHON")
   arcpy.JoinField_management(out_procEOs, "EO_ID", TabInter_mil, "EO_ID", "PERCENT_MIL")
   
   # Set EXCLUSION value for Military exclusions
   where_clause = '"EXCLUSION" = \'Keep\' and "PERCENT_MIL" > 25'
   arcpy.MakeFeatureLayer_management (out_procEOs, "lyr_EO", where_clause)
   arcpy.CalculateField_management("lyr_EO", "EXCLUSION", "'Military Exclusion'", "PYTHON")
   
   # Tabulate Intersection of EOs with conservation lands where BMI = 1
   printMsg("Tabulating intersection of EOs with BMI-1 lands...")
   where_clause = '"BMI" = \'1\''
   arcpy.MakeFeatureLayer_management (in_consLands_flat, "lyr_bmi1", where_clause)
   TabInter_bmi1 = scratchGDB + os.sep + "TabInter_bmi1"
   arcpy.TabulateIntersection_analysis(out_procEOs, "EO_ID", "lyr_bmi1", TabInter_bmi1)
   
   # Field: PERCENT_bmi1
   arcpy.AddField_management(TabInter_bmi1, "PERCENT_bmi1", "DOUBLE")
   arcpy.CalculateField_management(TabInter_bmi1, "PERCENT_bmi1", "!PERCENTAGE!", "PYTHON")
   arcpy.JoinField_management(out_procEOs, "EO_ID", TabInter_bmi1, "EO_ID", "PERCENT_bmi1")
   
   # Tabulate Intersection of EOs with conservation lands where BMI = 2
   printMsg("Tabulating intersection of EOs with BMI-2 lands...")
   where_clause = '"BMI" = \'2\''
   arcpy.MakeFeatureLayer_management (in_consLands_flat, "lyr_bmi2", where_clause)
   TabInter_bmi2 = scratchGDB + os.sep + "TabInter_bmi2"
   arcpy.TabulateIntersection_analysis(out_procEOs, "EO_ID", "lyr_bmi2", TabInter_bmi2)
   
   # Field: PERCENT_bmi2
   arcpy.AddField_management(TabInter_bmi2, "PERCENT_bmi2", "DOUBLE")
   arcpy.CalculateField_management(TabInter_bmi2, "PERCENT_bmi2", "!PERCENTAGE!", "PYTHON")
   arcpy.JoinField_management(out_procEOs, "EO_ID", TabInter_bmi2, "EO_ID", "PERCENT_bmi2")

   printMsg("Calculating additional fields...")
   # Field: BMI_score
   arcpy.AddField_management(out_procEOs, "BMI_score", "DOUBLE")
   codeblock = '''def score(bmi1, bmi2):
      if not bmi1:
         bmi1 = 0
      if not bmi2:
         bmi2 = 0
      score = int((2*bmi1 + bmi2)/2)
      return score'''
   expression = 'score( !PERCENT_bmi1!, !PERCENT_bmi2!)'
   arcpy.CalculateField_management(out_procEOs, "BMI_score", expression, "PYTHON_9.3", codeblock)
   
   # Field: ysnNAP
   arcpy.AddField_management(out_procEOs, "ysnNAP", "SHORT")
   arcpy.CalculateField_management(out_procEOs, "ysnNAP", 0, "PYTHON")
   arcpy.MakeFeatureLayer_management(out_procEOs, "lyr_EO")
   where_clause = '"MATYPE" = \'State Natural Area Preserve\''
   arcpy.MakeFeatureLayer_management(in_consLands, "lyr_NAP", where_clause) 
   arcpy.SelectLayerByLocation_management("lyr_EO", "INTERSECT", "lyr_NAP", "", "NEW_SELECTION", "NOT_INVERT")
   arcpy.CalculateField_management("lyr_EO", "ysnNAP", 1, "PYTHON")
   #arcpy.SelectLayerByAttribute_management("lyr_EO", "CLEAR_SELECTION")
   
   # # Field: NEAR_DIST
   # where_clause = '"BMI" in (\'1\',\'2\')'
   # arcpy.MakeFeatureLayer_management (in_consLands, "lyr_ConsLands", where_clause)
   # arcpy.Near_analysis(out_procEOs, "lyr_ConsLands", "", "NO_LOCATION", "NO_ANGLE", "PLANAR")
   
   # # Field: INV_DIST
   # arcpy.AddField_management(out_procEOs, "INV_DIST", "DOUBLE")
   # expression = "1/math.sqrt(!NEAR_DIST! + 1)"
   # arcpy.CalculateField_management(out_procEOs, "INV_DIST", expression , "PYTHON_9.3")

   # Get subset of EOs to summarize based on EXCLUSION field
   where_clause = '"EXCLUSION" = \'Keep\''
   arcpy.MakeFeatureLayer_management (out_procEOs, "lyr_EO", where_clause)
      
   # Summarize to get count of EOs per element
   printMsg("Summarizing...")
   arcpy.Statistics_analysis("lyr_EO", out_sumTab, [["EO_ID", "COUNT"]], ["ELCODE", "NEW_GRANK"])
   
   # Add more info to summary table
   # Field: TARGET
   arcpy.AddField_management(out_sumTab, "TARGET", "SHORT")
   codeblock = '''def target(grank, count):
      if grank in ('G1', 'G2'):
         initTarget = 5
      else:
         initTarget = 2
      if count < initTarget:
         target = count
      else:
         target = initTarget
      return target'''
   expression =  "target(!NEW_GRANK!, !COUNT_EO_ID!)" 
   arcpy.CalculateField_management(out_sumTab, "TARGET", expression, "PYTHON_9.3", codeblock)
   
   # Field: TIER
   printMsg("Assigning initial tiers...")
   arcpy.AddField_management(out_sumTab, "TIER", "TEXT", "", "", 25)
   codeblock = '''def calcTier(grank, count):
      if count == 1:
         return "Irreplaceable"
      elif ((grank in ("G1","G2")) and (count <= 5)) or ((grank in ("G3","G4","G5")) and (count <= 2)) :
         return "Essential"
      else:
         return "Choice"'''
   expression = "calcTier(!NEW_GRANK!, !COUNT_EO_ID!)"
   arcpy.CalculateField_management(out_sumTab, "TIER", expression, "PYTHON_9.3", codeblock)
   
   # Join the TIER field to the EO table
   arcpy.JoinField_management("lyr_EO", "ELCODE", out_sumTab, "ELCODE", "TIER")
   
   printMsg("EO attribution complete")
   return (out_procEOs, out_sumTab)

def ScoreEOs(in_procEOs, in_sumTab, out_sortedEOs):
   # Get subset of choice elements
   where_clause = '"TIER" = \'Choice\''
   arcpy.MakeTableView_management (in_sumTab, "choiceTab", where_clause)
   
   # Make a data dictionary relating ELCODE to TARGET 
   targetDict = TabToDict("choiceTab", "ELCODE", "TARGET")
   #print targetDict
   
   # Loop through the dictionary and process each ELCODE
   for key in targetDict:
      elcode = key
      printMsg('Working on elcode %s...' %key)
      try:
         # Get subset of EOs to process
         Slots = targetDict[key]
         where_clause = '"ELCODE" = \'%s\' AND "TIER" = \'Choice\'' %elcode
         arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_EO", where_clause)
         currentCount = countFeatures("lyr_EO")
         print 'There are %s "Choice" features with this elcode' % str(currentCount)
               
         # Rank by EO-rank (selection order)
         printMsg('Updating tiers based on EO-rank...')
         addRanks("lyr_EO", "SEL_ORDER", "", rank_field='RANK_eo', thresh = 0.5, threshtype = "ABS")
         availSlots = updateTiers("lyr_EO", elcode, Slots, "RANK_eo")
         Slots = availSlots
      
         # Rank by presence on NAP
         if Slots == 0:
            pass
         else:
            printMsg('Updating tiers based on presence on NAP...')
            arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_EO", where_clause)
            addRanks("lyr_EO", "ysnNAP", "DESC", rank_field='RANK_nap', thresh = 0.5, threshtype = "ABS")
            availSlots = updateTiers("lyr_EO", elcode, Slots, "RANK_nap")
            Slots = availSlots
         
         # Rank by BMI score
         if Slots == 0:
            pass
         else:
            printMsg('Updating tiers based on BMI score...')
            arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_EO", where_clause)
            addRanks("lyr_EO", "BMI_score", "DESC", rank_field='RANK_bmi', thresh = 5, threshtype = "ABS")
            availSlots = updateTiers("lyr_EO", elcode, Slots, "RANK_bmi")
            Slots = availSlots
         
         # Rank by last observation year
         if Slots == 0:
            pass
         else:
            printMsg('Updating tiers based on last observation...')
            arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_EO", where_clause)
            addRanks("lyr_EO", "OBSYEAR", "DESC", rank_field='RANK_year', thresh = 3, threshtype = "ABS")
            availSlots = updateTiers("lyr_EO", elcode, Slots, "RANK_year")
            Slots = availSlots
            if Slots > 0:
               printMsg('No more criteria available for differentiation; Choice ties remain.')
      except:
         printWrng('There was a problem processing elcode %s.' %elcode)
   # Sort
   # Field: ChoiceRANK
   printMsg("Assigning final ranks...")
   arcpy.AddField_management(in_procEOs, "ChoiceRANK", "SHORT")
   codeblock = '''def calcRank(tier):
      if tier == "Irreplaceable":
         return 1
      elif tier == "Essential":
         return 2
      elif tier == "Priority":
         return 3
      elif tier == "Choice":
         return 4
      elif tier == "Surplus":
         return 5
      else:
         return 6'''
   expression = "calcRank(!TIER!)"
   arcpy.CalculateField_management(in_procEOs, "ChoiceRANK", expression, "PYTHON_9.3", codeblock)
   arcpy.Sort_management(in_procEOs, out_sortedEOs, [["ELCODE", "ASCENDING"], ["ChoiceRANK", "ASCENDING"]])

   printMsg("Attribution and sorting complete.")
   return out_sortedEOs
   
# Use the main function below to run desired function(s) directly from Python IDE or command line with hard-coded variables
def main():
   # Set up variables
   in_ProcFeats = r'E:\Laptop_MyDocuments\Working\ConSites\Essential_ConSites\ECS_Inputs.gdb\ProcFeats_20180222_191353'
   in_eoReps = r'E:\Laptop_MyDocuments\Working\ConSites\Essential_ConSites\ECS_Inputs.gdb\EO_reps20180222'
   in_sppExcl= r'E:\Laptop_MyDocuments\Working\ConSites\Essential_ConSites\ECS_Inputs.gdb\ExcludeSpecies'
   in_eoSelOrder = r'E:\Laptop_MyDocuments\Working\ConSites\Essential_ConSites\ECS_Inputs.gdb\EO_RankNum'
   in_consLands = r'E:\Laptop_MyDocuments\Working\ConSites\Essential_ConSites\ECS_Inputs.gdb\MAs'
   in_consLands_flat = r'E:\Laptop_MyDocuments\Working\ConSites\Essential_ConSites\ECS_Inputs.gdb\MngAreas_flat'
   out_procEOs = r'E:\Laptop_MyDocuments\Working\ConSites\Essential_ConSites\ECS_Outputs.gdb' + os.sep + 'procEOs'
   out_sumTab = r'E:\Laptop_MyDocuments\Working\ConSites\Essential_ConSites\ECS_Outputs.gdb' + os.sep + 'eoSumTab'
   out_sortedEOs = r'E:\Laptop_MyDocuments\Working\ConSites\Essential_ConSites\ECS_Outputs.gdb' + os.sep + 'procSortedEOs'
   # End of variable input

   # Specify function(s) to run below
   AttributeEOs(in_ProcFeats, in_eoReps, in_sppExcl, in_eoSelOrder, in_consLands, in_consLands_flat, out_procEOs, out_sumTab)
   ScoreEOs(out_procEOs, out_sumTab, out_sortedEOs)
   
if __name__ == '__main__':
   main()
