# ---------------------------------------------------------------------------
# EssentialConSites.py
# Version:  ArcGIS 10.3 / Python 2.7
# Creation Date: 2018-02-21
# Last Edit: 2020-03-10
# Creator:  Kirsten R. Hazler
# ---------------------------------------------------------------------------

# Import modules and functions
import Helper
from Helper import *

arcpy.env.overwriteOutput = True

### HELPER FUNCTIONS ###
def TabulateBMI(inFeats, uniqueID, conslands, bmiValue, fldName):
   '''A helper function that tabulates the percentage of each input polygon covered by conservation lands with specified BMI value. Called by the AttributeEOs function to tabulate for EOs.
   Parameters:
   - inFeats: Feature class with polygons for which BMI should be tabulated
   - uniqueID: Field in input feature class serving as unique ID
   - conslands: Feature class with conservation lands, flattened by BMI level
   - bmiValue: The value of BMI used to select subset of conservation lands
   - fldName: The output field name to be used to store percent of polygon covered by selected conservation lands
   '''
   #scratchGDB = arcpy.env.scratchGDB
   scratchGDB = "in_memory"
   #printMsg("Tabulating intersection of EOs with conservation lands of specified BMI...")
   where_clause = '"BMI" = \'%s\'' %bmiValue
   arcpy.MakeFeatureLayer_management (conslands, "lyr_bmi", where_clause)
   TabInter_bmi = scratchGDB + os.sep + "TabInter_bmi"
   arcpy.TabulateIntersection_analysis(inFeats, uniqueID, "lyr_bmi", TabInter_bmi)
   arcpy.AddField_management(TabInter_bmi, fldName, "DOUBLE")
   arcpy.CalculateField_management(TabInter_bmi, fldName, "!PERCENTAGE!", "PYTHON")
   if len(arcpy.ListFields(inFeats,fldName))>0:  
      arcpy.DeleteField_management(inFeats,fldName)
   else:  
      pass
   arcpy.JoinField_management(inFeats, uniqueID, TabInter_bmi, uniqueID, fldName)
   codeblock = '''def valUpd(val):
      if val == None:
         return 0
      else:
         return val
   '''
   expression = "valUpd(!%s!)" %fldName
   arcpy.CalculateField_management(inFeats, fldName, expression, "PYTHON", codeblock)
   
   return inFeats

def ScoreBMI(in_Feats, fld_ID, in_BMI, fld_Basename = "PERCENT_BMI_"):
   '''A helper function that tabulates the percentage of each input polygon covered by conservation lands with specified BMI value. Called by the AttributeEOs function to tabulate for EOs.
   Parameters:
   - in_Feats: Feature class with polygons for which BMI should be tabulated
   - fld_ID: Field in input feature class serving as unique ID
   - in_BMI: Feature class with conservation lands, flattened by BMI level
   - fld_Basename: The baseline of the field name to be used to store percent of polygon covered by selected conservation lands of specified BMI
   '''
   fldNames = {}
   
   for val in [1,2,3,4]:
      fldName = fld_Basename + str(val)
      printMsg("Tabulating intersection with BMI %s"%str(val))
      TabulateBMI(in_Feats, fld_ID, in_BMI, str(val), fldName)
      fldNames[val] = fldName
      
   printMsg("Calculating BMI score...")
   arcpy.AddField_management(in_Feats, "BMI_score", "SHORT")
   codeblock = '''def score(bmi1, bmi2, bmi3, bmi4):
      score = int(1.00*bmi1 + 0.75*bmi2 + 0.50*bmi3 + 0.25*bmi4)
      return score'''
   expression = 'score(!%s!, !%s!, !%s!, !%s!)'%(fldNames[1], fldNames[2], fldNames[3], fldNames[4])
   arcpy.CalculateField_management(in_Feats, "BMI_score", expression, "PYTHON_9.3", codeblock)
   
   return in_Feats
   
def addRanks(in_Table, fld_Sorting, order = 'ASCENDING', fld_Ranking='RANK', thresh = 5, threshtype = 'ABS', rounding = None):
   '''A helper function called by ScoreEOs and BuildPortfolio functions; ranks records by one specified sorting field. Assumes all records within in_Table are to be ranked against each other. If this is not the case the in_Table first needs to be filtered to contain only the records for comparison.
   Parameters:
   - in_Table: the input in_Table to which ranks will be added
   - fld_Sorting: the input field for sorting, on which ranks will be based
   - order: controls the sorting order. Assumes ascending order unless "DESC" or "DESCENDING" is entered.
   - fld_Ranking: the name of the new field that will be created to contain the ranks
   - thresh: the amount by which sorted values must differ to be ranked differently. 
   - threshtype: determines whether the threshold is an absolute value ("ABS") or a percentage ("PER")
   - rounding: determines whether sorted values are to be rounded prior to ranking, and by how much. Must be an integer or None. With rounding = 2, 1234.5678 and 1234.5690 are treated as the equivalent number for ranking purposes. With rounding = -1, 11 and 12 are treated as equivalents for ranking. Rounding is recommended if the sorting field is a double type, otherwise the function may fail.
   '''
   valList = unique_values(in_Table, fld_Sorting)
   if rounding <> None:
      valList = [round(val, rounding) for val in valList]
   if order == "DESC" or order == "DESCENDING":
      valList.reverse()
   printMsg('Values in order are: %s' % str(valList))
   rankDict = {}
   rank = 1
   sortVal = valList[0]
   
   #printMsg('Setting up ranking dictionary...')
   for v in valList:
      if threshtype == "PER":
         diff = 100*abs(v - sortVal)/sortVal
      else:
         diff = abs(v-sortVal)
      if diff > thresh:
         #printMsg('Difference is greater than threshold, so updating values.')
         sortVal = v
         rank += 1
      else:
         #printMsg('Difference is less than or equal to threshold, so maintaining values.')
         pass
      rankDict[v] = rank
   #printMsg('Ranking dictionary (value:rank) is as follows: %s' %str(rankDict))
   
   #printMsg('Writing ranks to in_Table...')
   if not arcpy.ListFields(in_Table, fld_Ranking):
      arcpy.AddField_management(in_Table, fld_Ranking, "SHORT")
   codeblock = '''def rankVals(val, rankDict, rounding):
      if rounding <> None:
         val = round(val,rounding)
      rank = rankDict[val]
      return rank'''
   expression = "rankVals(!%s!, %s, %s)" %(fld_Sorting, rankDict, rounding)
   arcpy.CalculateField_management(in_Table, fld_Ranking, expression, "PYTHON_9.3", codeblock)
   #printMsg('Finished ranking.')
   return

def modRanks(in_rankTab, fld_origRank, fld_modRank = 'MODRANK'):
   '''A helper function called by AttributeEOs function; can also be used as stand-alone funtion. Converts ranks to modified competition ranks. Assumes all records within table are to be ranked against each other. If this is not the case the table first needs to be filtered to contain only the records for comparison.
   Parameters:
   - in_rankTab: the input table to which modified ranks will be added. Must contain original ranks
   - fld_origRank: field in input table containing original rank values
   - fld_modRank: field to contain modified ranks; will be created if it doesn't already exist
   '''
   scratchGDB = "in_memory"
   
   # Get counts for each oldRank value --> rankSumTab
   rankSumTab = scratchGDB + os.sep + 'rankSumTab'
   arcpy.Frequency_analysis(in_rankTab, rankSumTab, fld_origRank)
   
   # Set up newRankDict
   rankDict = {}
   c0 = 0
   
   # extract values from summary stats in_tmpTab
   with arcpy.da.SearchCursor(rankSumTab, [fld_origRank, "FREQUENCY"]) as myRanks:
      for r in myRanks:
         origRank = r[0]
         count = r[1]
         modRank = c0 + count
         rankDict[origRank] = modRank
         c0 = modRank
   
   #printMsg('Writing ranks to in_rankTab...')
   if not arcpy.ListFields(in_rankTab, fld_modRank):
      arcpy.AddField_management(in_rankTab, fld_modRank, "SHORT")
   codeblock = '''def modRank(origRank, rankDict):
      rank = rankDict[origRank]
      return rank'''
   expression = "modRank(!%s!, %s)" %(fld_origRank, rankDict)
   arcpy.CalculateField_management(in_rankTab, fld_modRank, expression, "PYTHON_9.3", codeblock)
   
