# ----------------------------------------------------------------------------------------
# CreatePrepInputs.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2020-06-03
# Last Edit: 2020-06-03
# Creator:  Kirsten R. Hazler

# Summary:
# Suite of functions for preparing data needed for site delineation and/or prioritization
# ----------------------------------------------------------------------------------------

# Import modules
import Helper
from Helper import *
import re # support for regular expressions

def ExtractBiotics(BioticsPF, BioticsCS, outGDB):
   '''Extracts data from Biotics5 query layers for Procedural Features and Conservation Sites and saves to a file geodatabase.
   Note: this tool must be run from within a map document containing the relevant query layers.'''
   # Local variables:
   ts = datetime.now().strftime("%Y%m%d_%H%M%S") # timestamp
   
   # Inform user
   printMsg('This process can only be run in the foreground, and takes a few minutes...')

   # Process: Copy Features (ConSites)
   printMsg('Copying ConSites')
   outCS = outGDB + os.sep + 'ConSites_' + ts
   arcpy.CopyFeatures_management(BioticsCS, outCS)
   printMsg('Conservation Sites successfully exported to %s' %outCS)

   # Process: Copy Features (ProcFeats)
   printMsg('Copying Procedural Features')
   unprjPF = r'in_memory\unprjProcFeats'
   arcpy.CopyFeatures_management(BioticsPF, unprjPF)
   
   # Process: Project
   printMsg('Projecting ProcFeats features')
   outPF = outGDB + os.sep + 'ProcFeats_' + ts
   outCoordSyst = "PROJCS['NAD_1983_Virginia_Lambert',GEOGCS['GCS_North_American_1983',DATUM['D_North_American_1983',SPHEROID['GRS_1980',6378137.0,298.257222101]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Lambert_Conformal_Conic'],PARAMETER['False_Easting',0.0],PARAMETER['False_Northing',0.0],PARAMETER['Central_Meridian',-79.5],PARAMETER['Standard_Parallel_1',37.0],PARAMETER['Standard_Parallel_2',39.5],PARAMETER['Latitude_Of_Origin',36.0],UNIT['Meter',1.0]]"
   transformMethod = "WGS_1984_(ITRF00)_To_NAD_1983"
   inCoordSyst = "PROJCS['WGS_1984_Web_Mercator_Auxiliary_Sphere',GEOGCS['GCS_WGS_1984',DATUM['D_WGS_1984',SPHEROID['WGS_1984',6378137.0,298.257223563]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Mercator_Auxiliary_Sphere'],PARAMETER['False_Easting',0.0],PARAMETER['False_Northing',0.0],PARAMETER['Central_Meridian',0.0],PARAMETER['Standard_Parallel_1',0.0],PARAMETER['Auxiliary_Sphere_Type',0.0],UNIT['Meter',1.0]]"
   arcpy.Project_management(unprjPF, outPF, outCoordSyst, transformMethod, inCoordSyst, "PRESERVE_SHAPE", "")
   printMsg('Procedural Features successfully exported to %s' %outPF)

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
   
