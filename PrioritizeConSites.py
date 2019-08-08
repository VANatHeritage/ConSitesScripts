# ---------------------------------------------------------------------------
# EssentialConSites.py
# Version:  ArcGIS 10.3 / Python 2.7
# Creation Date: 2018-02-21
# Last Edit: 2019-08-08
# Creator:  Kirsten R. Hazler and Roy Gilb
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
   scratchGDB = arcpy.env.scratchGDB
   #printMsg("Tabulating intersection of EOs with conservation lands of specified BMI...")
   where_clause = '"BMI" = \'%s\'' %bmiValue
   arcpy.MakeFeatureLayer_management (conslands, "lyr_bmi", where_clause)
   TabInter_bmi = scratchGDB + os.sep + "TabInter_bmi"
   arcpy.TabulateIntersection_analysis(inFeats, uniqueID, "lyr_bmi", TabInter_bmi)
   arcpy.AddField_management(TabInter_bmi, fldName, "DOUBLE")
   arcpy.CalculateField_management(TabInter_bmi, fldName, "!PERCENTAGE!", "PYTHON")
   arcpy.JoinField_management(inFeats, uniqueID, TabInter_bmi, uniqueID, fldName)
   
   return inFeats

def ScoreBMI(inFeats, uniqueID, conslands, fldBasename = "PERCENT_BMI_"):
   '''A helper function that tabulates the percentage of each input polygon covered by conservation lands with specified BMI value. Called by the AttributeEOs function to tabulate for EOs.
   Parameters:
   - inFeats: Feature class with polygons for which BMI should be tabulated
   - uniqueID: Field in input feature class serving as unique ID
   - conslands: Feature class with conservation lands, flattened by BMI level
   - fldBasename: The baseline of the field name to be used to store percent of polygon covered by selected conservation lands of specified BMI
   '''
   fldNames = {}
   
   for val in [1,2,3,4]:
      fldName = fldBasename + str(val)
      printMsg("Tabulating intersection with BMI %s"%str(val))
      TabulateBMI(inFeats, uniqueID, conslands, str(val), fldName)
      fldNames[val] = fldName
      
   printMsg("Calculating BMI score...")
   arcpy.AddField_management(inFeats, "BMI_score", "DOUBLE")
   codeblock = '''def score(bmi1, bmi2, bmi3, bmi4):
      parmVals = {1:bmi1, 2:bmi2, 3:bmi3, 4:bmi4}
      for key in parmVals:
         if not parmVals[key]:
            parmVals[key] = 0.0
      score = int((8*parmVals[1] + 4*parmVals[2] + 2*parmVals[3] + 1*parmVals[4])/8)
      return score'''
   expression = 'score(!%s!, !%s!, !%s!, !%s!)'%(fldNames[1], fldNames[2], fldNames[3], fldNames[4])
   arcpy.CalculateField_management(inFeats, "BMI_score", expression, "PYTHON_9.3", codeblock)
   
   return inFeats
   