def updateTiers(in_procEOs, elcode, availSlots, rankFld):
   '''A helper function called by ScoreEOs. Updates tier levels, specifically bumping "Choice" records up to "Priority" or down to "Surplus".
   Parameters:
   - in_procEOs: input processed EOs (i.e., out_procEOs from the AttributeEOs function)
   - elcode: the element code to be processed
   - availSlots: available slots remaining to be filled in the EO portfolio
   - rankFld: the ranking field used to determine which record(s) should fill the available slots
   '''
   r = 1
   while availSlots > 0:
      where_clause1 = '"ELCODE" = \'%s\' AND "TIER" = \'Choice\' AND "%s" <= %s' %(elcode, rankFld, str(r))
      where_clause2 = '"ELCODE" = \'%s\' AND "TIER" = \'Choice\' AND "%s" > %s' %(elcode, rankFld, str(r))
      arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_choiceEO", where_clause1)
      c = countFeatures("lyr_choiceEO")
      #printMsg('Current rank: %s' % str(r))
      #printMsg('Available slots: %s' % str(availSlots))
      #printMsg('Features counted: %s' % str(c))
      if c == 0:
         #print "Nothing to work with here. Moving on."
         break
      elif c < availSlots:
         #printMsg('Filling some slots')
         arcpy.CalculateField_management("lyr_choiceEO", "TIER", "'Priority'", "PYTHON")
         availSlots -= c
         r += 1
      elif c == availSlots:
         #printMsg('Filling all slots')
         arcpy.CalculateField_management("lyr_choiceEO", "TIER", "'Priority'", "PYTHON")
         arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_surplusEO", where_clause2)
         arcpy.CalculateField_management("lyr_surplusEO", "TIER", "'Surplus'", "PYTHON")
         availSlots -= c
         break
      else:
         #printMsg('Unable to differentiate; moving on to next criteria.')
         arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_surplusEO", where_clause2)
         arcpy.CalculateField_management("lyr_surplusEO", "TIER", "'Surplus'", "PYTHON")
         break
   return availSlots

def updateSlots(in_procEOs, elcode, availSlots, rankFld):
   '''A helper function called by BuildPortfolio. Updates portfolio status for EOs, specifically adding records to the portfolio.
   Parameters:
   - in_procEOs: input processed EOs (i.e., out_procEOs from the AttributeEOs function, further processed by the ScoreEOs function)
   - elcode: the element code to be processed
   - availSlots: available slots remaining to be filled in the EO portfolio
   - rankFld: the ranking field used to determine which record(s) should fill the available slots
   '''
   r = 1
   while availSlots > 0:
      where_clause = '"ELCODE" = \'%s\' AND "TIER" = \'Choice\' AND "PORTFOLIO" = 0 AND "%s" <= %s' %(elcode, rankFld, str(r))
      #where_clause2 = '"ELCODE" = \'%s\' AND "TIER" = \'Choice\' AND "PORTFOLIO" = 0 AND "%s" > %s' %(elcode, rankFld, str(r))
      arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_choiceEO", where_clause)
      c = countFeatures("lyr_choiceEO")
      #printMsg('Current rank: %s' % str(r))
      #printMsg('Available slots: %s' % str(availSlots))
      #printMsg('Features counted: %s' % str(c))
      if c == 0:
         #print "Nothing to work with here. Moving on."
         break
      elif c < availSlots:
         #printMsg('Filling some slots')
         arcpy.CalculateField_management("lyr_choiceEO", "PORTFOLIO", "1", "PYTHON")
         availSlots -= c
         r += 1
      elif c == availSlots:
         #printMsg('Filling all slots')
         arcpy.CalculateField_management("lyr_choiceEO", "PORTFOLIO", "1", "PYTHON")
         availSlots -= c
         break
      else:
         #printMsg('Unable to differentiate; moving on to next criteria.')
         break
   return availSlots

def UpdatePortfolio(in_procEOs,in_ConSites,in_sumTab):
   '''A helper function called by BuildPortfolio. Selects ConSites intersecting EOs in the EO portfolio, and adds them to the ConSite portfolio. Then selects "Choice" EOs intersecting ConSites in the portfolio, and adds them to the EO portfolio (bycatch). Finally, updates the summary table to indicate how many EOs of each element are in the different tier classes, and how many are included in the current portfolio.
   Parameters:
   - in_procEOs: input feature class of processed EOs (i.e., out_procEOs from the AttributeEOs function, further processed by the ScoreEOs function)
   - in_ConSites: input Conservation Site boundaries
   - in_sumTab: input table summarizing number of included EOs per element (i.e., out_sumTab from the AttributeEOs function.
   '''
   # Intersect ConSites with subset of EOs, and set PORTFOLIO to 1
   where_clause = '("ChoiceRANK" < 4 OR "PORTFOLIO" = 1) AND "OVERRIDE" <> -1' 
   arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_EO", where_clause)
   where_clause = '"OVERRIDE" <> -1'
   arcpy.MakeFeatureLayer_management (in_ConSites, "lyr_CS", where_clause)
   arcpy.SelectLayerByLocation_management ("lyr_CS", "INTERSECT", "lyr_EO", 0, "NEW_SELECTION", "NOT_INVERT")
   arcpy.CalculateField_management("lyr_CS", "PORTFOLIO", 1, "PYTHON_9.3")
   arcpy.CalculateField_management("lyr_EO", "PORTFOLIO", 1, "PYTHON_9.3")
   printMsg('ConSites portfolio updated')
   
   # Intersect Choice EOs with Portfolio ConSites, and set PORTFOLIO to 1
   where_clause = '"TIER" = \'Choice\' AND "OVERRIDE" <> -1'
   arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_EO", where_clause)
   where_clause = '"PORTFOLIO" = 1'
   arcpy.MakeFeatureLayer_management (in_ConSites, "lyr_CS", where_clause)
   arcpy.SelectLayerByLocation_management ("lyr_EO", "INTERSECT", "lyr_CS", 0, "NEW_SELECTION", "NOT_INVERT")
   arcpy.CalculateField_management("lyr_EO", "PORTFOLIO", 1, "PYTHON_9.3")
   printMsg('EOs portfolio updated')
   
   # Fill in counter fields
   printMsg('Summarizing portfolio status...')
   freqTab = in_procEOs + '_freq'
   pivotTab = in_procEOs + '_pivot'
   arcpy.Frequency_analysis(in_procEOs, freqTab, frequency_fields="ELCODE;TIER") 
   arcpy.PivotTable_management(freqTab, fields="ELCODE", pivot_field="TIER", value_field="FREQUENCY", out_table=pivotTab)
   
   fields = ["Irreplaceable", "Critical", "Priority", "Choice", "Surplus"]
   for fld in fields:
      try:
         arcpy.DeleteField_management (in_sumTab, fld)
      except:
         pass
      arcpy.JoinField_management (in_sumTab, "ELCODE", pivotTab, "ELCODE", fld)
      #printMsg('Field "%s" joined to table %s.' %(fld, in_sumTab))
   
   portfolioTab = in_procEOs + '_portfolio'
   arcpy.Frequency_analysis(in_procEOs, portfolioTab, frequency_fields="ELCODE", summary_fields="PORTFOLIO")
   try: 
      arcpy.DeleteField_management (in_sumTab, "PORTFOLIO")
   except:
      pass
   arcpy.JoinField_management (in_sumTab, "ELCODE", portfolioTab, "ELCODE", "PORTFOLIO")
   #printMsg('Field "PORTFOLIO" joined to table %s.' %in_sumTab)

def buildSlotDict(in_sumTab):
   '''Creates a data dictionary relating ELCODE to available slots, for elements where portfolio targets are still not met''' 
   printMsg('Finding ELCODES for which portfolio is still not filled...')
   slotDict = {}
   where_clause = '"PORTFOLIO" < "TARGET"'
   arcpy.MakeTableView_management (in_sumTab, "vw_EOsum", where_clause)
   with arcpy.da.SearchCursor("vw_EOsum", ["ELCODE", "TARGET", "PORTFOLIO"]) as cursor:
      for row in cursor:
         elcode = row[0]
         target = row[1]
         portfolio = row[2]
         slots = target - portfolio
         slotDict[elcode] = slots
   count = countFeatures("vw_EOsum")
   printMsg("There are %s Elements with remaining slots to fill."%count)
   return slotDict
   

### MAIN FUNCTIONS ###
def ParseSiteTypes(in_ProcFeats, in_ConSites, out_GDB):
   '''Splits input Procedural Features and Conservation Sites into 3 feature classes each, one for each of site types subject to ECS process.
   Parameters:
   - in_ProcFeats: input feature class representing Procedural Features
   - in_ConSites: input feature class representing Conservation Sites
   - out_GDB: geodatabase in which outputs will be stored   
   '''
   
   # Define some queries
   qry_pfTCS = "RULE NOT IN ('SCU','MACS','KCS','AHZ')"
   qry_pfKCS = "RULE = 'KCS'"
   qry_pfSCU = "RULE = 'SCU'"
   qry_csTCS = "SITE_TYPE = 'Conservation Site'"
   qry_csKCS = "SITE_TYPE = 'Cave Site'"
   qry_csSCU = "SITE_TYPE = 'SCU'"
   
   # Define some outputs
   pfTCS = out_GDB + os.sep + 'pfTerrestrial'
   pfKCS = out_GDB + os.sep + 'pfKarst'
   pfSCU = out_GDB + os.sep + 'pfStream'
   csTCS = out_GDB + os.sep + 'csTerrestrial'
   csKCS = out_GDB + os.sep + 'csKarst'
   csSCU = out_GDB + os.sep + 'csStream'
   
   # Make a list of input/query/output triplets
   procList = [[in_ProcFeats, qry_pfTCS, pfTCS],
               [in_ProcFeats, qry_pfKCS, pfKCS],
               [in_ProcFeats, qry_pfSCU, pfSCU],
               [in_ConSites, qry_csTCS, csTCS],
               [in_ConSites, qry_csKCS, csKCS],
               [in_ConSites, qry_csSCU, csSCU]]
               
   # Process the data
   fcList = []
   for item in procList:
      input = item[0]
      query = item[1]
      output = item[2]
      printMsg("Creating feature class %s" %output)
      arcpy.Select_analysis (input, output, query)
      fcList.append(output)
   
   return fcList