### Functions for processing National Wetlands Inventory data. 
def TabParseNWI(inNWI, outTab):
   '''Given a National Wetlands Inventory (NWI) feature class, creates a table containing one record for each unique code in the ATTRIBUTE field. The codes in the ATTRIBUTE field are then parsed into easily comprehensible fields, to facilitate processing and mapping. This may be obsolete now that NWI is providing parsed data. (Adapted from a Model-Builder tool and a script tool.) 

   The following new fields are created, based on the value in the ATTRIBUTE field:
   - Syst: contains the System name; this is tier 1 in the NWI hierarchy
   - Subsyst: contains the Subsystem name; this is tier 2 in the NWI hierarchy
   - Cls1: contains the primary (in some cases the only) Class name; this is tier 3 in the NWI hierarchy
   - Subcls1: contains the primary (in some cases the only) Subclass name; this is tier 4 in the NWI hierarchy
   - Cls2: contains the secondary Class name for mixed NWI types
   - Subcls2: contains the secondary Subclass name for mixed NWI types
   - Tidal: contains the tidal status portion of the water regime
   - WtrReg: contains the flood frequency portion of the water regime
   - Mods: contains any additional type modifiers
   - Exclude: contains the value 'X' to flag features to be excluded from rule assignment. Features are excluded if the Mods field codes for any of the following modifiers: Farmed' (f), 'Artificial' (r), 'Spoil' (s), or 'Excavated' (x)

   The output table can be joined back to the NWI polygons using the ATTRIBUTE field as the key.
   
   Parameters:
   - inNWI: Input NWI polygon feature class
   - outTab: Output table containing one record for each unique code in the ATTRIBUTE field
   '''
   
   # Generate the initial table containing one record for each ATTRIBUTE value
   printMsg('Generating table with unique NWI codes...')
   arcpy.Statistics_analysis(inNWI, outTab, "ACRES SUM", "ATTRIBUTE;WETLAND_TYPE")

   # Create new fields to hold relevant attributes
   printMsg('Adding and initializing NWI attribute fields...')
   FldList = [('Syst', 10), 
              ('Subsyst', 25), 
              ('Cls1', 25), 
              ('Subcls1', 50),
              ('Cls2', 25),
              ('Subcls2', 50),
              ('Tidal', 20), 
              ('WtrReg', 50), 
              ('Mods', 5), 
              ('Exclude', 1)]
   flds = ["ATTRIBUTE"] # initializes master field list for later use
   for Fld in FldList:
      FldName = Fld[0]
      FldLen = Fld[1]
      flds.append(FldName)
      arcpy.AddField_management (outTab, FldName, 'TEXT', '', '', FldLen, '', 'NULLABLE', '', '')
   
   printMsg('Setting up some regex patterns and code dictionaries...')
   # Set up some patterns to match
   mix_mu = re.compile(r'/([1-7])?(RB|UB|AB|RS|US|EM|ML|SS|FO|RF|SB)?([1-7])?')
   # pattern for mixed map units
   full_pat =  re.compile(r'^(M|E|R|L|P)([1-5])?(RB|UB|AB|RS|US|EM|ML|SS|FO|RF|SB)?([1-7])?([A-V])?(.*)$') 
   # full pattern after removing secondary type
   ex_pat = re.compile(r'(f|r|s|x)', re.IGNORECASE)
   # pattern for final modifiers warranting exclusion from natural systems
   
   ### Set up a bunch of dictionaries, using the NWI code diagram for reference.
   # https://www.fws.gov/wetlands/documents/NWI_Wetlands_and_Deepwater_Map_Code_Diagram.pdf 
   # This code section reviewed/updated against diagram published in February 2019.
   
   # Set up subsystem dictionaries for each system
   # Lacustrine
   dLac = {'1':'Limnetic', '2':'Littoral'}
   # Marine and Estuarine
   dMarEst = {'1':'Subtidal', '2':'Intertidal'}
   # Riverine
   dRiv = {'1':'Tidal', 
           '2':'Lower Perennial',
           '3':'Upper Perennial',
           '4':'Intermittent'}
   # For dRiv, note that 5: Unknown Perennial is no longer a valid code and has been removed from the dictionary
           
   # Set up system dictionary matching each system with its subsystem dictionary
   # Note that Palustrine System has no Subsystems, thus no subsystem dictionary
   dSyst = {'M': ('Marine', dMarEst),
            'E': ('Estuarine', dMarEst),
            'R': ('Riverine', dRiv),
            'L': ('Lacustrine', dLac),
            'P': ('Palustrine', '')}
            
   # Set up subclass dictionaries for each class
   # Rock Bottom
   dRB = {'1': 'Bedrock',
          '2': 'Rubble'}
   # Unconsolidated Bottom
   dUB = {'1': 'Cobble-Gravel',
          '2': 'Sand',
          '3': 'Mud',
          '4': 'Organic'}
   # Aquatic Bed
   dAB = {'1': 'Algal',
          '2': 'Aquatic Moss',
          '3': 'Rooted Vascular',
          '4': 'Floating Vascular'}
   # Reef
   dRF = {'1': 'Coral',
          '2': 'Mollusk',
          '3': 'Worm'}
   # Rocky Shore
   dRS = {'1': 'Bedrock',
          '2': 'Rubble'}
   # Unconsolidated Shore
   dUS = {'1': 'Cobble-Gravel',
          '2': 'Sand',
          '3': 'Mud',
          '4': 'Organic',
          '5': 'Vegetated'}
   # Streambed
   dSB = {'1': 'Bedrock',
          '2': 'Rubble',
          '3': 'Cobble-Gravel',
          '4': 'Sand',
          '5': 'Mud',
          '6': 'Organic',
          '7': 'Vegetated'}
   # Emergent
   dEM = {'1': 'Persistent',
          '2': 'Non-persistent',
          '5': 'Phragmites australis'}
   # Woody (for Scrub-Shrub and Forested classes)
   dWd = {'1': 'Broad-leaved Deciduous',
          '2': 'Needle-leaved Deciduous',
          '3': 'Broad-leaved Evergreen',
          '4': 'Needle-leaved Evergreen',
          '5': 'Dead',
          '6': 'Deciduous',
          '7': 'Evergreen'}         
   
   # Set up class dictionary matching each class with its subclass dictionary
   dCls = {'RB': ('Rock Bottom', dRB),
           'UB': ('Unconsolidated Bottom', dUB),
           'AB': ('Aquatic Bed', dAB),
           'RF': ('Reef', dRF),
           'RS': ('Rocky Shore', dRS),
           'US': ('Unconsolidated Shore', dUS),
           'SB': ('Streambed', dSB),
           'EM': ('Emergent', dEM),
           'SS': ('Scrub-Shrub', dWd), 
           'FO': ('Forested', dWd)}
           
   # Set up water regime dictionary
   # Note that previously, there was no D or Q code; these have been added. The descriptors of some other codes have changed.
   dWtr = {'A': ('Nontidal', 'Temporarily Flooded'),
           'B': ('Nontidal', 'Seasonally Saturated'),
           'C': ('Nontidal', 'Seasonally Flooded'), 
           'D': ('Nontidal', 'Continuously Saturated'),
           'E': ('Nontidal', 'Seasonally Flooded / Saturated'),
           'F': ('Nontidal', 'Semipermanently Flooded'),
           'G': ('Nontidal', 'Intermittently Exposed'),
           'H': ('Nontidal', 'Permanently Flooded'),
           'J': ('Nontidal', 'Intermittently Flooded'),
           'K': ('Nontidal', 'Artificially Flooded'),
           'L': ('Saltwater Tidal', 'Subtidal'),
           'M': ('Saltwater Tidal', 'Irregularly Exposed'),
           'N': ('Saltwater Tidal', 'Regularly Flooded'),
           'P': ('Saltwater Tidal', 'Irregularly Flooded'),
           'Q': ('Freshwater Tidal', 'Regularly Flooded-Fresh Tidal'),
           'R': ('Freshwater Tidal', 'Seasonally Flooded-Fresh Tidal'),
           'S': ('Freshwater Tidal', 'Temporarily Flooded-Fresh Tidal'),
           'T': ('Freshwater Tidal', 'Semipermanently Flooded-Fresh Tidal'),
           'V': ('Freshwater Tidal', 'Permanently Flooded-Fresh Tidal')}
   
   # Loop through the records and assign field attributes based on NWI codes
   printMsg('Looping through the NWI codes to parse...')
   printMsg('Fields: %s'%flds)
   with arcpy.da.UpdateCursor(outTab, flds) as cursor:
      for row in cursor:
         nwiCode = row[0] 
         printMsg('Code: %s' % nwiCode)
         
         # First, for mixed map units, extract the secondary code portion from the code string
         m = mix_mu.search(nwiCode)
         if m:
            extract = m.group()
            nwiCode = nwiCode.replace(extract, '')
         
         # Parse out the primary sub-codes
         s = full_pat.search(nwiCode)
         h1 = s.group(1) # System code
         h2 = s.group(2) # Subsystem code
         h3 = s.group(3) # Class code
         h4 = s.group(4) # Subclass code
         mod1 = s.group(5) # Water Regime code
         row[9] = s.group(6) # Additional modifier code(s) go directly into Mods field
         if s.group(6):
            x = ex_pat.search(s.group(6))
            if x:
               row[10] = 'X' # Flags record for exclusion from natural(ish) systems
         
         # Assign attributes to primary fields by extracting from dictionaries
         row[1] = (dSyst[h1])[0] # Syst field
         try:
            row[2] = ((dSyst[h1])[1])[h2] # Subsyst field
         except:
            row[2] = None 
         try:
            row[3] = (dCls[h3])[0] # Cls1 field
         except:
            row[3] = None
         try:
            row[4] = ((dCls[h3])[1])[h4] # Subcls1 field
         except:
            row[4] = None
         try:
            row[7] = (dWtr[mod1])[0] # Tidal field
         except:
            row[7] = None
         try:
            row[8] = (dWtr[mod1])[1] # WtrReg field
         except:
            row[8] = None

         # If applicable, assign attributes to secondary fields by extracting from dictionaries
         if m:
            if m.group(1):
               h4_2 = m.group(1) # Secondary subclass code
            elif m.group(3):
               h4_2 = m.group(3)
            else:
               h4_2 = None
            if m.group(2):
               h3_2 = m.group(2) # Secondary class code
            else:
               h3_2 = None
            try:
               row[5] = (dCls[h3_2])[0] # Cls2 field
            except:
               row[5] = None
            try:
               row[6] = ((dCls[h3_2])[1])[h4_2] # Subcls2 field; requires secondary class for definition of subclass
            except:
               try:
                  row[6] = ((dCls[h3])[1])[h4_2] # If no secondary class, use primary class for subclass definition
               except:
                  row[6] = None   
            
         cursor.updateRow(row)
   printMsg('Mission accomplished.')
   return outTab
   