def addRanks(table, sort_field, order = 'ASCENDING', rank_field='RANK', thresh = 5, threshtype = 'ABS', rounding = None):
   '''A helper function called by ScoreEOs and BuildPortfolio functions; ranks records by one specified sorting field.
   Parameters:
   - table: the input table to which ranks will be added
   - sort_field: the input field on which ranks will be based
   - order: controls the sorting order. Assumes ascending order unless "DESC" or "DESCENDING" is entered.
   - rank_field: the name of the new field that will be created to contain the ranks
   - thresh: the amount by which sorted values must differ to be ranked differently. 
   - threshtype: determines whether the threshold is an absolute value ("ABS") or a percentage ("PER")
   - rounding: determines whether sorted values are to be rounded prior to ranking, and by how much. Must be an integer or None. With rounding = 2, 1234.5678 and 1234.5690 are treated as the equivalent number for ranking purposes. With rounding = -1, 11 and 12 are treated as equivalents for ranking.
   '''
   valList = unique_values(table, sort_field)
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
   printMsg('Ranking dictionary (value:rank) is as follows: %s' %str(rankDict))
   
   #printMsg('Writing ranks to table...')
   if not arcpy.ListFields(table, rank_field):
      arcpy.AddField_management(table, rank_field, "SHORT")
   codeblock = '''def rankVals(val, rankDict, rounding):
      if rounding <> None:
         val = round(val,rounding)
      rank = rankDict[val]
      return rank'''
   expression = "rankVals(!%s!, %s, %s)" %(sort_field, rankDict, rounding)
   arcpy.CalculateField_management(table, rank_field, expression, "PYTHON_9.3", codeblock)
   #printMsg('Finished ranking.')
   return
      
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
      where_clause1 = '"ELCODE" = \'%s\' AND "TIER" = \'Choice\' AND "PORTFOLIO" = 0 AND "%s" <= %s' %(elcode, rankFld, str(r))
      where_clause2 = '"ELCODE" = \'%s\' AND "TIER" = \'Choice\' AND "PORTFOLIO" = 0 AND "%s" > %s' %(elcode, rankFld, str(r))
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
   where_clause = '"ChoiceRANK" < 4 OR "PORTFOLIO" = 1' 
   arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_EO", where_clause)
   arcpy.MakeFeatureLayer_management (in_ConSites, "lyr_CS")
   arcpy.SelectLayerByLocation_management ("lyr_CS", "INTERSECT", "lyr_EO", 0, "NEW_SELECTION", "NOT_INVERT")
   arcpy.CalculateField_management("lyr_CS", "PORTFOLIO", 1, "PYTHON_9.3")
   arcpy.CalculateField_management("lyr_EO", "PORTFOLIO", 1, "PYTHON_9.3")
   printMsg('ConSites portfolio updated')
   
   # Intersect Choice EOs with Portfolio ConSites, and set PORTFOLIO to 1
   where_clause = '"TIER" = \'Choice\''
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
   
   fields = ["Irreplaceable", "Essential", "Priority", "Choice", "Surplus"]
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
   