def getBRANK(in_EOs, in_ConSites):
   '''Automates the assignment of B-ranks to conservation sites
   NOTE: Should only be run on one site type at a time, with type-specific inputs. Needs to run in foreground so tables update attributes. Best to close attribute tables prior to running.
   '''
   ### For the EOs, calculate the IBR (individual B-rank)
   printMsg('Creating and calculating IBR field for EOs...')
   arcpy.AddField_management(in_EOs, "IBR", "TEXT", 2)
   # Searches elcodes for "CEGL" so it can treat communities a little differently than species.
   # Should it do the same for "ONBCOLONY" bird colonies?
   codeblock = '''def ibr(grank, srank, eorank, fstat, sstat, elcode):
      if eorank == "A":
         if grank == "G1":
            return "B1"
         elif grank in ("G2", "G3"):
            return "B2"
         else:
            if srank == "S1":
               return "B3"
            elif srank == "S2":
               return "B4"
            else:
               return "B5"
      elif eorank == "B":
         if grank in ("G1", "G2"):
            return "B2"
         elif grank == "G3":
            return "B3"
         else:
            if srank == "S1":
               return "B4"
            else:
               return "B5"
      elif eorank == "C":
         if grank == "G1":
            return "B2"
         elif grank == "G2":
            return "B3"
         elif grank == "G3":
            return "B4"
         else:
            if srank in ("S1", "S2"):
               return "B5"
            elif elcode[:4] == "CEGL":
               return "B5"
            else:
               return "BU"
      elif eorank == "D":
         if grank == "G1":
            return "B2"
         elif grank == "G2":
            return "B3"
         elif grank == "G3":
            return "B4"
         else:
            if (fstat in ("LT%", "LE%") or sstat in ("LT", "LE")) and (srank in ("S1", "S2")):
               return "B5"
            elif elcode[:4] == "CEGL":
               return "B5"
            else:
               return "BU"
      else:
         return "BU"
   '''
   expression = "ibr(!BIODIV_GRANK!, !BIODIV_SRANK!, !BIODIV_EORANK!, !FEDSTAT!, !SPROT!, !ELCODE!)"
   arcpy.CalculateField_management(in_EOs, "IBR", expression, "PYTHON_9.3", codeblock)
   
   ### For the EOs, calculate the IBR score
   printMsg('Creating and calculating IBR_SCORE field for EOs...')
   arcpy.AddField_management(in_EOs, "IBR_SCORE", "LONG")
   codeblock = '''def score(ibr):
      if ibr == "B1":
         return 256
      elif ibr == "B2":
         return 64
      elif ibr == "B3":
         return 16
      elif ibr == "B4":
         return 4
      elif ibr == "B5":
         return 1
      else:
         return 0
   '''
   expression = "score(!IBR!)"
   arcpy.CalculateField_management(in_EOs, "IBR_SCORE", expression, "PYTHON_9.3", codeblock)
   
   ### For the ConSites, calculate the B-rank and flag if it conflicts with previous B-rank
   printMsg('Adding several fields to ConSites...')
   arcpy.AddField_management(in_ConSites, "IBR_SUM", "LONG")
   arcpy.AddField_management(in_ConSites, "IBR_MAX", "LONG")
   arcpy.AddField_management(in_ConSites, "AUTO_BRANK", "TEXT", 2)
   arcpy.AddField_management(in_ConSites, "FLAG_BRANK", "LONG")

   # Calculate B-rank scores 
   printMsg('Calculating B-rank sums and maximums in loop...')
   arcpy.MakeFeatureLayer_management (in_EOs, "eo_lyr")
   failList = []
   with arcpy.da.UpdateCursor (in_ConSites, ["SHAPE@", "SITEID", "IBR_SUM", "IBR_MAX"]) as cursor:
      for row in cursor:
         myShp = row[0]
         siteID = row[1]
         arcpy.SelectLayerByLocation_management ("eo_lyr", "INTERSECT", myShp, "", "NEW_SELECTION")
         c = countSelectedFeatures("eo_lyr")
         if c > 0:
            arr = arcpy.da.TableToNumPyArray ("eo_lyr",["IBR_SCORE"], skip_nulls=True)
            
            row[2] = arr["IBR_SCORE"].sum() 
            row[3] = arr["IBR_SCORE"].max() 

            cursor.updateRow(row)
            # printMsg("Site %s: Completed"%siteID)
         else:
            printMsg("Site %s: Failed"%siteID)
            failList.append(siteID)
         
   # Determine B-rank based on the sum of IBRs
   printMsg('Calculating site B-ranks from sums and maximums of individual B-ranks...')
   codeblock = '''def brank(sum, max):
      if sum == None:
         sumRank = None
      elif sum < 4:
         sumRank = "B5"
      elif sum < 16:
         sumRank = "B4"
      elif sum < 64:
         sumRank = "B3"
      elif sum < 256:
         sumRank = "B2"
      else:
         sumRank = "B1"
      
      if max == None:
         maxRank = None
      elif max < 4:
         maxRank = "B4"
      elif max < 16:
         maxRank = "B3"
      elif max < 64:
         maxRank = "B2"
      else:
         maxRank = "B1"

      if sumRank < maxRank:
         return maxRank
      else:
         return sumRank
      '''
   
   expression= "brank(!IBR_SUM!,!IBR_MAX!)"
   arcpy.CalculateField_management(in_ConSites, "AUTO_BRANK", expression, "PYTHON_9.3", codeblock)
   
   printMsg('Calculating flag status...')
   codeblock = '''def flag(brank, auto_brank):
      if auto_brank == None:
         return None
      elif brank == auto_brank:
         return 0
      else:
         return 1
   '''
   expression = "flag(!BRANK!, !AUTO_BRANK!)"
   arcpy.CalculateField_management(in_ConSites, "FLAG_BRANK", expression, "PYTHON_9.3", codeblock)

   if len(failList) > 0:
      printMsg("Processing incomplete for some sites %s"%failList)
   return (in_EOs, in_ConSites)
   printMsg('Finished.')

def MakeExclusionList(in_Tabs, out_Tab):
   '''Creates a list of elements to exclude from ECS processing, from a set of input spreadsheets which have standardized fields and have been converted to CSV format. 
   Parameters:
   - in_Tabs: spreadsheet(s) in CSV format (full paths) [If multiple, this is a list OR a string with items separated by ';']
   - out_Tab: output compiled table in a geodatabase
   '''
   # Create the output table
   printMsg('Creating Element Exclusion table...')
   out_path = os.path.dirname(out_Tab)
   out_name = os.path.basename(out_Tab)
   arcpy.CreateTable_management (out_path, out_name)
   
   # Add the standard fields
   printMsg('Adding standard fields to table...')
   fldList = [['ELCODE', 'TEXT', 10],
               ['EXCLUDE', 'SHORT', ''],
               ['DATADEF', 'SHORT', ''],
               ['TAXRES', 'SHORT', ''],
               ['WATCH', 'SHORT', ''],
               ['EXTIRP', 'SHORT', ''],
               ['ECOSYST', 'SHORT', ''],
               ['OTHER', 'TEXT', 50],
               ['NOTES', 'TEXT', 50]]
   for fld in fldList:
      field_name = fld[0]
      field_type = fld[1]
      field_length = fld[2]
      arcpy.AddField_management (out_Tab, field_name, field_type, '', '', field_length)
         
   # Append each of the input tables
   printMsg('Appending lists to master table...')
   # First convert string to list if necessary
   if type(in_Tabs) == str:
      in_Tabs = in_Tabs.split(';')
   for tab in in_Tabs:
      arcpy.Append_management (tab, out_Tab, 'NO_TEST')
      
   printMsg('Finished creating Element Exclusion table.')
  