def SbbToNWI(inTab):
   '''Assigns Site Building Blocks (SBB) rules to National Wetland Inventory (NWI) codes. This function is specific to the Virginia Natural Heritage Program. (Adapted from a script tool.)
   
   NOTES:
   - SBB rules 5, 6, 7, and 9 are included in this process. 
   - This function creates a binary column for each rule. If the rule applies to a record, the value in the corresponding column is set to 1, otherwise the value is 0. 
   - Each record can have one or more rules assigned, or no rules at all.

   IMPORTANT: For this function to work correctly, the input table must have specific fields. To ensure that this is true, the table should be generated by the preceding TabParseNWI function.
   
   Parameters:
   - inTab: Input table to be processed. (This table will be modified by the addition of SBB rule fields.)
   '''
   # Create new fields to hold SBB rules, and set initial values to 0
   printMsg('Adding and initializing SBB rule fields...')
   RuleList = ['Rule5', 'Rule6', 'Rule7', 'Rule9']
   for Rule in RuleList:
      arcpy.AddField_management (inTab, Rule, 'SHORT')
      arcpy.CalculateField_management (inTab, Rule, 0, "PYTHON")
      
   # Set up a full list of the relevant fields   
   flds = ['ATTRIBUTE', 'WETLAND_TYPE', 'Syst', 'Subsyst', 'Cls1', 'Subcls1', 
           'Cls2', 'Subcls2', 'Tidal', 'WtrReg', 'Exclude',
           'Rule5', 'Rule6', 'Rule7', 'Rule9']
           
   # Loop through the records and assign SBB rules
   printMsg('Examining NWI codes and assigning SBB rules...')
   with arcpy.da.UpdateCursor(inTab, flds) as cursor:
      for row in cursor:
         # Get the values from relevant fields
         nwiCode = row[0]
         wetType = row[1]
         syst = row[2]
         subsyst = row[3]
         cls1 = row[4]
         subcls1 = row[5]
         cls2 = row[6]
         subcls2 = row[7]
         tidal = row[8]
         wtrReg = row[9]
         exclude = row[10]
         
         # Update the values of SBB rule fields based on various criteria
         if exclude == 'X':
            continue # Skip all the rest and go on to process the next record
         if tidal in ('Saltwater Tidal', 'Freshwater Tidal'):
            if syst == 'Marine' or syst == None:
               pass # No rule assigned
            else:
               if (cls1 in ('Emergent', 'Scrub-Shrub', 'Forested') or
                   cls2 in ('Emergent', 'Scrub-Shrub', 'Forested') or
                   cls1 == 'Aquatic Bed' and subcls1 == None or
                   cls2 == 'Aquatic Bed' and subcls2 == None or
                   subcls1 in ('Rooted Vascular', 'Floating Vascular', 'Vegetated') or
                   subcls2 in ('Rooted Vascular', 'Floating Vascular', 'Vegetated')):
                  row[14] = 1 # Assign Rule 9
               else:
                  pass # No rule assigned
         elif tidal == 'Nontidal':
            if syst == 'Lacustrine':
               row[12] = 1 # Assign Rule 6
               row[13] = 1 # Assign Rule 7
            elif syst == 'Palustrine':
               if (cls1 in ('Emergent', 'Scrub-Shrub', 'Forested') or
                   cls2 in ('Emergent', 'Scrub-Shrub', 'Forested')): 
                  if (cls1 == 'Emergent' or cls2 == 'Emergent'):
                     row[11] = 1 # Assign Rule 5
                     row[12] = 1 # Assign Rule 6
                     row[13] = 1 # Assign Rule 7
                  else:
                     row[11] = 1 # Assign Rule 5
               else:
                  row[12] = 1 # Assign Rule 6
                  row[13] = 1 # Assign Rule 7
            else:
               pass # No rule assigned
         else:
            pass # No rule assigned
         
         cursor.updateRow(row)
   printMsg('Mission accomplished.')
   return 
   