def AttributeEOs(in_ProcFeats, in_sppExcl, in_consLands, in_consLands_flat, out_procEOs, out_sumTab):
   '''Attaches various attributes to EOs, creating a new output attributed feature class as well as a summary table. The outputs from this function are subsequently used in the function ScoreEOs. 
   Parameters:
   - in_ProcFeats: Input feature class with "site-worthy" procedural features
   - in_eoReps: Input feature class or table with EO reps, e.g., EO_Reps_All.shp
   - in_sppExcl: Input table containing list of elements to be excluded from the process, e.g., EO_Exclusions.dbf
   - in_eoSelOrder: Input table designating selection order for different EO rank codes, e.g., EORANKNUM.dbf
   - in_consLands: Input feature class with conservation lands (managed areas), e.g., MAs.shp
   - in_consLands_flat: A "flattened" version of in_ConsLands, based on level of Biodiversity Management Intent (BMI). (This is needed due to stupid overlapping polygons in our database. Sigh.)
   - out_procEOs: Output EOs with TIER scores and other attributes.
   - out_sumTab: Output table summarizing number of included EOs per element'''
   
   scratchGDB = arcpy.env.scratchGDB
   
   # Dissolve procedural features on SF_EOID
   printMsg("Dissolving procedural features by EO...")
   arcpy.Dissolve_management(in_ProcFeats, out_procEOs, ["SF_EOID", "ELCODE", "SNAME", "BIODIV_GRANK", "BIODIV_SRANK", "RNDGRNK", "EORANK", "EOLASTOBS", "FEDSTAT", "SPROT"], [["SFID", "COUNT"]], "MULTI_PART")
      
   # Add and calculate some fields
   
   # Field: SEL_ORDER
   printMsg("Calculating SEL_ORDER field")
   arcpy.AddField_management(out_procEOs, "SEL_ORDER", "SHORT")
   codeblock = '''def selOrder(eorank):
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
      else:
         return -1
      '''
   expression = "selOrder(!EORANK!)"
   arcpy.CalculateField_management(out_procEOs, "SEL_ORDER", expression, "PYTHON_9.3", codeblock)
   
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
   arcpy.AddField_management(out_procEOs, "EXCLUSION", "TEXT", "", "", 20) # This will be calculated below by groups
   
   # Set EXCLUSION value for low EO ranks
   codeblock = '''def reclass(order):
      if order == -1 or order == None:
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
   ScoreBMI(out_procEOs, "SF_EOID", in_consLands_flat, fldBasename = "PERCENT_BMI_")
   
   # Field: ysnNAP
   arcpy.AddField_management(out_procEOs, "ysnNAP", "SHORT")
   arcpy.CalculateField_management(out_procEOs, "ysnNAP", 0, "PYTHON")
   arcpy.MakeFeatureLayer_management(out_procEOs, "lyr_EO")
   where_clause = '"MATYPE" = \'State Natural Area Preserve\''
   arcpy.MakeFeatureLayer_management(in_consLands, "lyr_NAP", where_clause) 
   arcpy.SelectLayerByLocation_management("lyr_EO", "INTERSECT", "lyr_NAP", "", "NEW_SELECTION", "NOT_INVERT")
   arcpy.CalculateField_management("lyr_EO", "ysnNAP", 1, "PYTHON")
   #arcpy.SelectLayerByAttribute_management("lyr_EO", "CLEAR_SELECTION")
   
   # Get subset of EOs to summarize based on EXCLUSION field
   where_clause = '"EXCLUSION" = \'Keep\''
   arcpy.MakeFeatureLayer_management (out_procEOs, "lyr_EO", where_clause)
      
   # Summarize to get count of EOs per element
   printMsg("Summarizing...")
   arcpy.Statistics_analysis("lyr_EO", out_sumTab, [["SF_EOID", "COUNT"]], ["ELCODE", "SNAME", "NEW_GRANK"])
   
   # Add more info to summary table
   # Field: TARGET
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
      elif grank == 'G1' and count <= 10:
         return "Essential"
      elif grank == 'G2' and count <= 5:
         return "Essential"
      elif grank in ('G3', 'G4', 'G5') and count <= 2:
         return "Essential"
      else:
         return "Choice"'''
   expression = "calcTier(!NEW_GRANK!, !COUNT_SF_EOID!)"
   arcpy.CalculateField_management(out_sumTab, "TIER", expression, "PYTHON_9.3", codeblock)
   
   # Join the TIER field to the EO table
   arcpy.JoinField_management("lyr_EO", "ELCODE", out_sumTab, "ELCODE", "TIER")
   
   printMsg("EO attribution complete")
   return (out_procEOs, out_sumTab)
   