def AttributeEOs(in_ProcFeats, in_elExclude, in_consLands, in_consLands_flat, in_ecoReg, fld_RegCode, cutYear, flagYear, out_procEOs, out_sumTab):
   '''Dissolves Procedural Features by EO-ID, then attaches numerous attributes to the EOs, creating a new output EO layer as well as an Element summary table. The outputs from this function are subsequently used in the function ScoreEOs. 
   Parameters:
   - in_ProcFeats: Input feature class with "site-worthy" procedural features
   - in_elExclude: Input table containing list of elements to be excluded from the process, e.g., EO_Exclusions.dbf
   - in_consLands: Input feature class with conservation lands (managed areas), e.g., MAs.shp
   - in_consLands_flat: A "flattened" version of in_ConsLands, based on level of Biodiversity Management Intent (BMI). (This is needed due to stupid overlapping polygons in our database. Sigh.)
   - in_ecoReg: A polygon feature class representing ecoregions
   - fld_RegCode: Field in in_ecoReg with short, unique region codes
   - cutYear: Integer value indicating hard cutoff year. EOs with last obs equal to or earlier than this cutoff are to be excluded from the ECS process altogether.
   - flagYear: Integer value indicating flag year. EOs with last obs equal to or earlier than this cutoff are to be flagged with "Update Needed". However, this cutoff does not affect the ECS process.
   - out_procEOs: Output EOs with TIER scores and other attributes.
   - out_sumTab: Output table summarizing number of included EOs per element'''
   
   scratchGDB = "in_memory"
   
   # Dissolve procedural features on SF_EOID
   printMsg("Dissolving procedural features by EO...")
   arcpy.Dissolve_management(in_ProcFeats, out_procEOs, ["SF_EOID", "ELCODE", "SNAME", "BIODIV_GRANK", "BIODIV_SRANK", "RNDGRNK", "EORANK", "EOLASTOBS", "FEDSTAT", "SPROT"], [["SFID", "COUNT"]], "MULTI_PART")
      
   # Add and calculate some fields
   
   # Field: EORANK_NUM
   printMsg("Calculating EORANK_NUM field")
   arcpy.AddField_management(out_procEOs, "EORANK_NUM", "SHORT")
   codeblock = '''def rankNum(eorank):
      if eorank == "A":
         return 1
      elif eorank == "A?":
         return 2
      elif eorank == "AB":
         return 3
      elif eorank in ("AC", "B"):
         return 4
      elif eorank == "B?":
         return 5
      elif eorank == "BC":
         return 6
      elif eorank == "C":
         return 7
      elif eorank in ("C?", "E"):
         return 8
      elif eorank == "CD":
         return 9
      elif eorank in ("D", "D?"):
         return 10
      else:
         return 11
      '''
   expression = "rankNum(!EORANK!)"
   arcpy.CalculateField_management(out_procEOs, "EORANK_NUM", expression, "PYTHON_9.3", codeblock)
   
   # Field: OBSYEAR
   printMsg("Calculating OBSYEAR field...")
   arcpy.AddField_management(out_procEOs, "OBSYEAR", "SHORT")
   codeblock = '''def truncDate(lastobs):
      try:
         year = int(lastobs[:4])
      except:
         year = 0
      return year'''
   expression = "truncDate(!EOLASTOBS!)"
   arcpy.CalculateField_management(out_procEOs, "OBSYEAR", expression, "PYTHON_9.3", codeblock)
   
   # Field: RECENT
   printMsg("Calculating RECENT field...")
   arcpy.AddField_management(out_procEOs, "RECENT", "SHORT")
   codeblock = '''def thresh(obsYear, cutYear, flagYear):
      if obsYear <= cutYear:
         return 0
      elif obsYear <= flagYear:
         return 1
      else:
         return 2'''
   expression = "thresh(!OBSYEAR!, %s, %s)"%(str(cutYear), str(flagYear))
   arcpy.CalculateField_management(out_procEOs, "RECENT", expression, "PYTHON_9.3", codeblock)
   
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
   expression = "reclass(!RNDGRNK!)"
   arcpy.CalculateField_management(out_procEOs, "NEW_GRANK", expression, "PYTHON_9.3", codeblock)
   
   # Field: EXCLUSION
   printMsg("Calculating EXCLUSION field...")
   arcpy.AddField_management(out_procEOs, "EXCLUSION", "TEXT", "", "", 20) # This will be calculated below by groups
   
   # Set EXCLUSION value for low EO ranks
   printMsg("Excluding low EO ranks...")
   codeblock = '''def reclass(order):
      if order == 10:
         return "Not viable"
      elif order >10 or order == None:
         return "Error Check Needed"
      else:
         return "Keep"'''
   expression = "reclass(!EORANK_NUM!)"
   arcpy.CalculateField_management(out_procEOs, "EXCLUSION", expression, "PYTHON_9.3", codeblock)
   
   # Set EXCLUSION value for old observations
   printMsg("Excluding old observations...")
   where_clause = '"RECENT" = 0'
   arcpy.MakeFeatureLayer_management (out_procEOs, "lyr_EO", where_clause)
   expression = "'Old Observation'"
   arcpy.CalculateField_management("lyr_EO", "EXCLUSION", expression, "PYTHON_9.3")

   # Set EXCLUSION value for elements exclusions
   printMsg("Excluding certain elements...")
   arcpy.MakeFeatureLayer_management (out_procEOs, "lyr_EO")
   arcpy.AddJoin_management ("lyr_EO", "ELCODE", in_elExclude, "ELCODE", "KEEP_COMMON")
   arcpy.CalculateField_management("lyr_EO", "EXCLUSION", "'Excluded Element'", "PYTHON")

   # Tabulate intersection of EOs with military land
   printMsg("Tabulating intersection of EOs with military lands...")
   where_clause = '"MATYPE" IN (\'Military Installation\', \'Military Recreation Area\', \'NASA Facility\', \'sold - Military Installation\', \'surplus - Military Installation\')'
   arcpy.MakeFeatureLayer_management (in_consLands, "lyr_Military", where_clause)
   TabInter_mil = scratchGDB + os.sep + "TabInter_mil"
   arcpy.TabulateIntersection_analysis (out_procEOs, "SF_EOID", "lyr_Military", TabInter_mil)
   
   # Field: PERCENT_MIL
   arcpy.AddField_management(TabInter_mil, "PERCENT_MIL", "DOUBLE")
   arcpy.CalculateField_management(TabInter_mil, "PERCENT_MIL", "!PERCENTAGE!", "PYTHON")
   arcpy.JoinField_management(out_procEOs, "SF_EOID", TabInter_mil, "SF_EOID", "PERCENT_MIL")
   codeblock = '''def updateMil(mil):
      if mil == None:
         return 0
      else:
         return mil'''
   expression = "updateMil(!PERCENT_MIL!)"
   arcpy.CalculateField_management(out_procEOs, "PERCENT_MIL", expression, "PYTHON_9.3", codeblock)
   
   # Tabulate Intersection of EOs with conservation lands of specified BMI values
   ScoreBMI(out_procEOs, "SF_EOID", in_consLands_flat, "PERCENT_BMI_")
   
   # Field: ysnNAP
   printMsg("Categorizing intersection of EOs with Natural Area Preserves...")
   arcpy.AddField_management(out_procEOs, "ysnNAP", "SHORT")
   arcpy.CalculateField_management(out_procEOs, "ysnNAP", 0, "PYTHON")
   arcpy.MakeFeatureLayer_management(out_procEOs, "lyr_EO")
   where_clause = '"MATYPE" = \'State Natural Area Preserve\''
   arcpy.MakeFeatureLayer_management(in_consLands, "lyr_NAP", where_clause) 
   arcpy.SelectLayerByLocation_management("lyr_EO", "INTERSECT", "lyr_NAP", "", "NEW_SELECTION", "NOT_INVERT")
   arcpy.CalculateField_management("lyr_EO", "ysnNAP", 1, "PYTHON")
   #arcpy.SelectLayerByAttribute_management("lyr_EO", "CLEAR_SELECTION")
   
   # Indicate presence of EOs in ecoregions
   printMsg('Indicating presence of EOs in ecoregions...')
   ecoregions = unique_values(in_ecoReg, fld_RegCode)
   for code in ecoregions:
      arcpy.AddField_management(out_procEOs, code, "SHORT")
      where_clause = '"%s" = \'%s\''%(fld_RegCode, code)
      arcpy.MakeFeatureLayer_management(in_ecoReg, "lyr_ecoReg", where_clause)
      arcpy.SelectLayerByLocation_management("lyr_EO", "INTERSECT", "lyr_ecoReg", "", "NEW_SELECTION", "NOT_INVERT")
      arcpy.CalculateField_management("lyr_EO", code, 1, "PYTHON")
      arcpy.SelectLayerByLocation_management("lyr_EO", "INTERSECT", "lyr_ecoReg", "", "NEW_SELECTION", "INVERT")
      arcpy.CalculateField_management("lyr_EO", code, 0, "PYTHON")
   
   # Get subset of EOs meeting criteria, based on EXCLUSION field
   where_clause = '"EXCLUSION" = \'Keep\''
   arcpy.MakeFeatureLayer_management (out_procEOs, "lyr_EO", where_clause)
      
   # Summarize to get count of included EOs per element, and counts in ecoregions
   printMsg("Summarizing...")
   statsList = [["SF_EOID", "COUNT"]]
   for code in ecoregions:
      statsList.append([str(code), "SUM"])
   arcpy.Statistics_analysis("lyr_EO", out_sumTab, statsList, ["ELCODE", "SNAME", "NEW_GRANK"])
   
   # Add more info to summary table
   # Field: NUM_REG
   printMsg("Determining the number of regions in which each element occurs...")
   arcpy.AddField_management(out_sumTab, "NUM_REG", "SHORT")
   varString = str(ecoregions[0])
   for code in ecoregions[1:]:
      varString += ', %s' %str(code)
   cmdString = 'c = 0'
   for code in ecoregions:
      cmdString += '''
      if %s >0:
         c +=1
      else:
         pass'''%str(code)
   codeblock = '''def numReg(%s):
      %s
      return c
   '''%(varString, cmdString)
   expString = '!SUM_%s!' %str(ecoregions[0])
   for code in ecoregions[1:]:
      expString += ', !SUM_%s!' %str(code)
   expression = 'numReg(%s)'%expString
   arcpy.CalculateField_management(out_sumTab, "NUM_REG", expression, "PYTHON_9.3", codeblock)
   
   # Field: TARGET
   printMsg("Determining conservation targets...")
   arcpy.AddField_management(out_sumTab, "TARGET", "SHORT")
   codeblock = '''def target(grank, count):
      if grank == 'G1':
         initTarget = 10
      elif grank == 'G2':
         initTarget = 5
      else:
         initTarget = 2
      if count < initTarget:
         target = count
      else:
         target = initTarget
      return target'''
   expression =  "target(!NEW_GRANK!, !COUNT_SF_EOID!)" 
   arcpy.CalculateField_management(out_sumTab, "TARGET", expression, "PYTHON_9.3", codeblock)
   
   # Field: TIER
   printMsg("Assigning initial tiers...")
   arcpy.AddField_management(out_sumTab, "TIER", "TEXT", "", "", 25)
   codeblock = '''def calcTier(grank, count):
      if count == 1:
         return "Irreplaceable"
      elif count == 2:
         return "Critical"
      else:
         return "Choice"'''
   expression = "calcTier(!NEW_GRANK!, !COUNT_SF_EOID!)"
   arcpy.CalculateField_management(out_sumTab, "TIER", expression, "PYTHON_9.3", codeblock)
   
   # Join the TIER field to the EO table
   printMsg("Joining TIER field to the EO table...")
   arcpy.JoinField_management("lyr_EO", "ELCODE", out_sumTab, "ELCODE", "TIER")
   
   # Field: EO_MODRANK
   printMsg("Calculating modified competition ranks based on EO-ranks...")
   elcodes = unique_values("lyr_EO", "ELCODE")
   for code in elcodes:
      #printMsg('Working on %s...' %code)
      where_clause = '"EXCLUSION" = \'Keep\' AND "ELCODE" = \'%s\''%code
      #arcpy.MakeFeatureLayer_management (out_procEOs, "lyr_EO", where_clause)
      arcpy.SelectLayerByAttribute_management ("lyr_EO", "NEW_SELECTION", where_clause)
      modRanks("lyr_EO", "EORANK_NUM", "EO_MODRANK")
   
   printMsg("EO attribution complete")
   return (out_procEOs, out_sumTab)
   
