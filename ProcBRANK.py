### SLATED FOR DELETION - Function present in PrioritizeConSites.py
# ---------------------------------------------------------------------------
# ProcBRANK.py
# Version:  ArcGIS 10.3 / Python 2.7
# Creation Date: 2019-06-20
# Last Edit: 2019-06-25
# Creator:  Kirsten R. Hazler
# ---------------------------------------------------------------------------

# Import modules and functions
import Helper
from Helper import *

def getBRANK(in_EOs, in_ConSites):
   '''Automates the assignment of B-ranks to conservation sites
   
   '''

   ### For the EOs, calculate the IBR (individual B-rank)
   printMsg('Creating and calculating IBR fields for EOs...')
   arcpy.AddField_management(in_EOs, "IBR_1", "TEXT", 2)
   codeblock1 = '''def ibr(grank, srank, eorank, fstat, sstat):
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
            elif srank == "S3":
               return "B5"
            else:
               return "BU"
      elif eorank == "B":
         if grank in ("G1", "G2"):
            return "B2"
         elif grank == "G3":
            return "B3"
         else:
            if srank == "S1":
               return "B4"
            elif srank in ("S2", "S3"):
               return "B5"
            else:
               return "BU"
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
            else:
               return "BU"
      else:
         return "BU"
   '''
   expression1 = "ibr(!BIODIV_GRANK!, !SRANK!, !BIODIV_EORANK!, !FEDSTAT!, !SPROT!)"
   arcpy.CalculateField_management(in_EOs, "IBR_1", expression1, "PYTHON_9.3", codeblock1)
   
   arcpy.AddField_management(in_EOs, "IBR_2", "TEXT", 2)
   codeblock2 = '''def ibr(tier, grank, srank, eorank, fstat, sstat):
      if eorank == "A":
         if grank == "G1" or tier == "Irreplaceable":
            return "B1"
         elif grank in ("G2", "G3"):
            return "B2"
         else:
            if srank == "S1":
               return "B3"
            elif srank == "S2":
               return "B4"
            elif srank == "S3":
               return "B5"
            else:
               return "BU"
      elif eorank == "B":
         if grank in ("G1", "G2") or tier == "Irreplaceable":
            return "B2"
         elif grank == "G3":
            return "B3"
         else:
            if srank == "S1":
               return "B4"
            elif srank in ("S2", "S3"):
               return "B5"
            else:
               return "BU"
      elif eorank == "C":
         if grank == "G1" or tier == "Irreplaceable":
            return "B2"
         elif grank == "G2":
            return "B3"
         elif grank == "G3":
            return "B4"
         else:
            if srank in ("S1", "S2"):
               return "B5"
            else:
               return "BU"
      elif eorank == "D":
         if grank == "G1" or tier == "Irreplaceable":
            return "B2"
         elif grank == "G2":
            return "B3"
         elif grank == "G3":
            return "B4"
         else:
            if (fstat in ("LT%", "LE%") or sstat in ("LT", "LE")) and (srank in ("S1", "S2")):
               return "B5"
            else:
               return "BU"
      else:
         return "BU"
   '''
   expression2 = "ibr(!TIER!,!BIODIV_GRANK!, !SRANK!, !BIODIV_EORANK!, !FEDSTAT!, !SPROT!)"
   arcpy.CalculateField_management(in_EOs, "IBR_2", expression2, "PYTHON_9.3", codeblock2)
   
   ### For the EOs, calculate the IBR score
   printMsg('Creating and calculating IBR_SCORE fields for EOs...')
   arcpy.AddField_management(in_EOs, "IBR_SCORE1", "LONG")
   arcpy.AddField_management(in_EOs, "IBR_SCORE2", "LONG")
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
   expression1 = "score(!IBR_1!)"
   arcpy.CalculateField_management(in_EOs, "IBR_SCORE1", expression1, "PYTHON_9.3", codeblock)
   expression2 = "score(!IBR_2!)"
   arcpy.CalculateField_management(in_EOs, "IBR_SCORE2", expression2, "PYTHON_9.3", codeblock)
   
   ### For the ConSites, calculate the B-rank and flag if it conflicts with previous B-rank
   printMsg('Adding several fields to ConSites...')
   arcpy.AddField_management(in_ConSites, "IBR_SUM1", "LONG")
   arcpy.AddField_management(in_ConSites, "IBR_SUM2", "LONG")
   arcpy.AddField_management(in_ConSites, "IBR_MAX1", "LONG")
   arcpy.AddField_management(in_ConSites, "IBR_MAX2", "LONG")
   arcpy.AddField_management(in_ConSites, "AUTO_BRANK_1A", "TEXT", 2)
   arcpy.AddField_management(in_ConSites, "FLAG_BRANK_1A", "LONG")
   arcpy.AddField_management(in_ConSites, "AUTO_BRANK_1B", "TEXT", 2)
   arcpy.AddField_management(in_ConSites, "FLAG_BRANK_1B", "LONG")
   arcpy.AddField_management(in_ConSites, "AUTO_BRANK_2A", "TEXT", 2)
   arcpy.AddField_management(in_ConSites, "FLAG_BRANK_2A", "LONG")
   arcpy.AddField_management(in_ConSites, "AUTO_BRANK_2B", "TEXT", 2)
   arcpy.AddField_management(in_ConSites, "FLAG_BRANK_2B", "LONG")

   arcpy.MakeFeatureLayer_management (in_EOs, "eo_lyr")
   
   # Calculate B-rank scores 
   printMsg('Calculating B-rank sums and maximums in loop...')
   failList = []
   with arcpy.da.UpdateCursor (in_ConSites, ["SHAPE@", "SITEID", "IBR_SUM1", "IBR_SUM2", "IBR_MAX1", "IBR_MAX2"]) as cursor:
      for row in cursor:
         myShp = row[0]
         siteID = row[1]
         arcpy.SelectLayerByLocation_management ("eo_lyr", "INTERSECT", myShp, "", "NEW_SELECTION")
         c = countSelectedFeatures("eo_lyr")
         if c > 0:
            arr = arcpy.da.TableToNumPyArray ("eo_lyr",["IBR_SCORE1", "IBR_SCORE2"], skip_nulls=True)
            
            row[2] = arr["IBR_SCORE1"].sum() 
            row[3] = arr["IBR_SCORE2"].sum() 
            row[4] = arr["IBR_SCORE1"].max() 
            row[5] = arr["IBR_SCORE2"].max() 
            cursor.updateRow(row)
            printMsg("Site %s: Completed"%siteID)
         else:
            printMsg("Site %s: Failed"%siteID)
            failList.append(siteID)
         
   # Determine B-rank based on the sum of IBRs
   printMsg('Calculating site B-ranks from sums and maximums of individual B-ranks...')
   codeblockA = '''def brank(val):
      if val == None:
         return None
      elif val < 4:
         return "B5"
      elif val < 16:
         return "B4"
      elif val < 64:
         return "B3"
      elif val < 256:
         return "B2"
      else:
         return "B1"
      '''
   
   codeblockB = '''def brank(sumRank, max):
      if max == None:
         return None
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
   
   expression1A = "brank(!IBR_SUM1!)"
   arcpy.CalculateField_management(in_ConSites, "AUTO_BRANK_1A", expression1A, "PYTHON_9.3", codeblockA)
   expression2A = "brank(!IBR_SUM2!)"
   arcpy.CalculateField_management(in_ConSites, "AUTO_BRANK_2A", expression2A, "PYTHON_9.3", codeblockA)
   
   expression1B = "brank(!AUTO_BRANK_1A!,!IBR_MAX1!)"
   arcpy.CalculateField_management(in_ConSites, "AUTO_BRANK_1B", expression1B, "PYTHON_9.3", codeblockB)
   expression2B = "brank(!AUTO_BRANK_2A!,!IBR_MAX2!)"
   arcpy.CalculateField_management(in_ConSites, "AUTO_BRANK_2B", expression2B, "PYTHON_9.3", codeblockB)
   
   printMsg('Calculating flag status...')
   codeblock = '''def flag(brank, auto_brank):
      if auto_brank == None:
         return None
      elif brank == auto_brank:
         return 0
      else:
         return 1
   '''
   expression1A = "flag(!BRANK!, !AUTO_BRANK_1A!)"
   arcpy.CalculateField_management(in_ConSites, "FLAG_BRANK_1A", expression1A, "PYTHON_9.3", codeblock)
   expression1B = "flag(!BRANK!, !AUTO_BRANK_1B!)"
   arcpy.CalculateField_management(in_ConSites, "FLAG_BRANK_1B", expression1B, "PYTHON_9.3", codeblock)
   expression2A = "flag(!BRANK!, !AUTO_BRANK_2A!)"
   arcpy.CalculateField_management(in_ConSites, "FLAG_BRANK_2A", expression2A, "PYTHON_9.3", codeblock)
   expression2B = "flag(!BRANK!, !AUTO_BRANK_2B!)"
   arcpy.CalculateField_management(in_ConSites, "FLAG_BRANK_2B", expression2B, "PYTHON_9.3", codeblock)

   if len(failList) > 0:
      printMsg("Processing incomplete for some sites %s"%failList)
   return (in_EOs, in_ConSites)
   printMsg('Finished.')
   
def main():
   # Set up variable(s)
   in_EOs = r'C:\Users\xch43889\Documents\Working\EssentialConSites\ECS_Outputs_20190621.gdb\attrib_EOs_prioritized'
   in_ConSites = r'C:\Users\xch43889\Documents\Working\EssentialConSites\ECS_Outputs_20190621.gdb\ConSites_prioritized'
   
   # Run function(s)
   getBRANK(in_EOs, in_ConSites)
   
if __name__ == '__main__':
   main()
   