def SubsetNWI(inNWI, inTab, inGDB):
   '''Creates subsets of National Wetlands Inventory (NWI) polygons specific to Site Building Blocks (SBB) rules. This function is specific to the Virginia Natural Heritage Program. (Adapted from a Model-Builder tool.)
   
   Each subset contains only the polygons applicable to each rule, and adjacent polygons have boundaries dissolved. Three subsets are created:
   - Rule 5 polygons
   - Rule 6/7 polygons
   - Rule 9 polygons

   IMPORTANT: For this function to work correctly, the input table must have specific fields. To ensure that this is true, the table should be generated by the preceding TabParseNWI and SbbToNWI functions.
   
   Parameters:
   - inNWI: Polygon feature class representing wetlands, from NWI. 
   - inTab: Input table containing relevant attributes for subsetting. Must be able to link to inNWI via the ATTRIBUTE field.
   - inGDB: Geodatabase for storing outputs
   '''
   
   # Set up some variables
   nwi_rule5 = inGDB + os.sep + 'VA_Wetlands_Rule5'
   nwi_rule67 = inGDB + os.sep + 'VA_Wetlands_Rule67'
   nwi_rule9 = inGDB + os.sep + 'VA_Wetlands_Rule9'
   tabName = os.path.basename(inTab)

   # Create join
   printMsg('Joining tabular data to NWI polygons...')
   arcpy.MakeFeatureLayer_management (inNWI, "lyr_NWI")
   arcpy.AddJoin_management ("lyr_NWI", "ATTRIBUTE", inTab, "ATTRIBUTE", "KEEP_ALL")
   
   # Select and dissolve subsets
   printMsg('Selecting and dissolving Rule 5 features...')
   fldName = tabName + '.Rule5'
   qry = "%s = 1"%fldName
   arcpy.SelectLayerByAttribute_management ("lyr_NWI", "NEW_SELECTION", qry)
   arcpy.Dissolve_management("lyr_NWI", nwi_rule5, "", "", "SINGLE_PART", "DISSOLVE_LINES")
   
   printMsg('Selecting and dissolving Rule 6-7 features...')
   fldName1 = tabName + '.Rule6'
   fldName2 = tabName + '.Rule7'
   qry = "%s = 1 OR %s = 1"%(fldName1, fldName2)
   arcpy.SelectLayerByAttribute_management ("lyr_NWI", "NEW_SELECTION", qry)
   arcpy.Dissolve_management("lyr_NWI", nwi_rule67, "", "", "SINGLE_PART", "DISSOLVE_LINES")
   
   printMsg('Selecting and dissolving Rule 9 features...')
   fldName = tabName + '.Rule9'
   qry = "%s = 1"%fldName
   arcpy.SelectLayerByAttribute_management ("lyr_NWI", "NEW_SELECTION", qry)
   arcpy.Dissolve_management("lyr_NWI", nwi_rule9, "", "", "SINGLE_PART", "DISSOLVE_LINES")
   
   printMsg('Mission accomplished.')
   return (nwi_rule5, nwi_rule67, nwi_rule9)