def ScoreEOs(in_procEOs, in_sumTab, ysnMil, out_sortedEOs):
   '''Ranks EOs within an element based on a variety of attributes. This function must follow, and requires inputs from, the outputs of the AttributeEOs function. 
   Parameters:
   - in_procEOs: input feature class of processed EOs (i.e., out_procEOs from the AttributeEOs function)
   - in_sumTab: input table summarizing number of included EOs per element (i.e., out_sumTab from the AttributeEOs function.
   - ysnMil: determines whether to consider military land as a ranking factor ("true") or not ("false")
   - out_sortedEOs: output feature class of processed EOs, sorted by element code and rank.
   '''
         
   # Make copy of input
   scratchGDB = "in_memory"
   tmpEOs = scratchGDB + os.sep + "tmpEOs"
   arcpy.CopyFeatures_management(in_procEOs, tmpEOs)
   in_procEOs = tmpEOs
   
   # Add ranking fields
   for fld in ['RANK_mil', 'RANK_eo', 'RANK_year', 'RANK_numPF', 'RANK_csVal', 'RANK_nap', 'RANK_bmi', 'RANK_eoArea']:
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
         print 'There are %s "Choice" features with this elcode' % str(currentCount)
         
         # Rank by military land - prefer EOs not on military land
         if ysnMil == "false":
            arcpy.CalculateField_management(in_procEOs, "RANK_mil", 1, "PYTHON_9.3")
         else: 
            printMsg('Updating tiers based on proportion of EO on military land...')
            arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_EO", where_clause)
            addRanks("lyr_EO", "PERCENT_MIL", "", rank_field='RANK_mil', thresh = 5, threshtype = "ABS")
            availSlots = updateTiers("lyr_EO", elcode, Slots, "RANK_mil")
            Slots = availSlots
         
         # Rank by EO-rank (selection order) - prefer highest-ranked EOs
         if Slots == 0:
            pass
         else:
            printMsg('Updating tiers based on EO-rank...')
            addRanks("lyr_EO", "SEL_ORDER", "", rank_field='RANK_eo', thresh = 0.5, threshtype = "ABS")
            availSlots = updateTiers("lyr_EO", elcode, Slots, "RANK_eo")
            Slots = availSlots
      
         # Rank by last observation year - prefer more recently observed EOs
         if Slots == 0:
            pass
         else:
            printMsg('Updating tiers based on last observation...')
            arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_EO", where_clause)
            addRanks("lyr_EO", "OBSYEAR", "DESC", rank_field='RANK_year', thresh = 5, threshtype = "ABS")
            availSlots = updateTiers("lyr_EO", elcode, Slots, "RANK_year")
            Slots = availSlots
         
         # Rank by number of procedural features - prefer EOs with more of them
         if Slots == 0:
            pass
         else:
            printMsg('Updating tiers based on number of procedural features...')
            arcpy.MakeFeatureLayer_management (in_procEOs, "lyr_EO", where_clause)
            addRanks("lyr_EO", "COUNT_SFID", "DESC", rank_field='RANK_numPF', thresh = 1, threshtype = "ABS")
            availSlots = updateTiers("lyr_EO", elcode, Slots, "RANK_numPF")
            Slots = availSlots
         if Slots > 0:
            printMsg('No more criteria available for differentiation; Choice ties remain.')         
         
      except:
         printWrng('There was a problem processing elcode %s.' %elcode)
         tback()
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
   
   arcpy.Sort_management(in_procEOs, out_sortedEOs, [["ELCODE", "ASCENDING"], ["ChoiceRANK", "ASCENDING"], ["RANK_mil", "ASCENDING"], ["RANK_eo", "ASCENDING"], ["RANK_year", "ASCENDING"], ["RANK_numPF", "ASCENDING"]])

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
      
   # Add "PORTFOLIO" field to in_sortedEOs and in_ConSites tables, and set to zero
   for tab in [in_sortedEOs, in_ConSites]:
      arcpy.AddField_management(tab, "PORTFOLIO", "SHORT")
      # This command should be ignored if field already exists
      
   if build == 'NEW' or build == 'NEW_EO':
      arcpy.CalculateField_management(in_sortedEOs, "PORTFOLIO", 0, "PYTHON_9.3")
      printMsg('Portfolio picks reset to zero for EOs')
   else:
      printMsg('Portfolio picks maintained for EOs')

   if build == 'NEW' or build == 'NEW_CS':
      arcpy.CalculateField_management(in_ConSites, "PORTFOLIO", 0, "PYTHON_9.3")
      printMsg('Portfolio picks reset to zero for ConSites')
   else:
      printMsg('Portfolio picks maintained for ConSites')
      
   if build == 'NEW':
      # Add "EO_CONSVALUE" field to in_sortedEOs, and calculate
      arcpy.AddField_management(in_sortedEOs, "EO_CONSVALUE", "SHORT")
      codeblock = '''def calcConsVal(tier):
         if tier == "Irreplaceable":
            return 100
         elif tier == "Essential":
            return 50
         elif tier == "Priority":
            return 25
         elif tier == "Choice":
            return 5
         else:
            return 1'''
      expression = "calcConsVal(!TIER!)"
      arcpy.CalculateField_management(in_sortedEOs, "EO_CONSVALUE", expression, "PYTHON_9.3", codeblock)
      printMsg('EO_CONSVALUE field set')
      
      # Add "CS_CONSVALUE" field to ConSites, and calculate
      printMsg('Looping through ConSites to sum conservation values of EOs...')
      arcpy.AddField_management(in_ConSites, "CS_CONSVALUE", "SHORT")
      arcpy.MakeFeatureLayer_management (in_sortedEOs, "lyr_EO")
      with arcpy.da.UpdateCursor(in_ConSites, ["SHAPE@", "CS_CONSVALUE"]) as mySites:
         for site in mySites:
            myShp = site[0]
            arcpy.SelectLayerByLocation_management("lyr_EO", "INTERSECT", myShp, "", "NEW_SELECTION", "NOT_INVERT")
            c = countSelectedFeatures("lyr_EO")
            if c > 0:
               #printMsg('%s EOs selected' % str(c))
               myArray = arcpy.da.TableToNumPyArray ("lyr_EO", "EO_CONSVALUE")
               mySum = myArray["EO_CONSVALUE"].sum()
            else:
               #printMsg('No EOs selected')
               mySum = 0
            site[1] = mySum
            mySites.updateRow(site)
      printMsg('CS_CONSVALUE field set')
      
      # Add "CS_AREA_HA" field to ConSites, and calculate
      arcpy.AddField_management(in_ConSites, "CS_AREA_HA", "DOUBLE")
      expression = '!SHAPE_Area!/10000'
      arcpy.CalculateField_management(in_ConSites, "CS_AREA_HA", expression, "PYTHON_9.3")
      
      # Tabulate Intersection of ConSites with conservation lands of specified BMI values, and score
      ScoreBMI(in_ConSites, "SITEID", in_consLands_flat, fldBasename = "PERCENT_BMI_")
   
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
            addRanks("lyr_EO", "CS_CONSVALUE", "DESC", rank_field='RANK_csVal', thresh = 0.5, threshtype = "ABS")
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
      printMsg('Trying to fill remaining slots based on land protection status...')
      for elcode in slotDict:
         printMsg('Working on %s...' %elcode)
         where_clause = '"ELCODE" = \'%s\' and "TIER" = \'Choice\' and "PORTFOLIO" = 0' %elcode
         try:
            Slots = slotDict[elcode]
            printMsg('There are still %s slots to fill.' %str(int(Slots)))
            arcpy.MakeFeatureLayer_management (in_sortedEOs, "lyr_EO", where_clause)
            c = countFeatures("lyr_EO")
            printMsg('There are %s features where %s.' %(str(int(c)), where_clause))

            # Rank by presence on NAP - prefer EOs that intersect a Natural Area Preserve
            printMsg('Filling slots based on presence on NAP...')
            arcpy.MakeFeatureLayer_management (in_sortedEOs, "lyr_EO", where_clause)
            addRanks("lyr_EO", "ysnNAP", "DESC", rank_field='RANK_nap', thresh = 0.5, threshtype = "ABS")
            availSlots = updateSlots("lyr_EO", elcode, Slots, "RANK_nap")
            Slots = availSlots
                              
            # Rank by BMI score
            if Slots == 0:
               pass
            else:
               printMsg('Filling slots based on BMI score...')
               arcpy.MakeFeatureLayer_management (in_sortedEOs, "lyr_EO", where_clause)
               addRanks("lyr_EO", "BMI_score", "DESC", rank_field='RANK_bmi', thresh = 5, threshtype = "ABS")
               availSlots = updateSlots("lyr_EO", elcode, Slots, "RANK_bmi")
               Slots = availSlots
            
         except:
            printWrng('There was a problem processing elcode %s.' %elcode)  
            tback()        

      UpdatePortfolio(in_sortedEOs,in_ConSites,in_sumTab)
      slotDict = buildSlotDict(in_sumTab)
   else:
      pass
   
   if len(slotDict) > 0:
      printMsg('Filling remaining slots based on EO size...')    
      for elcode in slotDict:
         printMsg('Working on %s...' %elcode)
         where_clause = '"ELCODE" = \'%s\' and "TIER" = \'Choice\' and "PORTFOLIO" = 0' %elcode
         try:
            Slots = slotDict[elcode]
            printMsg('There are still %s slots to fill.' %str(int(Slots)))
            arcpy.MakeFeatureLayer_management (in_sortedEOs, "lyr_EO", where_clause)
            c = countFeatures("lyr_EO")
            printMsg('There are %s features where %s.' %(str(int(c)), where_clause))   
   
            # Rank by SHAPE_Area
            printMsg('Filling slots based on EO size...')
            addRanks("lyr_EO", "SHAPE_Area", "DESC", rank_field='RANK_eoArea', thresh = 0.1, threshtype = "ABS", rounding = 2)
            availSlots = updateSlots("lyr_EO", elcode, Slots, "RANK_eoArea")
            Slots = availSlots
         except:
            printWrng('There was a problem processing elcode %s.' %elcode)  
            tback()  
      UpdatePortfolio(in_sortedEOs,in_ConSites,in_sumTab)
   else:
      pass
      
   # Create final outputs
   arcpy.Sort_management(in_sortedEOs, out_sortedEOs, [["ELCODE", "ASCENDING"], ["ChoiceRANK", "ASCENDING"], ["RANK_mil", "ASCENDING"], ["RANK_eo", "ASCENDING"], ["RANK_year", "ASCENDING"], ["RANK_numPF", "ASCENDING"], ["RANK_nap", "ASCENDING"], ["RANK_bmi", "ASCENDING"], ["RANK_csVal", "ASCENDING"], ["RANK_eoArea", "ASCENDING"], ["PORTFOLIO", "DESCENDING"]])
   
   arcpy.Sort_management(in_ConSites, out_ConSites, [["CS_CONSVALUE", "DESCENDING"]])
   
   arcpy.CopyRows_management(in_sumTab, out_sumTab)
      
   printMsg('Conservation sites prioritized and portfolio summary updated.')
   
   return (out_sortedEOs, out_sumTab, out_ConSites)
   