def ScoreEOs(in_procEOs, in_sumTab, out_sortedEOs, ysnMil = "false", ysnYear = "true"):
   '''Ranks EOs within an element based on a variety of attributes. This function must follow, and requires inputs from, the outputs of the AttributeEOs function. 
   Parameters:
   - in_procEOs: input feature class of processed EOs (i.e., out_procEOs from the AttributeEOs function)
   - in_sumTab: input table summarizing number of included EOs per element (i.e., out_sumTab from the AttributeEOs function.
   - ysnMil: determines whether to use military status of land as a ranking factor ("true") or not ("false"; default)
   - ysnYear: determines whether to use observation year as a ranking factor ("true"; default) or not ("false")
   - out_sortedEOs: output feature class of processed EOs, sorted by element code and rankings.
   '''
         
   # Make copy of input
   scratchGDB = "in_memory"
   tmpEOs = scratchGDB + os.sep + "tmpEOs"
   arcpy.CopyFeatures_management(in_procEOs, tmpEOs)
   in_procEOs = tmpEOs
   
   # Add ranking fields
   for fld in ['RANK_mil', 'RANK_eo', 'RANK_year', 'RANK_bmi', 'RANK_nap', 'RANK_csVal', 'RANK_numPF', 'RANK_eoArea']:
      arcpy.AddField_management(in_procEOs, fld, "SHORT")
      
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
         printMsg ('There are %s "Choice" features with this elcode' % str(currentCount))
         
         # Rank by military land - prefer EOs not on military land
         if ysnMil == "false":
            arcpy.CalculateField_management(in_procEOs, "RANK_mil", 0, "PYTHON_9.3")
         else: 
            printMsg('Updating tiers based on proportion of EO on military land...')
            # arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_EO", where_clause)
            addRanks("lyr_EO", "PERCENT_MIL", "", "RANK_mil", 5, "ABS")
            availSlots = updateTiers("lyr_EO", elcode, Slots, "RANK_mil")
            Slots = availSlots
         
         # Rank by EO-rank (selection order) - prefer highest-ranked EOs
         if Slots == 0:
            #arcpy.CalculateField_management(in_procEOs, "RANK_eo", 0, "PYTHON_9.3")
            pass
         else:
            printMsg('Updating tiers based on EO-rank...')
            arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_EO", where_clause)
            addRanks("lyr_EO", "EORANK_NUM", "", "RANK_eo", 0.5, "ABS")
            availSlots = updateTiers("lyr_EO", elcode, Slots, "RANK_eo")
            Slots = availSlots
             
         # Rank by observation year - prefer more recently observed EOs
         if ysnYear == "false":
            arcpy.CalculateField_management(in_procEOs, "RANK_year", 0, "PYTHON_9.3")
         elif Slots == 0:
            pass
         else:
            printMsg('Updating tiers based on observation year...')
            arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_EO", where_clause)
            addRanks("lyr_EO", "OBSYEAR", "DESC", "RANK_year", 3, "ABS")
            availSlots = updateTiers("lyr_EO", elcode, Slots, "RANK_year")
            Slots = availSlots
         
         if Slots > 0:
            printMsg('Choice ties remain.')
         else:
            printMsg('All slots filled.')

      except:
         printWrng('There was a problem processing elcode %s.' %elcode)
         tback()
   # Sort
   # Field: ChoiceRANK
   printMsg("Assigning final tier ranks...")
   arcpy.AddField_management(in_procEOs, "ChoiceRANK", "SHORT")
   codeblock = '''def calcRank(tier):
      if tier == "Irreplaceable":
         return 1
      elif tier == "Critical":
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
   
   # Add "EO_CONSVALUE" field to in_procEOs, and calculate
   printMsg("Calculating conservation values of individual EOs...")
   arcpy.AddField_management(in_procEOs, "EO_CONSVALUE", "SHORT")
   # Codeblock subject to change based on reviewer input.
   codeblock = '''def calcConsVal(tier, grank):
      if tier == "Irreplaceable":
         if grank == "G1":
            consval = 100
         elif grank == "G2":
            consval = 95
         elif grank == "G3":
            consval = 85
         elif grank == "G4":
            consval = 75
         else:
            consval = 70
      elif tier == "Critical":
         if grank == "G1":
            consval = 95
         elif grank == "G2":
            consval = 90
         elif grank == "G3":
            consval = 80
         elif grank == "G4":
            consval = 70
         else:
            consval = 65
      elif tier == "Priority":
         if grank == "G1":
            consval = 60
         elif grank == "G2":
            consval = 55
         elif grank == "G3":
            consval = 45
         elif grank == "G4":
            consval = 35
         else:
            consval = 30
      elif tier == "Choice":
         if grank == "G1":
            consval = 25
         elif grank == "G2":
            consval = 20
         elif grank == "G3":
            consval = 10
         elif grank == "G4":
            consval = 5
         else:
            consval = 5
      elif tier == "Surplus":
         if grank == "G1":
            consval = 5
         elif grank == "G2":
            consval = 5
         elif grank == "G3":
            consval = 0
         elif grank == "G4":
            consval = 0
         else:
            consval = 0
      else:
         consval = 0
      return consval
      '''
   expression = "calcConsVal(!TIER!, !NEW_GRANK!)"
   arcpy.CalculateField_management(in_procEOs, "EO_CONSVALUE", expression, "PYTHON_9.3", codeblock)
   printMsg('EO_CONSVALUE field set')
   
   fldList = [
   ["ELCODE", "ASCENDING"], 
   ["ChoiceRANK", "ASCENDING"], 
   ["RANK_mil", "ASCENDING"], 
   ["RANK_eo", "ASCENDING"], 
   ["RANK_year", "ASCENDING"],
   ["EORANK_NUM", "ASCENDING"],
   ]
   arcpy.Sort_management(in_procEOs, out_sortedEOs, fldList)

   printMsg("Attribution and sorting complete.")
   return out_sortedEOs
   
def BuildPortfolio(in_sortedEOs, out_sortedEOs, in_sumTab, out_sumTab, in_ConSites, out_ConSites, in_consLands_flat, build = 'NEW'):
   '''Builds a portfolio of EOs and Conservation Sites of highest conservation priority.
   Parameters:
   - in_sortedEOs: input feature class of scored EOs (i.e., out_sortedEOs from the ScoreEOs function)
   - out_sortedEOs: output prioritized EOs
   - in_sumTab: input table summarizing number of included EOs per element (i.e., out_sumTab from the AttributeEOs function.
   - out_sumTab: updated output element portfolio summary table
   - in_ConSites: input Conservation Site boundaries
   - out_ConSites: output prioritized Conservation Sites
   - build: type of portfolio build to perform. The options are:
      - NEW: overwrite any existing portfolio picks for both EOs and ConSites
      - NEW_EO: overwrite existing EO picks, but keep previous ConSite picks
      - NEW_CS: overwrite existing ConSite picks, but keep previous EO picks
      - UPDATE: Update portfolio but keep existing picks for both EOs and ConSites
   - in_consLands_flat: Input "flattened" version of Conservation Lands, based on level of Biodiversity Management Intent (BMI).
   '''
   
   scratchGDB = arcpy.env.scratchGDB
   # Lesson learned: Don't try to write to in_memory for this, because then the "SHAPE_Area" field no longer exists and then your code fails and then you haz a sad.
   
   # Make copies of inputs
   tmpEOs = scratchGDB + os.sep + "tmpEOs"
   arcpy.CopyFeatures_management(in_sortedEOs, tmpEOs)
   in_sortedEOs = tmpEOs
   
   tmpTab = scratchGDB + os.sep + "tmpTab"
   arcpy.CopyRows_management(in_sumTab, tmpTab)
   in_sumTab = tmpTab
   
   tmpCS = scratchGDB + os.sep + "tmpCS"
   arcpy.CopyFeatures_management(in_ConSites, tmpCS)
   in_ConSites = tmpCS
      
   # Add "PORTFOLIO" and "OVERRIDE" fields to in_sortedEOs and in_ConSites tables
   for tab in [in_sortedEOs, in_ConSites]:
      arcpy.AddField_management(tab, "PORTFOLIO", "SHORT")
      arcpy.AddField_management(tab, "OVERRIDE", "SHORT")
      # The AddField command should be ignored if field already exists
      
   if build == 'NEW' or build == 'NEW_EO':
      arcpy.CalculateField_management(in_sortedEOs, "PORTFOLIO", 0, "PYTHON_9.3")
      arcpy.CalculateField_management(in_sortedEOs, "OVERRIDE", 0, "PYTHON_9.3")
      printMsg('Portfolio picks set to zero for EOs')
   else:
      arcpy.CalculateField_management(in_sortedEOs, "PORTFOLIO", "!OVERRIDE!", "PYTHON_9.3")
      printMsg('Portfolio overrides maintained for EOs')

   if build == 'NEW' or build == 'NEW_CS':
      arcpy.CalculateField_management(in_ConSites, "PORTFOLIO", 0, "PYTHON_9.3")
      arcpy.CalculateField_management(in_ConSites, "OVERRIDE", 0, "PYTHON_9.3")
      printMsg('Portfolio picks set to zero for ConSites')
   else:
      arcpy.CalculateField_management(in_ConSites, "PORTFOLIO", "!OVERRIDE!", "PYTHON_9.3")
      printMsg('Portfolio overrides maintained for ConSites')
      
   if build == 'NEW':
      # Add "CS_CONSVALUE" and "EO_TIER" fields to ConSites, and calculate
      printMsg('Looping through ConSites to sum conservation values of EOs...')
      arcpy.AddField_management(in_ConSites, "CS_CONSVALUE", "SHORT")
      arcpy.AddField_management(in_ConSites, "ECS_TIER", "TEXT","","",15)
      arcpy.MakeFeatureLayer_management (in_sortedEOs, "lyr_EO")
      with arcpy.da.UpdateCursor(in_ConSites, ["SHAPE@", "CS_CONSVALUE", "ECS_TIER"]) as mySites:
         for site in mySites:
            myShp = site[0]
            arcpy.SelectLayerByLocation_management("lyr_EO", "INTERSECT", myShp, "", "NEW_SELECTION", "NOT_INVERT")
            c = countSelectedFeatures("lyr_EO")
            if c > 0:
               #printMsg('%s EOs selected' % str(c))
               myArray = arcpy.da.TableToNumPyArray ("lyr_EO", ("EO_CONSVALUE", "ChoiceRANK"))
               mySum = myArray["EO_CONSVALUE"].sum()
               myMin = myArray["ChoiceRANK"].min()
            else:
               #printMsg('No EOs selected')
               mySum = 0
               myMin = 6
            site[1] = mySum
            if myMin == 1:
               tier = "Irreplaceable"
            elif myMin == 2:
               tier = "Critical"
            elif myMin == 3:
               tier = "Priority"
            elif myMin == 4:
               tier = "Choice"
            else:
               tier = "NA"
            site[2] = tier
            mySites.updateRow(site)
      printMsg('CS_CONSVALUE and ECS_TIER fields set')
      
      # Add "CS_AREA_HA" field to ConSites, and calculate
      arcpy.AddField_management(in_ConSites, "CS_AREA_HA", "DOUBLE")
      expression = '!SHAPE_Area!/10000'
      arcpy.CalculateField_management(in_ConSites, "CS_AREA_HA", expression, "PYTHON_9.3")
      
      # Tabulate Intersection of ConSites with conservation lands of specified BMI values, and score
      ScoreBMI(in_ConSites, "SITEID", in_consLands_flat, "PERCENT_BMI_")
   
      # Spatial Join EOs to ConSites, and join relevant field back to EOs
      for fld in ["CS_CONSVALUE", "CS_AREA_HA"]:
         try: 
            arcpy.DeleteField_management (in_sortedEOs, fld)
         except:
            pass
      joinFeats = in_sortedEOs + '_csJoin'
      fldmap1 = 'SF_EOID "SF_EOID" true true false 20 Double 0 0 ,First,#,%s,SF_EOID,-1,-1'%in_sortedEOs
      fldmap2 = 'CS_CONSVALUE "CS_CONSVALUE" true true false 2 Short 0 0 ,Max,#,%s,CS_CONSVALUE,-1,-1' %in_ConSites
      fldmap3 = 'CS_AREA_HA "CS_AREA_HA" true true false 4 Double 0 0 ,Max,#,%s,CS_AREA_HA,-1,-1' %in_ConSites
      field_mapping="""%s;%s;%s""" %(fldmap1,fldmap2,fldmap3)
      
      printMsg('Performing spatial join between EOs and ConSites...')
      arcpy.SpatialJoin_analysis(in_sortedEOs, in_ConSites, joinFeats, "JOIN_ONE_TO_ONE", "KEEP_ALL", field_mapping, "INTERSECT")
      for fld in ["CS_CONSVALUE", "CS_AREA_HA"]:
         arcpy.JoinField_management (in_sortedEOs, "SF_EOID", joinFeats, "SF_EOID", fld)
      #printMsg('Field "CS_CONSVALUE" joined to table %s.' %in_sortedEOs)

   UpdatePortfolio(in_sortedEOs,in_ConSites,in_sumTab)
   slotDict = buildSlotDict(in_sumTab)

   if len(slotDict) > 0:
      printMsg('Trying to fill remaining slots based on land protection status...')
      for elcode in slotDict:
         printMsg('Working on %s...' %elcode)
         where_clause = '"ELCODE" = \'%s\' and "TIER" = \'Choice\' and "PORTFOLIO" = 0' %elcode
         try:
            Slots = slotDict[elcode]
            printMsg('There are still %s slots to fill.' %str(int(Slots)))
            arcpy.MakeFeatureLayer_management (in_sortedEOs, "lyr_EO", where_clause)
            c = countFeatures("lyr_EO")
            printMsg('There are %s features to fill them.' %str(int(c)))

            # Rank by BMI score
            printMsg('Filling slots based on BMI score...')
            arcpy.MakeFeatureLayer_management (in_sortedEOs, "lyr_EO", where_clause)
            addRanks("lyr_EO", "BMI_score", "DESC", "RANK_bmi", 5, "ABS")
            availSlots = updateSlots("lyr_EO", elcode, Slots, "RANK_bmi")
            Slots = availSlots
            
            # Rank by presence on NAP - prefer EOs that intersect a Natural Area Preserve
            if Slots == 0:
               pass
            else:
               printMsg('Filling slots based on presence on NAP...')
               addRanks("lyr_EO", "ysnNAP", "DESC", "RANK_nap", 0.5, "ABS")
               availSlots = updateSlots("lyr_EO", elcode, Slots, "RANK_nap")
               Slots = availSlots
            
         except:
            printWrng('There was a problem processing elcode %s.' %elcode)  
            tback()        

      UpdatePortfolio(in_sortedEOs,in_ConSites,in_sumTab)
      slotDict = buildSlotDict(in_sumTab)
   else:
      pass
   
   if len(slotDict) > 0:
      printMsg('Trying to fill remaining slots based on ConSite value...')    
      for elcode in slotDict:
         printMsg('Working on %s...' %elcode)
         where_clause = '"ELCODE" = \'%s\' and "TIER" = \'Choice\' and "PORTFOLIO" = 0' %elcode
         try:
            Slots = slotDict[elcode]
            printMsg('There are still %s slots to fill.' %str(int(Slots)))
            arcpy.MakeFeatureLayer_management (in_sortedEOs, "lyr_EO", where_clause)
            c = countFeatures("lyr_EO")
            printMsg('There are %s features where %s.' %(str(int(c)), where_clause))
            
            # Rank by site conservation value
            printMsg('Filling slots based on overall site conservation value...')
            addRanks("lyr_EO", "CS_CONSVALUE", "DESC", "RANK_csVal", 1, "ABS")
            availSlots = updateSlots("lyr_EO", elcode, Slots, "RANK_csVal")
            Slots = availSlots
         except:
            printWrng('There was a problem processing elcode %s.' %elcode)  
            tback()        

      UpdatePortfolio(in_sortedEOs,in_ConSites,in_sumTab)
      slotDict = buildSlotDict(in_sumTab)
   else:
      pass
   
   if len(slotDict) > 0:
      printMsg('Filling remaining slots based on PF number and EO size...')    
      for elcode in slotDict:
         printMsg('Working on %s...' %elcode)
         where_clause = '"ELCODE" = \'%s\' and "TIER" = \'Choice\' and "PORTFOLIO" = 0' %elcode
         try:
            Slots = slotDict[elcode]
            printMsg('There are still %s slots to fill.' %str(int(Slots)))
            arcpy.MakeFeatureLayer_management (in_sortedEOs, "lyr_EO", where_clause)
            c = countFeatures("lyr_EO")
            printMsg('There are %s features where %s.' %(str(int(c)), where_clause))   
            
            # Rank by number of procedural features - prefer EOs with more
            printMsg('Updating tiers based on number of procedural features...')
            addRanks("lyr_EO", "COUNT_SFID", "DESC", "RANK_numPF", 1, "ABS")
            availSlots = updateSlots("lyr_EO", elcode, Slots, "RANK_numPF")
            Slots = availSlots
            
            # Rank by SHAPE_Area
            if Slots == 0:
               pass
            else:
               printMsg('Filling slots based on EO size...')
               arcpy.MakeFeatureLayer_management (in_sortedEOs, "lyr_EO", where_clause)
               addRanks("lyr_EO", "SHAPE_Area", "DESC", "RANK_eoArea", thresh = 0.1, threshtype = "ABS", rounding = 2)
               availSlots = updateSlots("lyr_EO", elcode, Slots, "RANK_eoArea")
               Slots = availSlots
         except:
            printWrng('There was a problem processing elcode %s.' %elcode)  
            tback()  
      UpdatePortfolio(in_sortedEOs,in_ConSites,in_sumTab)
   else:
      pass
      
   # Create final outputs
   printMsg("Assigning extended tier attributes...")
   arcpy.AddField_management(in_sortedEOs, "EXT_TIER", "TEXT", "", "", 50)
   codeblock = '''def extTier(exclusion, tier, eoModRank, eoRankNum, recent, portfolio):
      if tier == None:
         if exclusion in ("Excluded Element", "Old Observation"):
            t = exclusion
         elif eoRankNum == 10:
            t = "Restoration Potential"
         else:
            t = "Error Check Needed"
      elif tier in ("Irreplaceable", "Critical", "Surplus"):
         t = tier
      elif tier == "Priority":
         t = "Priority - Top %s" %eoModRank
      elif tier == "Choice":
         if portfolio == 1:
            t = "Choice - In Portfolio"
         else:
            t = "Choice - Swap Option"
      else:
         t = "Error Check Needed"
         
      if recent < 2:
         t += " (Update Needed)"
      else:
         pass
         
      return t
      '''
   expression = "extTier(!EXCLUSION!, !TIER!, !EO_MODRANK!, !EORANK_NUM!, !RECENT!, !PORTFOLIO!)"
   arcpy.CalculateField_management(in_sortedEOs, "EXT_TIER", expression, "PYTHON_9.3", codeblock)
   
   fldList = [
   ["ELCODE", "ASCENDING"], 
   ["ChoiceRANK", "ASCENDING"], 
   ["RANK_mil", "ASCENDING"], 
   ["RANK_eo", "ASCENDING"], 
   ["EORANK_NUM", "ASCENDING"],
   ["RANK_year", "ASCENDING"], 
   ["RANK_bmi", "ASCENDING"], 
   ["RANK_nap", "ASCENDING"], 
   ["RANK_csVal", "ASCENDING"], 
   ["RANK_numPF", "ASCENDING"], 
   ["RANK_eoArea", "ASCENDING"], 
   ["PORTFOLIO", "DESCENDING"]
   ]
   arcpy.Sort_management(in_sortedEOs, out_sortedEOs, fldList)
   
   arcpy.Sort_management(in_ConSites, out_ConSites, [["PORTFOLIO", "DESCENDING"],["CS_CONSVALUE", "DESCENDING"]])
   
   arcpy.CopyRows_management(in_sumTab, out_sumTab)
      
   printMsg('Conservation sites prioritized and portfolio summary updated.')
   
   return (out_sortedEOs, out_sumTab, out_ConSites)

def BuildElementLists(in_Bounds, fld_ID, in_procEOs, in_elementTab, out_Tab, out_Excel):
   '''Creates a master list relating a summary of processed, viable EOs to a set of boundary polygons, which could be Conservation Sites, Natural Area Preserves, parcels, or any other boundaries. The output table is sorted by polygon ID, Element, tier, and G-rank. Optionally, the output table can be exported to an excel spreadsheet.
   Parameters:
   - in_Bounds: Input polygon feature class for which Elements will be summarized
   - fld_ID: Field in in_Bounds used to identify polygons
   - in_procEOs: Input processed EOs, resulting from the BuildPortfolio function
   - in_elementTab: Input updated Element Portfolio Summary table, resulting from the BuildPortfolio function
   - out_Tab: Output table summarizing Elements by boundaries
   - out_Excel: Output table converted to Excel spreadsheet. Specify "None" if none is desired.
   '''
   scratchGDB = arcpy.env.scratchGDB
   
   # Dissolve boundaries on the specified ID field, retaining only that field.
   printMsg("Dissolving...")
   dissBnds = scratchGDB + os.sep + "dissBnds"
   arcpy.Dissolve_management(in_Bounds, dissBnds, fld_ID, "", "MULTI_PART")
   
   # Make feature layer containing only viable EOs
   where_clause = '"ChoiceRANK" < 6'
   arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_EO", where_clause)
   
   # Perform spatial join between EOs and dissolved boundaries
   printMsg("Spatial joining...")
   sjEOs = scratchGDB + os.sep + "sjEOs"
   arcpy.SpatialJoin_analysis("lyr_EO", dissBnds, sjEOs, "JOIN_ONE_TO_MANY", "KEEP_COMMON", "", "INTERSECT")
   
   # Export the table from the spatial join. This appears to be necessary for summary statistics to work. Why?
   printMsg("Exporting spatial join table...")
   sjTab = scratchGDB + os.sep + "sjTab"
   arcpy.TableToTable_conversion (sjEOs, scratchGDB, "sjTab")
   
   # Compute the summary stats
   printMsg("Computing summary statistics...")
   sumTab = scratchGDB + os.sep + "sumTab"
   caseFields = "%s;ELCODE;SNAME;RNDGRNK"%fld_ID
   statsList = [["ChoiceRANK", "MIN"],["EO_MODRANK", "MIN"]]
   arcpy.Statistics_analysis(sjTab, sumTab, statsList, caseFields)
   
   # Add and calculate a TIER field
   printMsg("Calculating TIER field...")
   arcpy.AddField_management(sumTab, "TIER", "TEXT", "", "", "15")
   codeblock = '''def calcTier(rank):
      if rank == 1:
         return "Irreplaceable"
      elif rank == 2:
         return "Critical"
      elif rank == 3:
         return "Priority"
      elif rank == 4:
         return "Choice"
      elif rank == 5:
         return "Surplus"
      else:
         return "NA"
      '''
   expression = "calcTier( !MIN_ChoiceRANK!)"
   arcpy.CalculateField_management(sumTab, "TIER", expression, "PYTHON_9.3", codeblock)
   
   # Make a data dictionary relating ELCODE to FREQUENCY (= number of viable EOs) 
   viableDict = TabToDict(in_elementTab, "ELCODE", "FREQUENCY")
   
   # Add and calculate an ALL_IN field
   # This indicates if the boundary contains all of the state's viable example(s) of an Element
   printMsg("Calculating ALL_IN field...")
   arcpy.AddField_management(sumTab, "ALL_IN", "SHORT")
   codeblock = '''def allIn(elcode, frequency, viableDict):
      try:
         numViable = viableDict[elcode]
         if numViable <= frequency:
            return 1
         else:
            return 0
      except:
         return -1
      '''
   expression = "allIn(!ELCODE!, !FREQUENCY!, %s)"%viableDict
   arcpy.CalculateField_management(sumTab, "ALL_IN", expression, "PYTHON_9.3", codeblock)

   # Sort to create final output table
   printMsg("Sorting...")
   sortFlds ="%s ASCENDING;MIN_ChoiceRANK ASCENDING;ALL_IN DESCENDING; RNDGRNK ASCENDING"%fld_ID
   arcpy.Sort_management(sumTab, out_Tab, sortFlds)
   
   # Export to Excel
   if out_Excel == "None":
      pass
   else:
      printMsg("Exporting to Excel...")
      arcpy.TableToExcel_conversion(out_Tab, out_Excel)
   
   return out_Tab
   
# Use the main function below to run desired function(s) directly from Python IDE or command line with hard-coded variables
def main():
   ### Set up input variables ###
   
   # Path to output geodatabase
   out_GDB = r'F:\Working\EssentialConSites\ECS_Run_March2020\ECS_Outputs_March2020.gdb'
   
   # Path to directory for storing output spreadsheets
   out_DIR = r'F:\Working\EssentialConSites\ECS_Run_March2020\Spreadsheets_March2020' 
   
   # Input Procedural Features by site type
   in_pf_tcs = r'F:\Working\EssentialConSites\ECS_Run_March2020\ECS_Inputs_March2020.gdb\pfTerrestrial'
   in_pf_scu = r'F:\Working\EssentialConSites\ECS_Run_March2020\ECS_Inputs_March2020.gdb\pfStream'
   in_pf_kcs = r'F:\Working\EssentialConSites\ECS_Run_March2020\ECS_Inputs_March2020.gdb\pfKarst'
   
   # Input Conservation Sites by type
   in_cs_tcs = r'F:\Working\EssentialConSites\ECS_Run_March2020\ECS_Inputs_March2020.gdb\csTerrestrial'
   in_cs_scu = r'F:\Working\EssentialConSites\ECS_Run_March2020\ECS_Inputs_March2020.gdb\csStream'
   in_cs_kcs = r'F:\Working\EssentialConSites\ECS_Run_March2020\ECS_Inputs_March2020.gdb\csKarst'
   
   # Input other standard variables
   in_elExclude = r'F:\Working\EssentialConSites\ECS_Run_March2020\ECS_Inputs_March2020.gdb\ElementExclusions'
   in_consLands = r'F:\Working\EssentialConSites\ECS_Run_March2020\ECS_Inputs_March2020.gdb\conslands200302'
   in_consLands_flat = r'F:\Working\EssentialConSites\ECS_Run_March2020\ECS_Inputs_March2020.gdb\conslands200302_flat'
   in_ecoReg = r'F:\Working\EssentialConSites\ECS_Run_March2020\ECS_Inputs_March2020.gdb\tncEcoRegions_lam'
   fld_RegCode = 'GEN_REG'
   
   # Input cutoff years
   cutYear = 1995 # yyyy - 25 for TCS and SCU
   flagYear = 2000 # yyyy - 20 for TCS and SCU
   cutYear_kcs = 1980 # yyyy - 40 for KCS
   flagYear_kcs = 1985 # yyyy - 35 for KCS

   # Set up outputs by type - no need to change these as long as your out_GDB above is valid
   attribEOs_tcs = out_GDB + os.sep + 'attribEOs_tcs'
   sumTab_tcs = out_GDB + os.sep + 'sumTab_tcs'
   scoredEOs_tcs = out_GDB + os.sep + 'scoredEOs_tcs'
   priorEOs_tcs = out_GDB + os.sep + 'priorEOs_tcs'
   sumTab_upd_tcs = out_GDB + os.sep + 'sumTab_upd_tcs'
   priorConSites_tcs = out_GDB + os.sep + 'priorConSites_tcs'
   elementList_tcs = out_GDB + os.sep + 'elementList_tcs'
   excelList_tcs = out_DIR + os.sep + 'elementList_tcs.xls'
   
   attribEOs_scu = out_GDB + os.sep + 'attribEOs_scu'
   sumTab_scu = out_GDB + os.sep + 'sumTab_scu'
   scoredEOs_scu = out_GDB + os.sep + 'scoredEOs_scu'
   priorEOs_scu = out_GDB + os.sep + 'priorEOs_scu'
   sumTab_upd_scu = out_GDB + os.sep + 'sumTab_upd_scu'
   priorConSites_scu = out_GDB + os.sep + 'priorConSites_scu'
   elementList_scu = out_GDB + os.sep + 'elementList_scu'
   excelList_scu = out_DIR + os.sep + 'elementList_scu.xls'   
      
   attribEOs_kcs = out_GDB + os.sep + 'attribEOs_kcs'
   sumTab_kcs = out_GDB + os.sep + 'sumTab_kcs'
   scoredEOs_kcs = out_GDB + os.sep + 'scoredEOs_kcs'
   priorEOs_kcs = out_GDB + os.sep + 'priorEOs_kcs'
   sumTab_upd_kcs = out_GDB + os.sep + 'sumTab_upd_kcs'
   priorConSites_kcs = out_GDB + os.sep + 'priorConSites_kcs'
   elementList_kcs = out_GDB + os.sep + 'elementList_kcs'
   excelList_kcs = out_DIR + os.sep + 'elementList_kcs.xls'
   
   
   ### Specify functions to run - no need to change these as long as all your input/output variables above are valid ###
   
   # Attribute EOs
   AttributeEOs(in_pf_tcs, in_elExclude, in_consLands, in_consLands_flat, in_ecoReg, fld_RegCode, cutYear, flagYear, attribEOs_tcs, sumTab_tcs)
   
   AttributeEOs(in_pf_scu, in_elExclude, in_consLands, in_consLands_flat, in_ecoReg, fld_RegCode, cutYear, flagYear, attribEOs_scu, sumTab_scu)
   
   AttributeEOs(in_pf_kcs, in_elExclude, in_consLands, in_consLands_flat, in_ecoReg, fld_RegCode, cutYear_kcs, flagYear_kcs, attribEOs_kcs, sumTab_kcs)
   
   
   # Score EOs
   ScoreEOs(attribEOs_tcs, sumTab_tcs, scoredEOs_tcs, ysnMil = "false", ysnYear = "true")
   
   ScoreEOs(attribEOs_scu, sumTab_scu, scoredEOs_scu, ysnMil = "false", ysnYear = "true")
   
   ScoreEOs(attribEOs_kcs, sumTab_kcs, scoredEOs_kcs, ysnMil = "false", ysnYear = "true")
   
   
   # Build Portfolio
   BuildPortfolio(scoredEOs_tcs, priorEOs_tcs, sumTab_tcs, sumTab_upd_tcs, in_cs_tcs, priorConSites_tcs, in_consLands_flat, build = 'NEW')
   
   BuildPortfolio(scoredEOs_scu, priorEOs_scu, sumTab_scu, sumTab_upd_scu, in_cs_scu, priorConSites_scu, in_consLands_flat, build = 'NEW')
   
   BuildPortfolio(scoredEOs_kcs, priorEOs_kcs, sumTab_kcs, sumTab_upd_kcs, in_cs_kcs, priorConSites_kcs, in_consLands_flat, build = 'NEW')
   
   
   # Build Elements List
   BuildElementLists(in_cs_tcs, 'SITENAME', priorEOs_tcs, sumTab_upd_tcs, elementList_tcs, excelList_tcs)
   
   BuildElementLists(in_cs_scu, 'SITENAME', priorEOs_scu, sumTab_upd_scu, elementList_scu, excelList_scu)
   
   BuildElementLists(in_cs_kcs, 'SITENAME', priorEOs_kcs, sumTab_upd_kcs, elementList_kcs, excelList_kcs)
   
if __name__ == '__main__':
   main()
