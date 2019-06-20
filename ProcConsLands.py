# ---------------------------------------------------------------------------
# ProcConsLands.py
# Version:  ArcGIS 10.3 / Python 2.7
# Creation Date: 2019-06-19
# Last Edit: 2019-06-19
# Creator:  Kirsten R. Hazler
# ---------------------------------------------------------------------------

# Import modules and functions
import Helper
from Helper import *

arcpy.env.overwriteOutput = True

def bmiFlatten(inConsLands, outConsLands, scratchGDB = None):
   '''Eliminates overlaps in the Conservation Lands feature class. The BMI field is used for consolidation; better BMI ranks (lower numeric values) take precedence over worse ones.
   
   Parameters:
   - inConsLands: Input polygon feature class representing Conservation Lands. Must include a field called 'BMI', with permissible values "1", "2", "3", "4", "5", or "U".
   - outConsLands: Output feature class with "flattened" Conservation Lands and updated BMI field.
   - scratchGDB: Geodatabase for storing scratch products
   '''
   
   arcpy.env.extent = 'MAXOF'
   
   if not scratchGDB:
      # For some reason this function does not work reliably if "in_memory" is used for scratchGDB, at least on my crappy computer, so set to scratchGDB on disk.
      scratchGDB = arcpy.env.scratchGDB
   
   for val in ["U", "5", "4", "3", "2", "1"]:
      # Make a subset feature layer
      lyr = "bmi%s"%val
      where_clause = "BMI = '%s'"%val
      printMsg('Making feature layer...')
      arcpy.MakeFeatureLayer_management(inConsLands, lyr, where_clause)
      
      # Dissolve
      dissFeats = scratchGDB + os.sep + "bmiDiss" + val
      printMsg('Dissolving...')
      arcpy.Dissolve_management(lyr, dissFeats, "BMI", "", "SINGLE_PART")
      
      # Update
      if val == "U":
         printMsg('Setting initial features to be updated...')
         inFeats = dissFeats
      else:
         printMsg('Updating with bmi %s...'%val)
         printMsg('input features: %s'%inFeats)
         printMsg('update features: %s'%dissFeats)
         if val == "1":
            updatedFeats = outConsLands
         else:
            updatedFeats = scratchGDB + os.sep + "upd_bmi%s"%val
         arcpy.Update_analysis(inFeats, dissFeats, updatedFeats)
         inFeats = updatedFeats
   return outConsLands