# Use the main function below to run desired function(s) directly from Python IDE or command line with hard-coded variables
def main():
   # Set up variables
   in_ProcFeats = r'C:\Users\xch43889\Documents\Working\EssentialConSites\Biotics\biotics_extract.gdb\ProcFeats_20190619_175628'
   in_eoReps = r'C:\Users\xch43889\Documents\Working\EssentialConSites\Biotics\biotics_extract.gdb\EOs_20190620'
   in_sppExcl= r'C:\Users\xch43889\Documents\Working\EssentialConSites\ECS_Inputs.gdb\ExcludeSpecies'
   in_eoSelOrder = r'C:\Users\xch43889\Documents\Working\EssentialConSites\ECS_Inputs.gdb\EO_RankNum'
   in_consLands = r'C:\Users\xch43889\Documents\Working\EssentialConSites\Biotics\bioticsdata6132019.gdb\ManagedAreas6172019'
   in_consLands_flat = r'C:\Users\xch43889\Documents\Working\EssentialConSites\ECS_Inputs.gdb\flatConsLands'
   in_ConSites = r'C:\Users\xch43889\Documents\Working\EssentialConSites\Biotics\biotics_extract.gdb\ConSites_20190619_175628'   #r'C:\Users\xch43889\Documents\Working\ConSites\Essential_ConSites\ECS_Inputs.gdb\ConSites_TestSubset2'
   out_procEOs = r'C:\Users\xch43889\Documents\Working\EssentialConSites\ECS_Outputs_20190620.gdb\tcs_attribEOs'
   out_sumTab = r'C:\Users\xch43889\Documents\Working\EssentialConSites\ECS_Outputs_20190620.gdb\tcs_elementSumTab'
   out_sortedEOs = r'C:\Users\xch43889\Documents\Working\EssentialConSites\ECS_Outputs_20190620.gdb\tcs_sortedEOs'
   # End of variable input

   # Specify function(s) to run below
   AttributeEOs(in_ProcFeats, in_eoReps, in_sppExcl, in_eoSelOrder, in_consLands, in_consLands_flat, out_procEOs, out_sumTab)
   # ScoreEOs(out_procEOs, out_sumTab, out_sortedEOs)
   # BuildPortfolio(out_sortedEOs, out_sumTab, in_ConSites, 'NEW')
   
if __name__ == '__main__':
   main()
