# ----------------------------------------------------------------------------------------
# CreateConSites.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016-02-25
# Last Edit: 2020-06-25
# Creator:  Kirsten R. Hazler

# Summary:
# Suite of functions to delineate and review Natural Heritage Conservation Sites.
# Includes functionality to produce:
# - Terrestrial Conservation Sites (TCS)
# - Anthopogenic Habitat Zones (AHZ)
# - Stream Conservation Sites (SCS)

# Dependencies:
# Functions for creating SCS will not work if the hydro network is not set up properly! The network geodatabase VA_HydroNet.gdb has been set up manually, not programmatically. The Network Analyst extension is required for some SCS functions, which will fail if the license is unavailable.
# ----------------------------------------------------------------------------------------

# Import function libraries and settings
import Helper
from Helper import *
from arcpy.sa import *
import re # support for regular expressions


### Functions for input data preparation and output data review ###
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

def ParseSiteTypes(in_ProcFeats, in_ConSites, out_GDB):
   '''Splits input Procedural Features and Conservation Sites into 3 feature classes each, one for each of site types subject to ConSite delineation and prioritization processes.
   Parameters:
   - in_ProcFeats: input feature class representing Procedural Features
   - in_ConSites: input feature class representing Conservation Sites
   - out_GDB: geodatabase in which outputs will be stored   
   '''
   
   # Define some queries
   qry_pfTCS = "RULE NOT IN ('SCU','MACS','KCS','AHZ')"
   qry_pfKCS = "RULE = 'KCS'"
   qry_pfSCU = "RULE = 'SCU'"
   qry_pfAHZ = "RULE = 'AHZ'"
   qry_csTCS = "SITE_TYPE = 'Conservation Site'"
   qry_csKCS = "SITE_TYPE = 'Cave Site'"
   qry_csSCU = "SITE_TYPE = 'SCU'"
   qry_csAHZ = "SITE_TYPE = 'Anthropogenic Habitat Zone'"
   
   
   # Define some outputs
   pfTCS = out_GDB + os.sep + 'pfTerrestrial'
   pfKCS = out_GDB + os.sep + 'pfKarst'
   pfSCU = out_GDB + os.sep + 'pfStream'
   pfAHZ = out_GDB + os.sep + 'pfAnthro'
   csTCS = out_GDB + os.sep + 'csTerrestrial'
   csKCS = out_GDB + os.sep + 'csKarst'
   csSCU = out_GDB + os.sep + 'csStream'
   csAHZ = out_GDB + os.sep + 'csAnthro'
   
   # Make a list of input/query/output triplets
   procList = [[in_ProcFeats, qry_pfTCS, pfTCS],
               [in_ProcFeats, qry_pfKCS, pfKCS],
               [in_ProcFeats, qry_pfSCU, pfSCU],
               [in_ProcFeats, qry_pfAHZ, pfAHZ],
               [in_ConSites, qry_csTCS, csTCS],
               [in_ConSites, qry_csKCS, csKCS],
               [in_ConSites, qry_csSCU, csSCU],
               [in_ConSites, qry_csAHZ, csAHZ]]
               
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

def prepFlowBuff(in_FlowDist, truncDist, out_Rast, snapRast = None):
   '''Given a continuous raster representing flow distance, creates a binary raster where distances less than or equal to the truncation distance are set to 1, and everything else is set to null.
   
   Parameters:
   - in_FlowDist: Input raster representing flow distance 
   - truncDist: The distance (in raster map units) used as the truncation threshold
   - out_Rast: Output raster in which flow distances less than or equal to the truncation distance are set to 1
   - snapRast (optional): Raster used to determine coordinate system and alignment of output. If a snap raster is specified, the output will be reprojected to match.
   '''
   
   # Check out Spatial Analyst extention
   arcpy.CheckOutExtension("Spatial")
   
   # Cast string as raster
   in_FlowDist = Raster(in_FlowDist)
   
   # Convert nulls to zero
   printMsg("Converting nulls to zero...")
   FlowDist = Con(IsNull(in_FlowDist),0,in_FlowDist)
   
   # Recode raster
   printMsg("Recoding raster...")
   where_clause = "VALUE > %s" %truncDist
   buffRast = SetNull (FlowDist, 1, where_clause)
   
   # Reproject or save directly
   if snapRast == None:
      printMsg("Saving raster...")
      buffRast.save(out_Rast)
   else:
      ProjectToMatch_ras(buffRast, snapRast, out_Rast, "NEAREST")
   
   # Check in Spatial Analyst extention
   arcpy.CheckInExtension("Spatial")
   
   printMsg("Mission complete.")
   
   return out_Rast
   
def ReviewConSites(auto_CS, orig_CS, cutVal, out_Sites, fld_SiteID = "SITEID", scratchGDB = arcpy.env.scratchWorkspace):
   '''Submits new (typically automated) Conservation Site features to a Quality Control procedure, comparing new to existing (old) shapes  from the previous production cycle. It determines which of the following applies to the new site:
- N:  Site is new, not corresponding to any old site.
- I:  Site is identical to an old site.
- M:  Site is a merger of two or more old sites.
- S:  Site is one of several that split off from an old site.
- C:  Site is a combination of merger(s) and split(s)
- B:  Boundary change only.  Site corresponds directly to an old site, but the boundary has changed to some extent.

For the last group of sites (B), determines how much the boundary has changed.  A "PercDiff" field contains the percentage difference in area between old and new shapes.  The area that differs is determined by ArcGIS's Symmetrical Difference tool.  The user specifies a threshold beyond which the difference is deemed "significant".  (I recommend 10% change as the cutoff).

Finally, adds additional fields for QC purposes, and flags records that should be examined by a human (all N, M, and S sites, plus and B sites with change greater than the threshold).

In the output feature class, the output geometry is identical to the input new Conservation Sites features, but attributes have been added for QC purposes.  The addeded attributes are as follows:
- ModType:  Text field indicating how the site has been modified, relative to existing old sites.  Values are "N". "M", "S", "I", or "B" as described above.
- PercDiff:  Numeric field indicating the percent difference between old and new boundaries, as described above.  Applies only to sites where ModType = "B".
- AssignID:  Long integer field containing the old SITEID associated with the new site.  This field is automatically populated only for sites where ModType is "B" or "I".  For other sites, the ID should be manually assigned during site review.  Attributes associated with this ID may be transferred, in whole or in part, from the old site to the new site.  
- Flag:  Short integer field indicating whether the new site needs to be examined by a human (1) or not (0).  All sites where ModType is "N", "M", or "S" are flagged automatically.  Sites where ModType = "B" are flagged if the value in the PercDiff field is greater than the user-specified threshold.
- Comment:  Text field to be used by site reviewers to enter comments.  Nothing is entered automatically.

User inputs:
- auto_CS: new (typically automated) Conservation Site feature class
- orig_CS: old Conservation Site feature class for comparison (the one currently in Biotics)
- cutVal: a cutoff percentage that will be used to flag features that represent significant boundary growth or reduction(e.g., 10%)
- out_Sites: output new Conservation Sites feature class with QC information
- fld_SiteID: the unique site ID field in the old CS feature class
- scratchGDB: scratch geodatabase for intermediate products'''

   # Determine how many old sites are overlapped by each automated site.  Automated sites provide the output geometry
   printMsg("Performing first spatial join...")
   Join1 = scratchGDB + os.sep + "Join1"
   fldmap = "Shape_Length \"Shape_Length\" false true true 8 Double 0 0 ,First,#,auto_CS,Shape_Length,-1,-1;Shape_Area \"Shape_Area\" false true true 8 Double 0 0 ,First,#,auto_CS,Shape_Area,-1,-1"
   arcpy.SpatialJoin_analysis(auto_CS, orig_CS, Join1, "JOIN_ONE_TO_ONE", "KEEP_ALL", fldmap, "INTERSECT", "", "")

   # Get the new sites.
   # These are automated sites with no corresponding old site
   printMsg("Separating out brand new sites...")
   NewSites = scratchGDB + os.sep + "NewSites"
   arcpy.Select_analysis(Join1, NewSites, "Join_Count = 0")

   # Get the single and split sites.
   # These are sites that overlap exactly one old site each. This may be a one-to-one correspondence or a split.
   printMsg("Separating out sites that may be singles or splits...")
   ssSites = scratchGDB + os.sep + "ssSites"
   arcpy.Select_analysis(Join1, ssSites, "Join_Count = 1")
   arcpy.MakeFeatureLayer_management(ssSites, "ssLyr")

   # Get the merger sites.
   # These are sites overlapping multiple old sites. Some may be pure merges, others combo merge/split sites.
   printMsg("Separating out merged sites...")
   mSites = scratchGDB + os.sep + "mSites"
   arcpy.Select_analysis(Join1, mSites, "Join_Count > 1")
   arcpy.MakeFeatureLayer_management(mSites, "mergeLyr")

   # Process: Remove extraneous fields as needed
   for tbl in [NewSites, ssSites, mSites]:
      for fld in ["Join_Count", "TARGET_FID"]:
         try:
            arcpy.DeleteField_management (tbl, fld)
         except:
            pass

   # Determine how many automated sites are overlapped by each old site.  Old sites provide the output geometry
   printMsg("Performing second spatial join...")
   Join2 = scratchGDB + os.sep + "Join2"
   arcpy.SpatialJoin_analysis(orig_CS, auto_CS, Join2, "JOIN_ONE_TO_ONE", "KEEP_COMMON", fldmap, "INTERSECT", "", "")
   arcpy.JoinField_management (Join2, "TARGET_FID", orig_CS, "OBJECTID", "%s" %fld_SiteID)

   # Make separate layers for old sites that were or were not split
   arcpy.MakeFeatureLayer_management(Join2, "NoSplitLyr", "Join_Count = 1")
   arcpy.MakeFeatureLayer_management(Join2, "SplitLyr", "Join_Count > 1")

   # Get the single sites (= no splits, no merges; one-to-one relationship with old sites)
   printMsg("Separating out single sites...")
   arcpy.SelectLayerByLocation_management("ssLyr", "INTERSECT", "NoSplitLyr", "", "NEW_SELECTION", "NOT_INVERT")
   SingleSites = scratchGDB + os.sep + "SingleSites"
   arcpy.CopyFeatures_management("ssLyr", SingleSites, "", "0", "0", "0")

   # Get the old site IDs to attach to SingleSites.  SingleSites provide the output geometry
   printMsg("Performing third spatial join...")
   Join3 = scratchGDB + os.sep + "Join3"
   arcpy.SpatialJoin_analysis(SingleSites, orig_CS, Join3, "JOIN_ONE_TO_ONE", "KEEP_COMMON", "", "INTERSECT", "", "")
   arcpy.JoinField_management (SingleSites, "OBJECTID", Join3, "TARGET_FID", "%s" %fld_SiteID) 

   # Save out the single sites that are identical to old sites
   arcpy.MakeFeatureLayer_management(SingleSites, "SingleLyr")
   printMsg("Separating out single sites that are identical to old sites...")
   arcpy.SelectLayerByLocation_management("SingleLyr", "ARE_IDENTICAL_TO", orig_CS, "", "NEW_SELECTION", "NOT_INVERT")
   IdentSites = scratchGDB + os.sep + "IdentSites"
   arcpy.CopyFeatures_management("SingleLyr", IdentSites, "", "0", "0", "0")

   # Save out the single sites that are NOT identical to old sites
   printMsg("Separating out single sites where boundaries have changed...")
   arcpy.SelectLayerByAttribute_management("SingleLyr", "SWITCH_SELECTION", "")
   BndChgSites = scratchGDB + os.sep + "BndChgSites"
   arcpy.CopyFeatures_management("SingleLyr", BndChgSites, "", "0", "0", "0")
   
   # Save out the split sites
   printMsg("Separating out split sites...")
   arcpy.SelectLayerByAttribute_management("ssLyr", "SWITCH_SELECTION", "")
   SplitSites = scratchGDB + os.sep + "SplitSites"
   arcpy.CopyFeatures_management("ssLyr", SplitSites, "", "0", "0", "0")
   
   # Save out the combo merger sites (those that also involve splits)
   printMsg("Separating out combo merger sites...")
   arcpy.SelectLayerByLocation_management("mergeLyr", "INTERSECT", "SplitLyr", "", "NEW_SELECTION", "NOT_INVERT")
   ComboSites = scratchGDB + os.sep + "ComboSites"
   arcpy.CopyFeatures_management("mergeLyr", ComboSites, "", "0", "0", "0")
   
   # Save out the simple merger sites (no splits)
   printMsg("Separating out simple merger sites...")
   arcpy.SelectLayerByAttribute_management("mergeLyr", "SWITCH_SELECTION", "")
   MergeSites = scratchGDB + os.sep + "MergeSites"
   arcpy.CopyFeatures_management("mergeLyr", MergeSites, "", "0", "0", "0")

   # Process:  Add Fields; Calculate Fields
   printMsg("Calculating fields...")
   for tbl in [(NewSites, "N"), (MergeSites, "M"), (ComboSites, "C"), (SplitSites, "S"), (IdentSites, "I"), (BndChgSites, "B")]: 
      for fld in [("ModType", "TEXT", 1), ("PercDiff", "DOUBLE", ""), ("AssignID", "TEXT", 40), ("Flag", "SHORT", ""), ("Comment", "TEXT", 250)]:
         arcpy.AddField_management (tbl[0], fld[0], fld[1], "", "", fld[2]) 
      arcpy.CalculateField_management (tbl[0], "ModType", '"%s"' %tbl[1], "PYTHON") 
      CodeBlock = """def Flag(ModType):
         if ModType in ("N", "M", "C", "S", "B"):
            flg = 1
         else:
            flg = 0
         return flg"""
      Expression = "Flag(!ModType!)"
      arcpy.CalculateField_management (tbl[0], "Flag", Expression, "PYTHON", CodeBlock) 
      
   for tbl in [IdentSites, BndChgSites]:
      arcpy.CalculateField_management (tbl, "AssignID", "!%s!" %fld_SiteID, "PYTHON") 
      arcpy.DeleteField_management (tbl, "%s" %fld_SiteID) 
      
   # Loop through the individual Boundary Change sites and check for amount of change
   myIndex = 1 # Set a counter index
   printMsg("Examining boundary changes for boundary change only sites...")
   with arcpy.da.UpdateCursor(BndChgSites, ["AssignID", "PercDiff", "Flag"]) as mySites: 
      for site in mySites: 
         try: # put all this in a TRY block so that even if one feature fails, script can proceed to next feature
            # Extract the unique ID from the data record
            myID = site[0]
            printMsg("\nWorking on Site ID %s" %myID)
            
            # Process:  Select (Analysis)
            # Create temporary feature classes including only the current new and old sites
            myWhereClause_AutoSites = '"AssignID" = \'%s\'' %myID
            tmpAutoSite = "in_memory" + os.sep + "tmpAutoSite"
            arcpy.Select_analysis (BndChgSites, tmpAutoSite, myWhereClause_AutoSites)
            tmpOldSite = "in_memory" + os.sep + "tmpOldSite"
            myWhereClause_OldSite = '"%s" = \'%s\'' %(fld_SiteID, myID)
            arcpy.Select_analysis (orig_CS, tmpOldSite, myWhereClause_OldSite)

            # Get the area of the old site
            OldArea = arcpy.SearchCursor(tmpOldSite).next().shape.area

            # Process:  Symmetrical Difference (Analysis)
            # Create features from the portions of the old and new sites that do NOT overlap
            tmpSymDiff = "in_memory" + os.sep + "tmpSymDiff"
            arcpy.SymDiff_analysis (tmpOldSite, tmpAutoSite, tmpSymDiff, "ONLY_FID", "")

            # Process:  Dissolve (Data Management)
            # Dissolve the Symmetrical Difference polygons into a single (multi-part) polygon
            tmpDissolve = "in_memory" + os.sep + "tmpDissolve"
            arcpy.Dissolve_management (tmpSymDiff, tmpDissolve, "", "", "", "")

            # Get the area of the difference shape
            DiffArea = arcpy.SearchCursor(tmpDissolve).next().shape.area

            # Calculate the percent difference from old shape, and set the value in the record
            PercDiff = 100*DiffArea/OldArea
            printMsg("The shapes differ by " + str(PercDiff) + " percent of original site area")
            site[1] = PercDiff

            # If the difference is greater than the cutoff, set the flag value to "Suspect", otherwise "Okay"
            if PercDiff > cutVal:
               printMsg("Shapes are significantly different; flagging record")
               site[2] = 1
            else:
               printMsg("Shapes are similar; unflagging record")
               site[2] = 0

            # Update the data table
            mySites.updateRow(site) 
         
         except:       
            # Add failure message
            printMsg("Failed to fully process feature " + str(myIndex))
            print "Failed to fully process feature " + str(myIndex)

            # Error handling code swiped from "A Python Primer for ArcGIS"
            tb = sys.exc_info()[2]
            tbinfo = traceback.format_tb(tb)[0]
            pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
            msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

            arcpy.AddError(msgs)
            arcpy.AddError(pymsg)
            printMsg(arcpy.GetMessages(1))

            print msgs
            print pymsg
            print printMsg(arcpy.GetMessages(1))

            # Add status message
            printMsg("\nMoving on to the next feature.  Note that the output will be incomplete.")
         
         finally:
            # Increment the index by one, and clear the in_memory workspace before returning to beginning of the loop
            myIndex += 1 
            arcpy.Delete_management("in_memory")

   # Process:  Merge
   printMsg("Merging sites into final feature class...")
   fcList = [NewSites, MergeSites, ComboSites, SplitSites, IdentSites, BndChgSites]
   arcpy.Merge_management (fcList, out_Sites) 
   
   return out_Sites


### Functions for creating Terrestrial Conservation Sites (TCS) and Anthropogenic Habitat Zones (AHZ) ###
def GetEraseFeats (inFeats, selQry, elimDist, outEraseFeats, elimFeats = "", scratchGDB = "in_memory"):
   ''' For ConSite creation: creates exclusion features from input hydro or transportation surface features'''
   # Process: Make Feature Layer (subset of selected features)
   arcpy.MakeFeatureLayer_management(inFeats, "Selected_lyr", selQry)

   # If it's a string, parse elimination distance and get the negative
   if type(elimDist) == str:
      origDist, units, meas = multiMeasure(elimDist, 1)
      negDist, units, negMeas = multiMeasure(elimDist, -1)
   else:
      origDist = elimDist
      meas = elimDist
      negDist = -1*origDist
      negMeas = negDist
   
   # Process: Eliminate narrow features (or portions thereof)
   CoalEraseFeats = scratchGDB + os.sep + 'CoalEraseFeats'
   Coalesce("Selected_lyr", negDist, CoalEraseFeats, scratchGDB)
   
   # Process: Bump features back out to avoid weird pinched shapes
   BumpEraseFeats = scratchGDB + os.sep + 'BumpEraseFeats'
   Coalesce(CoalEraseFeats, elimDist, BumpEraseFeats, scratchGDB)

   if elimFeats == "":
      CleanFeatures(BumpEraseFeats, outEraseFeats)
   else:
      CleanErase(BumpEraseFeats, elimFeats, outEraseFeats)
   
   # Cleanup
   if scratchGDB == "in_memory":
      trashlist = [CoalEraseFeats]
      garbagePickup(trashlist)
   
   return outEraseFeats

def CullEraseFeats (inEraseFeats, in_Feats, fld_SFID, PerCov, outEraseFeats, scratchGDB = "in_memory"):
   '''For ConSite creation: Culls exclusion features containing a significant percentage of any input feature's (PF or SBB) area'''
   # Process:  Add Field (Erase ID) and Calculate
   arcpy.AddField_management (inEraseFeats, "eFID", "LONG")
   arcpy.CalculateField_management (inEraseFeats, "eFID", "!OBJECTID!", "PYTHON")
   
   # Process: Tabulate Intersection
   # This tabulates the percentage of each input feature that is contained within each erase feature
   TabIntersect = scratchGDB + os.sep + os.path.basename(inEraseFeats) + "_TabInter"
   arcpy.TabulateIntersection_analysis(in_Feats, fld_SFID, inEraseFeats, TabIntersect, "eFID", "", "", "HECTARES")
   
   # Process: Summary Statistics
   # This tabulates the maximum percentage of ANY input feature within each erase feature
   TabSum = scratchGDB + os.sep + os.path.basename(inEraseFeats) + "_TabSum"
   arcpy.Statistics_analysis(TabIntersect, TabSum, "PERCENTAGE SUM", fld_SFID)
   
   # Process: Join Field
   # This joins the summed percentage value back to the original input features
   try:
      arcpy.DeleteField_management (in_Feats, "SUM_PERCENTAGE")
   except:
      pass
   arcpy.JoinField_management(in_Feats, fld_SFID, TabSum, fld_SFID, "SUM_PERCENTAGE")
   
   # Process: Select features containing a large enough percentage of erase features
   WhereClause = "SUM_PERCENTAGE >= %s" % PerCov
   selInFeats = scratchGDB + os.sep + 'selInFeats'
   arcpy.Select_analysis(in_Feats, selInFeats, WhereClause)
   
   # Process:  Clean Erase (Use selected input features to chop out areas of exclusion features)
   CleanErase(inEraseFeats, selInFeats, outEraseFeats, scratchGDB)
   
   if scratchGDB == "in_memory":
      # Cleanup
      trashlist = [TabIntersect, TabSum]
      garbagePickup(trashlist)
   
   return outEraseFeats

def CullFrags (inFrags, in_PF, searchDist, outFrags):
   '''For ConSite creation: Culls SBB or ConSite fragments farther than specified search distance from 
   Procedural Features'''
   
   # Process: Near
   arcpy.Near_analysis(inFrags, in_PF, searchDist, "NO_LOCATION", "NO_ANGLE", "PLANAR")

   # Process: Make Feature Layer
   WhereClause = '"NEAR_FID" <> -1'
   arcpy.MakeFeatureLayer_management(inFrags, "Frags_lyr", WhereClause)

   # Process: Clean Features
   CleanFeatures("Frags_lyr", outFrags)
   
   return outFrags

def ExpandSBBselection(inSBB, inPF, fld_SFID, inConSites, SearchDist, outSBB, outPF):
   '''Given an initial selection of Site Building Blocks (SBB) features, selects additional SBB features in the vicinity that should be included in any Conservation Site update. Also selects the Procedural Features (PF) corresponding to selected SBBs. Outputs the selected SBBs and PFs to new feature classes.'''
   # If applicable, clear any selections on the PFs and ConSites inputs
   typePF = (arcpy.Describe(inPF)).dataType
   typeCS = (arcpy.Describe(inConSites)).dataType
   if typePF == 'FeatureLayer':
      arcpy.SelectLayerByAttribute_management (inPF, "CLEAR_SELECTION")
   if typeCS == 'FeatureLayer':
      arcpy.SelectLayerByAttribute_management (inConSites, "CLEAR_SELECTION")
      
   # Make Feature Layers from PFs and ConSites
   arcpy.MakeFeatureLayer_management(inPF, "PF_lyr")   
   arcpy.MakeFeatureLayer_management(inConSites, "Sites_lyr")
      
   # # Process: Select subset of terrestrial ConSites
   # # WhereClause = "TYPE = 'Conservation Site'" 
   # arcpy.SelectLayerByAttribute_management ("Sites_lyr", "NEW_SELECTION", '')

   # Initialize row count variables
   initRowCnt = 0
   finRowCnt = 1

   while initRowCnt < finRowCnt:
      # Keep adding to the SBB selection as long as the counts of selected records keep changing
      # Get count of records in initial SBB selection
      initRowCnt = int(arcpy.GetCount_management(inSBB).getOutput(0))
      
      # Select SBBs within distance of current selection
      arcpy.SelectLayerByLocation_management(inSBB, "WITHIN_A_DISTANCE", inSBB, SearchDist, "ADD_TO_SELECTION", "NOT_INVERT")
      
      # Select ConSites intersecting current SBB selection
      arcpy.SelectLayerByLocation_management("Sites_lyr", "INTERSECT", inSBB, "", "NEW_SELECTION", "NOT_INVERT")
      
      # Select SBBs within current selection of ConSites
      arcpy.SelectLayerByLocation_management(inSBB, "INTERSECT", "Sites_lyr", "", "ADD_TO_SELECTION", "NOT_INVERT")
      
      # Make final selection
      arcpy.SelectLayerByLocation_management(inSBB, "WITHIN_A_DISTANCE", inSBB, SearchDist, "ADD_TO_SELECTION", "NOT_INVERT")
      
      # Get count of records in final SBB selection
      finRowCnt = int(arcpy.GetCount_management(inSBB).getOutput(0))
      
   # Save subset of SBBs and corresponding PFs to output feature classes
   SubsetSBBandPF(inSBB, inPF, "PF", fld_SFID, outSBB, outPF)
   
   featTuple = (outSBB, outPF)
   return featTuple
   
def SubsetSBBandPF(inSBB, inPF, selOption, fld_SFID, outSBB, outPF):
   '''Given input Site Building Blocks (SBB) features, selects the corresponding Procedural Features (PF). Or vice versa, depending on SelOption parameter.  Outputs the selected SBBs and PFs to new feature classes.'''
   if selOption == "PF":
      inSelector = inSBB
      inSelectee = inPF
      outSelector = outSBB
      outSelectee = outPF
   elif selOption == "SBB":
      inSelector = inPF
      inSelectee = inSBB
      outSelector = outPF
      outSelectee = outSBB
   else:
      printErr('Invalid selection option')
     
   # If applicable, clear any selections on the Selectee input
   typeSelectee = (arcpy.Describe(inSelectee)).dataType
   if typeSelectee == 'FeatureLayer':
      arcpy.SelectLayerByAttribute_management (inSelectee, "CLEAR_SELECTION")
      
   # Copy the Selector features to the output feature class
   arcpy.CopyFeatures_management (inSelector, outSelector) 

   # Make Feature Layer from Selectee features
   arcpy.MakeFeatureLayer_management(inSelectee, "Selectee_lyr") 

   # Get the Selectees associated with the Selectors, keeping only common records
   arcpy.AddJoin_management ("Selectee_lyr", fld_SFID, outSelector, fld_SFID, "KEEP_COMMON")

   # Select all Selectees that were joined
   arcpy.SelectLayerByAttribute_management ("Selectee_lyr", "NEW_SELECTION")

   # Remove the join
   arcpy.RemoveJoin_management ("Selectee_lyr")

   # Copy the selected Selectee features to the output feature class
   arcpy.CopyFeatures_management ("Selectee_lyr", outSelectee)
   
   featTuple = (outPF, outSBB)
   return featTuple

def AddCoreAreaToSBBs(in_PF, in_SBB, fld_SFID, in_Core, out_SBB, BuffDist = "1000 METERS", scratchGDB = "in_memory"):
   '''Adds core area to SBBs of PFs intersecting that core. This function should only be used with a single Core feature; i.e., either embed it within a loop, or use an input Cores layer that contains only a single core. Otherwise it will not behave as needed.
   in_PF: layer or feature class representing Procedural Features
   in_SBB: layer or feature class representing Site Building Blocks
   fld_SFID: unique ID field relating PFs to SBBs
   in_Core: layer or feature class representing habitat Cores
   BuffDist: distance used to add buffer area to SBBs
   scratchGDB: geodatabase to store intermediate products'''
   
   # Make Feature Layer from PFs
   where_clause = "RULE NOT IN ('AHZ', '1')"
   arcpy.MakeFeatureLayer_management(in_PF, "PF_CoreSub", where_clause)
   
   # Get PFs centered in the core
   printMsg('Selecting PFs intersecting the core...')
   arcpy.SelectLayerByLocation_management("PF_CoreSub", "INTERSECT", in_Core, "", "NEW_SELECTION", "NOT_INVERT")
   
   # Get SBBs associated with selected PFs
   printMsg('Copying selected PFs and their associated SBBs...')
   sbbSub = scratchGDB + os.sep + 'sbb'
   pfSub = scratchGDB + os.sep + 'pf'
   SubsetSBBandPF(in_SBB, "PF_CoreSub", "SBB", fld_SFID, sbbSub, pfSub)
   
   # Buffer SBBs 
   printMsg("Buffering SBBs...")
   sbbBuff = scratchGDB + os.sep + "sbbBuff"
   arcpy.Buffer_analysis(sbbSub, sbbBuff, BuffDist, "FULL", "ROUND", "NONE", "", "PLANAR")
   
   # Clip buffers to core
   printMsg("Clipping buffered SBBs to core...")
   clpBuff = scratchGDB + os.sep + "clpBuff"
   CleanClip(sbbBuff, in_Core, clpBuff, scratchGDB)
   
   # Remove any SBB fragments not containing a PF
   printMsg('Culling SBB fragments...')
   sbbRtn = scratchGDB + os.sep + 'sbbRtn'
   CullFrags(clpBuff, pfSub, "0 METERS", sbbRtn)
   
   # Merge, then dissolve to get final shapes
   printMsg('Dissolving original SBBs with buffered SBBs to get final shapes...')
   sbbMerge = scratchGDB + os.sep + "sbbMerge"
   arcpy.Merge_management ([sbbSub, sbbRtn], sbbMerge)
   arcpy.Dissolve_management (sbbMerge, out_SBB, [fld_SFID, "intRule"], "")
   
   printMsg('Done.')
   return out_SBB

def ChopSBBs(in_PF, in_SBB, in_EraseFeats, out_Clusters, out_subErase, dilDist = "5 METERS", scratchGDB = "in_memory"):
   '''Uses Erase Features to chop out sections of SBBs. Stitches SBB fragments back together only if within twice the dilDist of each other. Subsequently uses output to erase EraseFeats.'''

   # Use in_EraseFeats to chop out sections of SBB
   # Use regular Erase, not Clean Erase; multipart is good output at this point
   printMsg('Chopping SBBs...')
   firstChop = scratchGDB + os.sep + 'firstChop'
   arcpy.Erase_analysis (in_SBB, in_EraseFeats, firstChop)

   # Eliminate parts comprising less than 5% of total SBB size
   printMsg('Eliminating insignificant parts of SBBs...')
   rtnParts = scratchGDB + os.sep + 'rtnParts'
   arcpy.EliminatePolygonPart_management (firstChop, rtnParts, 'PERCENT', '', 5, 'ANY')
   
   # Shrinkwrap to fill in gaps
   printMsg('Clustering SBB fragments...')
   initClusters = scratchGDB + os.sep + 'initClusters'
   ShrinkWrap(rtnParts, dilDist, initClusters, smthMulti = 2)
   
   # Remove any fragments without procedural features
   printMsg('Culling SBB fragments...')
   CullFrags(initClusters, in_PF, 0, out_Clusters)
   
   # Use SBB clusters to chop out sections of Erase Features
   printMsg('Eliminating irrelevant Erase Features')
   CleanErase(in_EraseFeats, out_Clusters, out_subErase)
   
   outTuple = (out_Clusters, out_subErase)
   return outTuple

def warnings(rule):
   '''Generates warning messages specific to SBB rules'''
   warnMsgs = arcpy.GetMessages(1)
   if warnMsgs:
      printWrng('Finished processing Rule %s, but there were some problems.' % str(rule))
      printWrng(warnMsgs)
   else:
      printMsg('Rule %s SBBs completed' % str(rule))

def PrepProcFeats(in_PF, fld_Rule, fld_Buff, tmpWorkspace):
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
            if RuleString == 'AHZ':
               RuleInteger = -1
            else:
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

def CreateStandardSBB(in_PF, out_SBB, scratchGDB = "in_memory"):
   '''Creates standard buffer SBBs for specified subset of PFs'''
   try:
      # Process: Select (Defined Buffer Rules)
      selQry = "(intRule in (-1,1,2,3,4,8,10,11,12,13,14)) AND (fltBuffer <> 0)"
      arcpy.MakeFeatureLayer_management(in_PF, "tmpLyr", selQry)

      # Count records and proceed accordingly
      count = countFeatures("tmpLyr")
      if count > 0:
         # Process: Buffer
         tmpSBB = scratchGDB + os.sep + 'tmpSBB'
         arcpy.Buffer_analysis("tmpLyr", tmpSBB, "fltBuffer", "FULL", "ROUND", "NONE", "", "PLANAR")
         # Append to output and cleanup
         arcpy.Append_management (tmpSBB, out_SBB, "NO_TEST")
         printMsg('Simple buffer SBBs completed')
         garbagePickup([tmpSBB])
      else:
         printMsg('There are no PFs using the simple buffer rules')
   except:
      printWrng('Unable to process the simple buffer features')
      tback()

def CreateNoBuffSBB(in_PF, out_SBB):
   '''Creates SBBs that are simple copies of PFs for specified subset'''
   try:
      # Process: Select (No-Buffer Rules)
      selQry = "(intRule in (-1,13,15) AND (fltBuffer = 0))"
      arcpy.MakeFeatureLayer_management(in_PF, "tmpLyr", selQry)

      # Count records and proceed accordingly
      count = countFeatures("tmpLyr")
      if count > 0:
         # Append to output and cleanup
         arcpy.Append_management ("tmpLyr", out_SBB, "NO_TEST")
         printMsg('No-buffer SBBs completed')
      else:
         printMsg('There are no PFs using the no-buffer rules')
   except:
      printWrng('Unable to process the no-buffer features.')
      tback()

def CreateWetlandSBB(in_PF, fld_SFID, selQry, in_NWI, out_SBB, tmpWorkspace = "in_memory", scratchGDB = "in_memory"):
   '''Creates standard wetland SBBs from Rule 5, 6, 7, or 9 Procedural Features (PFs). The procedures are the same for all rules, the only difference being the rule-specific inputs.
   
#     Carries out the following general procedures:
#     1.  Buffer the PF by 250-m.  This is the minimum buffer.
#     2.  Buffer the PF by 500-m.  This is the maximum buffer.
#     3.  Clip any NWI wetland features to the maximum buffer, then shrinkwrap features.
#     4.  Select clipped NWI features within 15-m of the PF.
#     5.  Buffer the selected NWI feature(s), if applicable, by 100-m.
#     6.  Merge the minimum buffer with the buffered NWI feature(s).
#     7.  Clip the merged feature to the maximum buffer.'''

   # Process: Select PFs
   sub_PF = tmpWorkspace + os.sep + 'sub_PF'
   arcpy.Select_analysis (in_PF, sub_PF, selQry)
   
   # Count records and proceed accordingly
   count = countFeatures(sub_PF)
   if count > 0:
      # Declare some additional parameters
      # These can be tweaked as desired
      nwiBuff = "100 METERS"# buffer to be used for NWI features (may or may not equal minBuff)
      minBuff = "250 METERS" # minimum buffer to include in SBB
      maxBuff = "500 METERS" # maximum buffer to include in SBB
      searchDist = "15 METERS" # search distance for inclusion of NWI features

      # Set workspace and some additional variables
      arcpy.env.workspace = scratchGDB
      num, units, newMeas = multiMeasure(searchDist, 0.5)

      # Create an empty list to store IDs of features that fail to get processed
      myFailList = []

      # Loop through the individual Procedural Features
      myIndex = 1 # Set a counter index
      with arcpy.da.SearchCursor(sub_PF, [fld_SFID, "SHAPE@"]) as myProcFeats:
         for myPF in myProcFeats:
         # for each Procedural Feature in the set, do the following...
            try: # Even if one feature fails, script can proceed to next feature

               # Extract the unique Source Feature ID and geometry object
               myID = myPF[0]
               myShape = myPF[1]

               # Add a progress message
               printMsg("\nWorking on feature %s, with SFID = %s" %(str(myIndex), myID))

               # Process:  Select (Analysis)
               # Create a temporary feature class including only the current PF
               selQry = fld_SFID + " = '%s'" % myID
               arcpy.Select_analysis (in_PF, "tmpPF", selQry)

               # Step 1: Create a minimum buffer around the Procedural Feature
               printMsg("Creating minimum buffer")
               arcpy.Buffer_analysis ("tmpPF", "myMinBuffer", minBuff)

               # Step 2: Create a maximum buffer around the Procedural Feature
               printMsg("Creating maximum buffer")
               arcpy.Buffer_analysis ("tmpPF", "myMaxBuffer", maxBuff)
               
               # Step 3: Clip the NWI to the maximum buffer, and shrinkwrap
               printMsg("Clipping NWI features to maximum buffer and shrinkwrapping...")
               arcpy.Clip_analysis(in_NWI, "myMaxBuffer", "tmpClipNWI")
               shrinkNWI = scratchGDB + os.sep + "shrinkNWI"
               ShrinkWrap("tmpClipNWI", newMeas, shrinkNWI)

               # Step 4: Select shrinkwrapped NWI features within range
               printMsg("Selecting nearby NWI features")
               arcpy.MakeFeatureLayer_management ("shrinkNWI", "NWI_lyr", "", "", "")
               arcpy.SelectLayerByLocation_management ("NWI_lyr", "WITHIN_A_DISTANCE", "tmpPF", searchDist, "NEW_SELECTION")

               # Determine how many NWI features were selected
               selFeats = int(arcpy.GetCount_management("NWI_lyr")[0])

               # If NWI features are in range, then process
               if selFeats > 0:
                  # Step 5: Create a buffer around the NWI feature(s)
                  printMsg("Buffering selected NWI features...")
                  arcpy.Buffer_analysis ("NWI_lyr", "nwiBuff", nwiBuff)

                  # Step 6: Merge the minimum buffer with the NWI buffer
                  printMsg("Merging buffered PF with buffered NWI feature(s)...")
                  feats2merge = ["myMinBuffer", "nwiBuff"]
                  print str(feats2merge)
                  arcpy.Merge_management(feats2merge, "tmpMerged")

                  # Dissolve features into a single polygon
                  printMsg("Dissolving buffered PF and NWI features into a single feature...")
                  arcpy.Dissolve_management ("tmpMerged", "tmpDissolved", "", "", "", "")

                  # Step 7: Clip the dissolved feature to the maximum buffer
                  printMsg("Clipping dissolved feature to maximum buffer...")
                  arcpy.Clip_analysis ("tmpDissolved", "myMaxBuffer", "tmpClip", "")

                  # Use the clipped, combined feature geometry as the final shape
                  myFinalShape = arcpy.SearchCursor("tmpClip").next().Shape
               else:
                  # Use the simple minimum buffer as the final shape
                  printMsg("No NWI features found within specified search distance")
                  myFinalShape = arcpy.SearchCursor("myMinBuffer").next().Shape

               # Update the PF shape
               myCurrentPF_rows = arcpy.UpdateCursor("tmpPF", "", "", "Shape", "")
               myPF_row = myCurrentPF_rows.next()
               myPF_row.Shape = myFinalShape
               myCurrentPF_rows.updateRow(myPF_row)

               # Process:  Append
               # Append the final geometry to the SBB feature class.
               printMsg("Appending final shape to SBB feature class...")
               arcpy.Append_management("tmpPF", out_SBB, "NO_TEST", "", "")

               # Add final progress message
               printMsg("Finished processing feature " + str(myIndex))
               
            except:
               # Add failure message and append failed feature ID to list
               printMsg("\nFailed to fully process feature " + str(myIndex))
               myFailList.append(int(myID))

               # Error handling code swiped from "A Python Primer for ArcGIS"
               tb = sys.exc_info()[2]
               tbinfo = traceback.format_tb(tb)[0]
               pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
               msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

               printWrng(msgs)
               printWrng(pymsg)
               printMsg(arcpy.GetMessages(1))

               # Add status message
               printMsg("\nMoving on to the next feature.  Note that the SBB output will be incomplete.")

            finally:
              # Increment the index by one
               myIndex += 1
               
               # Release cursor row
               del myPF

      # Once the script as a whole has succeeded, let the user know if any individual
      # features failed
      if len(myFailList) == 0:
         printMsg("All features successfully processed")
      else:
         printWrng("Processing failed for the following features: " + str(myFailList))
   else:
      printMsg('There are no PFs with this rule; passing...')

def CreateSBBs(in_PF, fld_SFID, fld_Rule, fld_Buff, in_nwi5, in_nwi67, in_nwi9, out_SBB, scratchGDB = "in_memory"):
   '''Creates SBBs for all input PFs, subsetting and applying rules as needed.
   Usage Notes:  
   - This function does not test to determine if all of the input Procedural Features should be subject to a particular rule. The user must ensure that this is so.
   - It is recommended that the NWI feature class be stored on your local drive rather than a network drive, to optimize processing speed.
   - For the CreateWetlandSBBs function to work properly, the input NWI data must contain a subset of only those features applicable to the particular rule.  Adjacent NWI features should have boundaries dissolved.
   - For best results, it is recommended that you close all other programs before running this tool, since it relies on having ample memory for processing.'''

   tStart = datetime.now()
   
   # Print helpful message to geoprocessing window
   getScratchMsg(scratchGDB)

   # Set up some variables
   tmpWorkspace = createTmpWorkspace()
   sr = arcpy.Describe(in_PF).spatialReference
   printMsg("Additional critical temporary products will be stored here: %s" % tmpWorkspace)
   sub_PF = scratchGDB + os.sep + 'sub_PF' # for storing PF subsets

   # Set up trashList for later garbage collection
   trashList = [sub_PF]

   # Prepare input procedural featuers
   printMsg('Prepping input procedural features')
   tmp_PF = PrepProcFeats(in_PF, fld_Rule, fld_Buff, tmpWorkspace)
   trashList.append(tmp_PF)

   printMsg('Beginning SBB creation...')

   # Create empty feature class to store SBBs
   printMsg('Creating empty feature class for output')
   if arcpy.Exists(out_SBB):
      arcpy.Delete_management(out_SBB)
   outDir = os.path.dirname(out_SBB)
   outName = os.path.basename(out_SBB)
   printMsg('Creating %s in %s' %(outName, outDir))
   arcpy.CreateFeatureclass_management (outDir, outName, "POLYGON", tmp_PF, '', '', sr)

   # Standard buffer SBBs
   printMsg('Processing the simple defined-buffer features...')
   CreateStandardSBB(tmp_PF, out_SBB)

   # No buffer SBBs
   printMsg('Processing the no-buffer features')
   CreateNoBuffSBB(tmp_PF, out_SBB)

   # Rule 5 SBBs
   printMsg('Processing the Rule 5 features')
   selQry = "intRule = 5"
   in_NWI = in_nwi5
   try:
      CreateWetlandSBB(tmp_PF, fld_SFID, selQry, in_NWI, out_SBB, tmpWorkspace, "in_memory")
      warnings(5)
   except:
      printWrng('Unable to process Rule 5 features')
      tback()

   # Rule 6 SBBs
   printMsg('Processing the Rule 6 features')
   selQry = "intRule = 6"
   in_NWI = in_nwi67
   try:
      CreateWetlandSBB(tmp_PF, fld_SFID, selQry, in_NWI, out_SBB, tmpWorkspace, "in_memory")
      warnings(6)
   except:
      printWrng('Unable to process Rule 6 features')
      tback()

   # Rule 7 SBBs
   printMsg('Processing the Rule 7 features')
   selQry = "intRule = 7"
   in_NWI = in_nwi67
   try:
      CreateWetlandSBB(tmp_PF, fld_SFID, selQry, in_NWI, out_SBB, tmpWorkspace, "in_memory")
      warnings(7)
   except:
      printWrng('Unable to process Rule 7 features')
      tback()

   # Rule 9 SBBs
   printMsg('Processing the Rule 9 features')
   selQry = "intRule = 9"
   in_NWI = in_nwi9
   try:
      CreateWetlandSBB(tmp_PF, fld_SFID, selQry, in_NWI, out_SBB, tmpWorkspace, "in_memory")
      warnings(9)
   except:
      printWrng('Unable to process Rule 9 features')
      tback()

   printMsg('SBB processing complete')
   
   tFinish = datetime.now()
   deltaString = GetElapsedTime (tStart, tFinish)
   printMsg("Processing complete. Total elapsed time: %s" %deltaString)
   
   return out_SBB

def ExpandSBBs(in_Cores, in_SBB, in_PF, fld_SFID, out_SBB, scratchGDB = "in_memory"):
   '''Expands SBBs by adding core area.'''
   
   tStart = datetime.now()
   
   # Declare path/name of output data and workspace
   drive, path = os.path.splitdrive(out_SBB) 
   path, filename = os.path.split(path)
   myWorkspace = drive + path
   
   # Print helpful message to geoprocessing window
   getScratchMsg(scratchGDB)
   
   # Set up output locations for subsets of SBBs and PFs to process
   SBB_sub = scratchGDB + os.sep + 'SBB_sub'
   PF_sub = scratchGDB + os.sep + 'PF_sub'
   
   # Subset PFs and SBBs
   printMsg('Using the current SBB selection and making copies of the SBBs and PFs...')
   SubsetSBBandPF(in_SBB, in_PF, "PF", fld_SFID, SBB_sub, PF_sub)
   
   # Process: Select Layer By Location (Get Cores intersecting PFs)
   printMsg('Selecting cores that intersect procedural features')
   arcpy.MakeFeatureLayer_management(in_Cores, "Cores_lyr")
   arcpy.MakeFeatureLayer_management(PF_sub, "PF_lyr") 
   arcpy.SelectLayerByLocation_management("Cores_lyr", "INTERSECT", "PF_lyr", "", "NEW_SELECTION", "NOT_INVERT")

   # Process:  Copy the selected Cores features to scratch feature class
   selCores = scratchGDB + os.sep + 'selCores'
   arcpy.CopyFeatures_management ("Cores_lyr", selCores) 

   # Process:  Repair Geometry and get feature count
   arcpy.RepairGeometry_management (selCores, "DELETE_NULL")
   numCores = countFeatures(selCores)
   printMsg('There are %s cores to process.' %str(numCores))
   
   # Create Feature Class to store expanded SBBs
   printMsg("Creating feature class to store buffered SBBs...")
   arcpy.CreateFeatureclass_management (scratchGDB, 'sbbExpand', "POLYGON", SBB_sub, "", "", SBB_sub) 
   sbbExpand = scratchGDB + os.sep + 'sbbExpand'
   
   # Loop through Cores and add core buffers to SBBs
   counter = 1
   with  arcpy.da.SearchCursor(selCores, ["SHAPE@", "CoreID"]) as myCores:
      for core in myCores:
         # Add extra buffer for SBBs of PFs located in cores. Extra buffer needs to be snipped to core in question.
         coreShp = core[0]
         coreID = core[1]
         printMsg('Working on Core ID %s' % str(coreID))
         tmpSBB = scratchGDB + os.sep + 'sbb'
         AddCoreAreaToSBBs(PF_sub, SBB_sub, fld_SFID, coreShp, tmpSBB, "1000 METERS", scratchGDB)
         
         # Append expanded SBB features to output
         arcpy.Append_management (tmpSBB, sbbExpand, "NO_TEST")
         
         del core
   
   # Merge, then dissolve original SBBs with buffered SBBs to get final shapes
   printMsg('Merging all SBBs...')
   sbbAll = scratchGDB + os.sep + "sbbAll"
   #sbbFinal = myWorkspace + os.sep + "sbbFinal"
   arcpy.Merge_management ([SBB_sub, sbbExpand], sbbAll)
   arcpy.Dissolve_management (sbbAll, out_SBB, [fld_SFID, "intRule"], "")
   #arcpy.MakeFeatureLayer_management(sbbFinal, "SBB_lyr") 
   
   printMsg('SBB processing complete')
   
   tFinish = datetime.now()
   deltaString = GetElapsedTime (tStart, tFinish)
   printMsg("Processing complete. Total elapsed time: %s" %deltaString)
   
   return out_SBB

def ParseSBBs(in_SBB, out_terrSBB, out_ahzSBB):
   '''Splits input SBBs into two feature classes, one for standard terrestrial SBBs and one for AHZ SBBs.'''
   terrQry = "intRule <> -1" 
   ahzQry = "intRule = -1"
   arcpy.Select_analysis (in_SBB, out_terrSBB, terrQry)
   arcpy.Select_analysis (in_SBB, out_ahzSBB, ahzQry)
   
   sbbTuple = (out_terrSBB, out_ahzSBB)
   return sbbTuple

def CreateConSites(in_SBB, ysn_Expand, in_PF, fld_SFID, in_ConSites, out_ConSites, site_Type, in_Hydro, in_TranSurf = None, in_Exclude = None, scratchGDB = "in_memory"):
   '''Creates Conservation Sites from the specified inputs:
   - in_SBB: feature class representing Site Building Blocks
   - ysn_Expand: ["true"/"false"] - determines whether to expand the selection of SBBs to include more in the vicinity
   - in_PF: feature class representing Procedural Features
   - fld_SFID: name of the field containing the unique ID linking SBBs to PFs. Field name is must be the same for both.
   - in_ConSites: feature class representing current Conservation Sites (or, a template feature class)
   - out_ConSites: the output feature class representing updated Conservation Sites
   - site_Type: type of conservation site (TERRESTRIAL|AHZ)
   - in_Hydro: feature class representing water bodies
   - in_TranSurf: feature class(es) representing transportation surfaces (i.e., road and rail) [If multiple, this is a string with items separated by ';']
   - in_Exclude: feature class representing areas to definitely exclude from sites
   - scratchGDB: geodatabase to contain intermediate/scratch products. Setting this to "in_memory" can result in HUGE savings in processing time, but there's a chance you might run out of memory and cause a crash.
   '''
   
   # Get timestamp
   tStart = datetime.now()
   
   # Specify a bunch of parameters
   selDist = "1000 METERS" # Distance used to expand the SBB selection, if this option is selected. Also used to add extra buffer to SBBs.
   dilDist = "250 METERS" # Distance used to coalesce SBBs into ProtoSites (precursors to final automated CS boundaries). Features within twice this distance of each other will be merged into one.
   hydroPerCov = 100 # The minimum percent of any SBB feature that must be covered by water, for those features to be eliminated from the set of features which are used to erase portions of the site. Set to 101 if you don't want features to ever be purged.
   hydroQry = "Hydro = 1" # Expression used to select appropriate hydro features to create erase features
   hydroElimDist = "10 METERS" # Distance used to eliminate insignificant water features from the set of erasing features. Portions of water bodies less than double this width will not be used to split or erase portions of sites.
   transPerCov = 101 #The minimum percent any SBB that must be covered by transportation surfaces, for those surfaces to be eliminated from the set of features which are used to erase portions of the site. Set to 101 if you don't want features to ever be purged.
   transQry = "NH_IGNORE = 0 OR NH_IGNORE IS NULL" ### Substituted old query with new query, allowing user to specify segments to ignore. Old query was: "DCR_ROW_TYPE = 'IS' OR DCR_ROW_TYPE = 'PR'" # Expression used to select appropriate transportation surface features to create erase features
   buffDist = "200 METERS" # Distance used to buffer ProtoSites to establish the area for further processing.
   searchDist = "0 METERS" # Distance from PFs used to determine whether to cull SBB and ConSite fragments after ProtoSites have been split.
   coalDist = "25 METERS" # Distance for coalescing split sites back together. Sites with less than double this width between each other will merge.
   
   if not scratchGDB:
      scratchGDB = "in_memory"
      # Use "in_memory" as default, but if script is failing, use scratchGDB on disk. Also use scratchGDB on disk if you are trying to run this in two or more instances of Arc or Python, otherwise you can run into catastrophic memory conflicts.
      
   if scratchGDB != "in_memory":
      printMsg("Scratch outputs will be stored here: %s" % scratchGDB)
      scratchParm = scratchGDB
   else:
      printMsg("Scratch products are being stored in memory and will not persist. If processing fails inexplicably, or if you want to be able to inspect scratch products, try running this with a specified scratchGDB on disk.")
      scratchParm = "in_memory"

   # Set overwrite option so that existing data may be overwritten
   arcpy.env.overwriteOutput = True 

   # Declare path/name of output data and workspace
   drive, path = os.path.splitdrive(out_ConSites) 
   path, filename = os.path.split(path)
   myWorkspace = drive + path
   Output_CS_fname = filename
   
   # Parse out transportation datasets
   if site_Type == 'TERRESTRIAL':
      Trans = in_TranSurf.split(';')
   
   # If applicable, clear any selections on non-SBB inputs
   for fc in [in_PF, in_Hydro]:
      clearSelection(fc)

   if site_Type == 'TERRESTRIAL':
      printMsg("Site type is %s" % site_Type)
      clearSelection(in_Exclude)
      for fc in Trans:
         clearSelection(fc)
   
   ### Start data prep
   tStartPrep = datetime.now()
   
   # Merge the transportation layers, if necessary
   if site_Type == 'TERRESTRIAL':
      if len(Trans) == 1:
         Trans = Trans[0]
      else:
         printMsg('Merging transportation surfaces')
         # Must absolutely write this to disk (myWorkspace) not to memory (scratchGDB), or for some reason there is no OBJECTID field and as a result, code for CullEraseFeats will fail.
         mergeTrans = myWorkspace + os.sep + 'mergeTrans'
         arcpy.Merge_management(Trans, mergeTrans)
         Trans = mergeTrans

   # Get relevant hydro features
   openWater = scratchGDB + os.sep + 'openWater'
   arcpy.Select_analysis (in_Hydro, openWater, hydroQry)

   # Set up output locations for subsets of SBBs and PFs to process
   SBB_sub = scratchGDB + os.sep + 'SBB_sub'
   PF_sub = scratchGDB + os.sep + 'PF_sub'
   
   if ysn_Expand == "true":
      # Expand SBB selection
      printMsg('Expanding the current SBB selection and making copies of the SBBs and PFs...')
      ExpandSBBselection(in_SBB, in_PF, fld_SFID, in_ConSites, selDist, SBB_sub, PF_sub)
   else:
      # Subset PFs and SBBs
      printMsg('Using the current SBB selection and making copies of the SBBs and PFs...')
      SubsetSBBandPF(in_SBB, in_PF, "PF", fld_SFID, SBB_sub, PF_sub)

   # Make Feature Layers
   arcpy.MakeFeatureLayer_management(PF_sub, "PF_lyr") 
   arcpy.MakeFeatureLayer_management(SBB_sub, "SBB_lyr") 
   arcpy.MakeFeatureLayer_management(openWater, "Hydro_lyr")
   sub_Hydro = "Hydro_lyr"
   
   # Process:  Create Feature Classes (to store ConSites)
   printMsg("Creating ConSites features class to store output features...")
   arcpy.CreateFeatureclass_management (myWorkspace, Output_CS_fname, "POLYGON", in_ConSites, "", "", in_ConSites) 

   ### End data prep
   tEndPrep = datetime.now()
   deltaString = GetElapsedTime (tStartPrep, tEndPrep)
   printMsg("Data prep complete. Elapsed time: %s" %deltaString)
   
   # Process:  ShrinkWrap
   tProtoStart = datetime.now()
   printMsg("Creating ProtoSites by shrink-wrapping SBBs...")
   outPS = myWorkspace + os.sep + 'ProtoSites'
      # Saving ProtoSites to hard drive, just in case...
   printMsg('ProtoSites will be stored here: %s' % outPS)
   ShrinkWrap("SBB_lyr", dilDist, outPS)

   # Generalize Features in hopes of speeding processing and preventing random processing failures 
   arcpy.AddMessage("Simplifying features...")
   arcpy.Generalize_edit(outPS, "0.1 Meters")
   
   # Get info on ProtoSite generation
   numPS = countFeatures(outPS)
   tProtoEnd = datetime.now()
   deltaString = GetElapsedTime(tProtoStart, tProtoEnd)
   printMsg('Finished ProtoSite creation. There are %s ProtoSites.' %numPS)
   printMsg('Elapsed time: %s' %deltaString)

   # Loop through the ProtoSites to create final ConSites
   printMsg("Modifying individual ProtoSites to create final Conservation Sites...")
   counter = 1
   with arcpy.da.SearchCursor(outPS, ["SHAPE@"]) as myProtoSites:
      for myPS in myProtoSites:
         try:
            printMsg('Working on ProtoSite %s' % str(counter))
            tProtoStart = datetime.now()
            
            psSHP = myPS[0]
            tmpPS = scratchGDB + os.sep + "tmpPS"
            arcpy.CopyFeatures_management (psSHP, tmpPS) 
            tmpSS_grp = scratchGDB + os.sep + "tmpSS_grp"
            arcpy.CreateFeatureclass_management (scratchGDB, "tmpSS_grp", "POLYGON", in_ConSites, "", "", in_ConSites) 
            
            # Get SBBs within the ProtoSite
            printMsg('Selecting SBBs within ProtoSite...')
            arcpy.SelectLayerByLocation_management("SBB_lyr", "INTERSECT", tmpPS, "", "NEW_SELECTION", "NOT_INVERT")
            
            # Copy the selected SBB features to tmpSBB
            tmpSBB = scratchGDB + os.sep + 'tmpSBB'
            arcpy.CopyFeatures_management ("SBB_lyr", tmpSBB)
            printMsg('Selected SBBs copied.')
            
            # Get PFs within the ProtoSite
            printMsg('Selecting PFs within ProtoSite...')
            arcpy.SelectLayerByLocation_management("PF_lyr", "INTERSECT", tmpPS, "", "NEW_SELECTION", "NOT_INVERT")
            
            # Copy the selected PF features to tmpPF
            tmpPF = scratchGDB + os.sep + 'tmpPF'
            arcpy.CopyFeatures_management ("PF_lyr", tmpPF)
            printMsg('Selected PFs copied.')
            
            # Buffer around the ProtoSite
            printMsg('Buffering ProtoSite to get processing area...')
            tmpBuff = scratchGDB + os.sep + 'tmpBuff'
            arcpy.Buffer_analysis (tmpPS, tmpBuff, buffDist, "", "", "", "")  
            
            # Clip exclusion features to buffer
            if site_Type == 'TERRESTRIAL':
               printMsg('Clipping transportation features to buffer...')
               tranClp = scratchGDB + os.sep + 'tranClp'
               CleanClip(Trans, tmpBuff, tranClp, scratchParm)
               printMsg('Clipping exclusion features to buffer...')
               efClp = scratchGDB + os.sep + 'efClp'
               CleanClip(in_Exclude, tmpBuff, efClp, scratchParm)
            printMsg('Clipping hydro features to buffer...')
            hydroClp = scratchGDB + os.sep + 'hydroClp'
            CleanClip(sub_Hydro, tmpBuff, hydroClp, scratchParm)
                        
            # Cull Transportation Surface and Exclusion Features 
            # This is to eliminate features intended to be ignored in automation process
            if site_Type == 'TERRESTRIAL':    
               # Get Transportation Surface Erase Features
               printMsg('Subsetting transportation features')
               transErase = scratchGDB + os.sep + 'transErase'
               arcpy.Select_analysis (tranClp, transErase, transQry)
               
               # Get Exclusion Erase Features
               printMsg('Subsetting exclusion features')
               exclErase = scratchGDB + os.sep + 'exclErase'
               arcpy.Select_analysis (efClp, exclErase, transQry)
               efClp = exclErase
            
            # Cull Hydro Erase Features
            printMsg('Culling hydro erase features based on prevalence in SBBs...')
            hydroRtn = scratchGDB + os.sep + 'hydroRtn'
            CullEraseFeats (hydroClp, tmpSBB, fld_SFID, hydroPerCov, hydroRtn, scratchParm)
            
            # Dissolve Hydro Erase Features
            printMsg('Dissolving hydro erase features...')
            hydroDiss = scratchGDB + os.sep + 'hydroDiss'
            arcpy.Dissolve_management(hydroRtn, hydroDiss, "Hydro", "", "SINGLE_PART", "")
            
            # Get Hydro Erase Features
            printMsg('Eliminating narrow hydro features from erase features...')
            hydroErase = scratchGDB + os.sep + 'hydroErase'
            GetEraseFeats (hydroDiss, hydroQry, hydroElimDist, hydroErase, tmpPF, scratchParm)
            
            # Merge Erase Features (Exclusions, hydro, and transportation)
            if site_Type == 'TERRESTRIAL':
               printMsg('Merging erase features...')
               tmpErase = scratchGDB + os.sep + 'tmpErase'
               arcpy.Merge_management ([efClp, transErase, hydroErase], tmpErase)
            else:
               tmpErase = hydroErase
            
            # Coalesce erase features to remove weird gaps and slivers
            printMsg('Coalescing erase features...')
            coalErase = scratchGDB + os.sep + 'coalErase'
            Coalesce(tmpErase, "0.5 METERS", coalErase, scratchParm)

            # Modify SBBs and Erase Features
            printMsg('Clustering SBBs...')
            sbbClusters = scratchGDB + os.sep + 'sbbClusters'
            sbbErase = scratchGDB + os.sep + 'sbbErase'
            ChopSBBs(tmpPF, tmpSBB, coalErase, sbbClusters, sbbErase, "5 METERS", scratchParm)
            
            # Use erase features to chop out areas of SBBs
            printMsg('Erasing portions of SBBs...')
            sbbFrags = scratchGDB + os.sep + 'sbbFrags'
            CleanErase (tmpSBB, sbbErase, sbbFrags, scratchParm) 
            
            # Remove any SBB fragments too far from a PF
            printMsg('Culling SBB fragments...')
            sbbRtn = scratchGDB + os.sep + 'sbbRtn'
            CullFrags(sbbFrags, tmpPF, searchDist, sbbRtn)
            arcpy.MakeFeatureLayer_management(sbbRtn, "sbbRtn_lyr")
            
            # Use erase features to chop out areas of ProtoSites
            printMsg('Erasing portions of ProtoSites...')
            psFrags = scratchGDB + os.sep + 'psFrags'
            CleanErase (psSHP, sbbErase, psFrags, scratchParm) 
            
            # Remove any ProtoSite fragments too far from a PF
            printMsg('Culling ProtoSite fragments...')
            psRtn = scratchGDB + os.sep + 'psRtn'
            CullFrags(psFrags, tmpPF, searchDist, psRtn)
            
            # Loop through the final (split) ProtoSites
            counter2 = 1
            with arcpy.da.SearchCursor(psRtn, ["SHAPE@"]) as mySplitSites:
               for mySS in mySplitSites:
                  printMsg('Working on split site %s' % str(counter2))
                  
                  ssSHP = mySS[0]
                  tmpSS = scratchGDB + os.sep + "tmpSS" + str(counter2)
                  arcpy.CopyFeatures_management (ssSHP, tmpSS) 
                  
                  # Make Feature Layer from split site
                  arcpy.MakeFeatureLayer_management (tmpSS, "splitSiteLyr", "", "", "")
                           
                  # Get PFs within split site
                  arcpy.SelectLayerByLocation_management("PF_lyr", "INTERSECT", tmpSS, "", "NEW_SELECTION", "NOT_INVERT")
                  
                  # Select retained SBB fragments corresponding to selected PFs
                  tmpSBB2 = scratchGDB + os.sep + 'tmpSBB2' 
                  tmpPF2 = scratchGDB + os.sep + 'tmpPF2'
                  SubsetSBBandPF(sbbRtn, "PF_lyr", "SBB", fld_SFID, tmpSBB2, tmpPF2)
                  
                  # ShrinkWrap retained SBB fragments
                  csShrink = scratchGDB + os.sep + 'csShrink' + str(counter2)
                  ShrinkWrap(tmpSBB2, dilDist, csShrink)
                  
                  # Intersect shrinkwrap with original split site
                  # This is necessary to keep it from "spilling over" across features used to split.
                  csInt = scratchGDB + os.sep + 'csInt' + str(counter2)
                  arcpy.Intersect_analysis ([tmpSS, csShrink], csInt, "ONLY_FID")
                  
                  # Process:  Clean Erase (final removal of exclusion features)
                  if site_Type == 'TERRESTRIAL':
                     printMsg('Excising manually delineated exclusion features...')
                     ssErased = scratchGDB + os.sep + 'ssBnd' + str(counter2)
                     CleanErase (csInt, efClp, ssErased, scratchParm) 
                  else:
                     ssErased = csInt
                  
                  # Remove any fragments too far from a PF
                  # Verified this step is indeed necessary, 2018-01-23
                  printMsg('Culling site fragments...')
                  ssBnd = scratchGDB + os.sep + 'ssBnd'
                  CullFrags(ssErased, tmpPF2, searchDist, ssBnd)
                  
                  # Append the final geometry to the split sites group feature class.
                  printMsg("Appending feature...")
                  arcpy.Append_management(ssBnd, tmpSS_grp, "NO_TEST", "", "")
                  
                  counter2 +=1
                  del mySS

            # Re-merge split sites, if applicable
            printMsg("Reconnecting split sites, where warranted...")
            shrinkFrags = scratchGDB + os.sep + 'shrinkFrags'
            ShrinkWrap(tmpSS_grp, coalDist, shrinkFrags, 8)
            
            # Process:  Clean Erase (final removal of exclusion features)
            if site_Type == 'TERRESTRIAL':
               printMsg('Excising manually delineated exclusion features...')
               csErased = scratchGDB + os.sep + 'csErased'
               CleanErase (shrinkFrags, efClp, csErased, scratchParm) 
            else:
               csErased = shrinkFrags
            
            # Remove any fragments too far from a PF
            # Verified this step is indeed necessary, 2018-01-23
            printMsg('Culling site fragments...')
            csCull = scratchGDB + os.sep + 'csCull'
            CullFrags(csErased, tmpPF, searchDist, csCull)
            
            # Eliminate gaps
            printMsg('Eliminating gaps...')
            finBnd = scratchGDB + os.sep + 'finBnd'
            arcpy.EliminatePolygonPart_management (csCull, finBnd, "PERCENT", "", 99.99, "CONTAINED_ONLY")
            
            # Generalize
            printMsg('Generalizing boundary...')
            arcpy.Generalize_edit(finBnd, "0.5 METERS")

            # Append the final geometry to the ConSites feature class.
            printMsg("Appending feature...")
            arcpy.Append_management(finBnd, out_ConSites, "NO_TEST", "", "")
            
         except:
            # Error handling code swiped from "A Python Primer for ArcGIS"
            tb = sys.exc_info()[2]
            tbinfo = traceback.format_tb(tb)[0]
            pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
            msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

            printWrng(msgs)
            printWrng(pymsg)
            printMsg(arcpy.GetMessages(1))
         
         finally:
            tProtoEnd = datetime.now()
            deltaString = GetElapsedTime(tProtoStart, tProtoEnd)
            printMsg("Processing complete for ProtoSite %s. Elapsed time: %s" %(str(counter), deltaString))
            counter +=1
            del myPS
            
   tFinish = datetime.now()
   deltaString = GetElapsedTime (tStart, tFinish)
   printMsg("Processing complete. Total elapsed time: %s" %deltaString)
   

### Functions for creating Stream Conservation Sites (SCS) ###
def MakeServiceLayers_scs(in_hydroNet, upDist = 3000, downDist = 500):
   """Creates two Network Analyst service layers needed for SCU delineation. This tool only needs to be run the first time you run the suite of SCU delineation tools. After that, the output layers can be reused repeatedly for the subsequent tools in the SCU delineation sequence.
   
   NOTE: The restrictions (contained in "r" variable) for traversing the network must have been defined in the HydroNet itself (manually). If any additional restrictions are added, the HydroNet must be rebuilt or they will not take effect. I originally set a restriction of NoEphemeralOrIntermittent, but on testing I discovered that this eliminated some stream segments that actually might be needed. I set the restriction to NoEphemeral instead. We may find that we need to remove the NoEphemeral restriction as well, or that users will need to edit attributes of the NHDFlowline segments on a case-by-case basis. I also previously included NoConnectors as a restriction, but in some cases I noticed with INSTAR data, it seems necessary to allow connectors, so I have removed that restriction. The NoCanalDitch exclusion was also removed, after finding some INSTAR sites on this type of flowline, and with CanalDitch immediately upstream.
   
   Parameters:
   - in_hydroNet = Input hydrological network dataset
   - upDist = The distance (in map units) to traverse upstream from a point along the network
   - downDist = The distance (in map units) to traverse downstream from a point along the network
   """
   arcpy.CheckOutExtension("Network")
   
   # Set up some variables
   descHydro = arcpy.Describe(in_hydroNet)
   nwDataset = descHydro.catalogPath
   catPath = os.path.dirname(nwDataset) # This is where hydro layers will be found
   hydroDir = os.path.dirname(catPath)
   hydroDir = os.path.dirname(hydroDir) # This is where output layer files will be saved
   nwLines = catPath + os.sep + "NHDLine"
   qry = "FType = 343" # DamWeir only
   arcpy.MakeFeatureLayer_management (nwLines, "lyr_DamWeir", qry)
   in_Lines = "lyr_DamWeir"
   downString = (str(downDist)).replace(".","_")
   upString = (str(upDist)).replace(".","_")
   lyrDownTrace = hydroDir + os.sep + "naDownTrace_%s.lyr"%downString
   lyrUpTrace = hydroDir + os.sep + "naUpTrace_%s.lyr"%upString
   r = "NoPipelines;NoUndergroundConduits;NoEphemeral;NoCoastline"
   
   printMsg("Creating upstream and downstream service layers...")
   for sl in [["naDownTrace", downDist, "FlowDownOnly"], ["naUpTrace", upDist, "FlowUpOnly"]]:
      restrictions = r + ";" + sl[2]
      serviceLayer = arcpy.MakeServiceAreaLayer_na(in_network_dataset=nwDataset,
         out_network_analysis_layer=sl[0], 
         impedance_attribute="Length", 
         travel_from_to="TRAVEL_FROM", 
         default_break_values=sl[1], 
         polygon_type="NO_POLYS", 
         merge="NO_MERGE", 
         nesting_type="RINGS", 
         line_type="TRUE_LINES_WITH_MEASURES", 
         overlap="NON_OVERLAP", 
         split="SPLIT", 
         excluded_source_name="", 
         accumulate_attribute_name="Length", 
         UTurn_policy="ALLOW_UTURNS", 
         restriction_attribute_name=restrictions, 
         polygon_trim="TRIM_POLYS", 
         poly_trim_value="100 Meters", 
         lines_source_fields="LINES_SOURCE_FIELDS", 
         hierarchy="NO_HIERARCHY", 
         time_of_day="")
   
   # Add dam barriers to both service layers and save
   printMsg("Adding dam barriers to service layers...")
   for sl in [["naDownTrace", lyrDownTrace], ["naUpTrace", lyrUpTrace]]:
      barriers = arcpy.AddLocations_na(in_network_analysis_layer=sl[0], 
         sub_layer="Line Barriers", 
         in_table=in_Lines, 
         field_mappings="Name Permanent_Identifier #", 
         search_tolerance="100 Meters", 
         sort_field="", 
         search_criteria="NHDFlowline SHAPE_MIDDLE_END;HydroNet_ND_Junctions NONE", 
         match_type="MATCH_TO_CLOSEST", 
         append="CLEAR", 
         snap_to_position_along_network="SNAP", 
         snap_offset="0 Meters", 
         exclude_restricted_elements="INCLUDE", 
         search_query="NHDFlowline #;HydroNet_ND_Junctions #")
         
      printMsg("Saving service layer to %s..." %sl[1])      
      arcpy.SaveToLayerFile_management(sl[0], sl[1]) 
      del barriers
      
   del serviceLayer
   
   arcpy.CheckInExtension("Network")
   
   return (lyrDownTrace, lyrUpTrace)

def MakeNetworkPts_scs(in_hydroNet, in_Catch, in_PF, out_Points):
   """Given a set of procedural features, creates points along the hydrological network. The user must ensure that the procedural features are "SCU-worthy."
   Parameters:
   - in_hydroNet = Input hydrological network dataset
   - in_Catch = Input catchments from NHDPlus
   - in_PF = Input Procedural Features
   - out_Points = Output feature class containing points generated from procedural features
   """
   
   # timestamp
   t0 = datetime.now()
   
   # Set up some variables
   sr = arcpy.Describe(in_PF).spatialReference   
   descHydro = arcpy.Describe(in_hydroNet)
   nwDataset = descHydro.catalogPath
   catPath = os.path.dirname(nwDataset) # This is where hydro layers will be found
   nhdFlowline = catPath + os.sep + "NHDFlowline"
   
   # Make feature layers  
   arcpy.MakeFeatureLayer_management (nhdFlowline, "lyr_Flowlines")
   arcpy.MakeFeatureLayer_management (in_Catch, "lyr_Catchments")
   
   # Select catchments intersecting PFs
   printMsg("Selecting catchments intersecting Procedural Features...")
   arcpy.SelectLayerByLocation_management ("lyr_Catchments", "INTERSECT", in_PF)
   
   # Buffer PFs by 30-m (standard slop factor) or by 250-m for wood turtles
   printMsg("Buffering Procedural Features...")
   code_block = """def buff(elcode):
      if elcode == "ARAAD02020":
         b = 250
      else:
         b = 30
      return b
      """
   expression = "buff(!ELCODE!)"
   arcpy.CalculateField_management (in_PF, "BUFFER", expression, "PYTHON", code_block)
   buff_PF = "in_memory" + os.sep + "buff_PF"
   arcpy.Buffer_analysis (in_PF, buff_PF, "BUFFER", "", "", "NONE")

   # Clip buffered PFs to selected catchments
   printMsg("Clipping buffered Procedural Features...")
   clipBuff_PF = "in_memory" + os.sep + "clipBuff_PF"
   arcpy.Clip_analysis (buff_PF, "lyr_Catchments", clipBuff_PF)
   
   # Select by location flowlines that intersect selected catchments
   printMsg("Selecting flowlines intersecting selected catchments...")
   arcpy.SelectLayerByLocation_management ("lyr_Flowlines", "INTERSECT", "lyr_Catchments")
   
   # Clip selected flowlines to clipped, buffered PFs
   printMsg("Clipping flowlines...")
   clipLines = "in_memory" + os.sep + "clipLines"
   arcpy.Clip_analysis ("lyr_Flowlines", clipBuff_PF, clipLines)
   
   # Create points from start- and endpoints of clipped flowlines
   arcpy.FeatureVerticesToPoints_management (clipLines, out_Points, "BOTH_ENDS")
   
   # timestamp
   t1 = datetime.now()
   ds = GetElapsedTime (t0, t1)
   printMsg("Completed function. Time elapsed: %s" % ds)
   
   return out_Points
   
def CreateLines_scs(out_Lines, in_PF, in_Points, in_downTrace, in_upTrace, out_Scratch = arcpy.env.scratchGDB):
   """Loads SCU points derived from Procedural Features, solves the upstream and downstream service layers, and combines network segments to create linear SCUs.
   Parameters:
   - out_Lines = Output lines representing Stream Conservation Units
   - in_PF = Input Procedural Features
   - in_Points = Input feature class containing points generated from procedural features
   - in_downTrace = Network Analyst service layer set up to run downstream
   - in_upTrace = Network Analyst service layer set up to run upstream
   - out_Scratch = Geodatabase to contain intermediate outputs"""
   
   arcpy.CheckOutExtension("Network")
   
   # timestamp
   t0 = datetime.now()
   
   # Set up some variables
   if out_Scratch == "in_memory":
      # recast to save to disk, otherwise there is no OBJECTID field for queries as needed
      outScratch = arcpy.env.scratchGDB
   printMsg("Casting strings to layer objects...")
   in_upTrace = arcpy.mapping.Layer(in_upTrace)
   in_downTrace = arcpy.mapping.Layer(in_downTrace)
   descDT = arcpy.Describe(in_downTrace)
   nwDataset = descDT.network.catalogPath
   catPath = os.path.dirname(nwDataset) # This is where hydro layers will be found
   hydroDir = os.path.dirname(catPath)
   hydroDir = os.path.dirname(hydroDir) # This is where output layer files will be saved
   lyrDownTrace = hydroDir + os.sep + "naDownTrace.lyr"
   lyrUpTrace = hydroDir + os.sep + "naUpTrace.lyr"
   downLines = out_Scratch + os.sep + "downLines"
   upLines = out_Scratch + os.sep + "upLines"
   outDir = os.path.dirname(out_Lines)
  
   # Load all points as facilities into both service layers; search distance 500 meters
   printMsg("Loading points into service layers...")
   for sa in [[in_downTrace,lyrDownTrace], [in_upTrace, lyrUpTrace]]:
      inLyr = sa[0]
      outLyr = sa[1]
      naPoints = arcpy.AddLocations_na(in_network_analysis_layer=inLyr, 
         sub_layer="Facilities", 
         in_table=in_Points, 
         field_mappings="Name FID #", 
         search_tolerance="500 Meters", 
         sort_field="", 
         search_criteria="NHDFlowline SHAPE;HydroNet_ND_Junctions NONE", 
         match_type="MATCH_TO_CLOSEST", 
         append="CLEAR", 
         snap_to_position_along_network="SNAP", 
         snap_offset="0 Meters", 
         exclude_restricted_elements="EXCLUDE", 
         search_query="NHDFlowline #;HydroNet_ND_Junctions #")
   printMsg("Completed point loading.")
   
   del naPoints
  
   # Solve upstream and downstream service layers; save out lines and updated layers
   for sa in [[in_downTrace, downLines, lyrDownTrace], [in_upTrace, upLines, lyrUpTrace]]:
      inLyr = sa[0]
      outLines = sa[1]
      outLyr = sa[2]
      printMsg("Solving service area for %s..." % inLyr)
      arcpy.Solve_na(in_network_analysis_layer=inLyr, 
         ignore_invalids="SKIP", 
         terminate_on_solve_error="TERMINATE", 
         simplification_tolerance="")
      inLines = arcpy.mapping.ListLayers(inLyr, "Lines")[0]
      printMsg("Saving out lines...")
      arcpy.CopyFeatures_management(inLines, outLines)
      arcpy.RepairGeometry_management (outLines, "DELETE_NULL")
      printMsg("Saving updated %s service layer to %s..." %(inLyr,outLyr))      
      arcpy.SaveToLayerFile_management(inLyr, outLyr)
   
   # # Merge the downstream segments with the upstream segments
   # printMsg("Merging primary segments...")
   # mergedLines = out_Scratch + os.sep + "mergedLines"
   # arcpy.Merge_management ([downLines, upLines], mergedLines)
   
   # Grab additional segments that may have been missed within large PFs in wide water areas
   # No longer sure this is necessary...?
   nhdFlowline = catPath + os.sep + "NHDFlowline"
   clpLines = out_Scratch + os.sep + "clpLines"
   qry = "FType in (460, 558)" # StreamRiver and ArtificialPath only
   arcpy.MakeFeatureLayer_management (nhdFlowline, "StreamRiver_Line", qry)
   CleanClip("StreamRiver_Line", in_PF, clpLines)
   
   # Merge and dissolve the segments; ESRI does not make this simple
   printMsg("Merging primary segments with selected extension segments...")
   comboLines = out_Scratch + os.sep + "comboLines"
   arcpy.Merge_management ([downLines, upLines, clpLines], comboLines)
   
   printMsg("Buffering segments...")
   buffLines = out_Scratch + os.sep + "buffLines"
   arcpy.Buffer_analysis(comboLines, buffLines, "1 Meters", "FULL", "ROUND", "ALL") 
   
   printMsg("Exploding buffers...")
   explBuff = outDir + os.sep + "explBuff"
   arcpy.MultipartToSinglepart_management(buffLines, explBuff)
   
   printMsg("Grouping segments...")
   arcpy.AddField_management(explBuff, "grpID", "LONG")
   arcpy.CalculateField_management(explBuff, "grpID", "!OBJECTID!", "PYTHON")
   
   joinLines = out_Scratch + os.sep + "joinLines"
   fldMap = 'grpID "grpID" true true false 4 Long 0 0, First, #, %s, grpID, -1, -1' % explBuff
   arcpy.SpatialJoin_analysis(comboLines, explBuff, joinLines, "JOIN_ONE_TO_ONE", "KEEP_ALL", fldMap, "INTERSECT")
   
   printMsg("Dissolving segments by group...")
   arcpy.Dissolve_management(joinLines, out_Lines, "grpID", "", "MULTI_PART", "DISSOLVE_LINES")
   
   # timestamp
   t1 = datetime.now()
   ds = GetElapsedTime (t0, t1)
   printMsg("Completed function. Time elapsed: %s" % ds)

   arcpy.CheckInExtension("Network")
   
   return (out_Lines, lyrDownTrace, lyrUpTrace)

def BufferLines_scs(in_Lines, in_StreamRiver, in_LakePond, in_Catch, out_Buffers, out_Scratch = "in_memory", buffDist = 250 ):
   """Buffers streams and rivers associated with SCU-lines within catchments. This function is called by the DelinSite_scs function. 
   
   Parameters:
   in_Lines = Input SCU lines, generated as output from CreateLines_scu function
   in_StreamRiver = Input StreamRiver polygons from NHD
   in_LakePond = Input LakePond polygons from NHD
   in_Catch = Input catchments from NHDPlus
   buffDist = Distance, in meters, to buffer the SCU lines and their associated NHD polygons
   out_Scratch = Geodatabase to contain output products 
   """

   # Set up variables
   clipRiverPoly = out_Scratch + os.sep + "clipRiverPoly"
   fillRiverPoly = out_Scratch + os.sep + "fillRiverPoly"
   clipLakePoly = out_Scratch + os.sep + "clipLakePoly"
   fillLakePoly = out_Scratch + os.sep + "fillLakePoly"
   clipLines = out_Scratch + os.sep + "clipLines"
   StreamRiverBuff = out_Scratch + os.sep + "StreamRiverBuff"
   LakePondBuff = out_Scratch + os.sep + "LakePondBuff"
   LineBuff = out_Scratch + os.sep + "LineBuff"
   mergeBuff = out_Scratch + os.sep + "mergeBuff"
   dissBuff = out_Scratch + os.sep + "dissBuff"
   
   # Clip input layers to catchments
   # Also need to fill any holes in polygons to avoid aberrant results
   printMsg("Clipping StreamRiver polygons...")
   CleanClip("StreamRiver_Poly", in_Catch, clipRiverPoly)
   arcpy.EliminatePolygonPart_management (clipRiverPoly, fillRiverPoly, "PERCENT", "", 99, "CONTAINED_ONLY")
   arcpy.MakeFeatureLayer_management (fillRiverPoly, "StreamRivers")
   
   printMsg("Clipping LakePond polygons...")
   CleanClip("LakePond_Poly", in_Catch, clipLakePoly)
   arcpy.EliminatePolygonPart_management (clipLakePoly, fillLakePoly, "PERCENT", "", 99, "CONTAINED_ONLY")
   arcpy.MakeFeatureLayer_management (fillLakePoly, "LakePonds")
   
   printMsg("Clipping SCU lines...")
   arcpy.Clip_analysis(in_Lines, in_Catch, clipLines)
   
   # Select clipped NHD polygons intersecting clipped SCU lines
   printMsg("Selecting by location the clipped NHD polygons intersecting clipped SCU lines...")
   arcpy.SelectLayerByLocation_management("StreamRivers", "INTERSECT", clipLines, "", "NEW_SELECTION")
   arcpy.SelectLayerByLocation_management("LakePonds", "INTERSECT", clipLines, "", "NEW_SELECTION")
   
   # Buffer SCU lines and selected NHD polygons
   printMsg("Buffering StreamRiver polygons...")
   arcpy.Buffer_analysis("StreamRivers", StreamRiverBuff, buffDist, "", "ROUND", "NONE")
   
   printMsg("Buffering LakePond polygons...")
   arcpy.Buffer_analysis("LakePonds", LakePondBuff, buffDist, "", "ROUND", "NONE")
   
   printMsg("Buffering SCU lines...")
   arcpy.Buffer_analysis(clipLines, LineBuff, buffDist, "", "ROUND", "NONE")
   
   # Merge buffers and dissolve
   printMsg("Merging buffer polygons...")
   arcpy.Merge_management ([StreamRiverBuff, LakePondBuff, LineBuff], mergeBuff)
   
   printMsg("Dissolving...")
   arcpy.Dissolve_management (mergeBuff, dissBuff, "", "", "SINGLE_PART")
   
   # Clip buffers to catchment
   printMsg("Clipping buffer zone to catchments...")
   CleanClip(dissBuff, in_Catch, out_Buffers)
   # arcpy.MakeFeatureLayer_management (out_Buffers, "clipBuffers")
   
   return out_Buffers
   
def DelinSite_scs(in_Lines, in_Catch, in_hydroNet, out_Polys, in_FlowBuff, trim = "true", buffDist = 250, out_Scratch = "in_memory"):
   """Creates Stream Conservation Sites.
   
   Parameters:
   in_Lines = Input SCU lines, generated as output from CreateLines_scu function
   in_Catch = Input catchments from NHDPlus
   in_hydroNet = Input hydrological network dataset
   out_Polys = Output polygons representing partial watersheds draining to the SCU lines
   in_FlowBuff = Input raster where the flow distances shorter than a specified truncation distance are coded 1; output from the prepFlowBuff function. Ignored if trim = "false", in which case "None" can be entered.
   trim = Indicates whether sites should be restricted to buffers ("true"; default) or encompass entire catchments ("false")
   out_Scratch = Geodatabase to contain output products 
   """
   
   # timestamp
   t0 = datetime.now()

   # Select catchments intersecting scuLines
   printMsg("Selecting catchments containing SCU lines...")
   arcpy.MakeFeatureLayer_management (in_Catch, "lyr_Catchments")
   arcpy.SelectLayerByLocation_management ("lyr_Catchments", "INTERSECT", in_Lines)
   
   # Dissolve catchments
   printMsg("Dissolving catchments...")
   dissCatch = out_Scratch + os.sep + "dissCatch"
   arcpy.Dissolve_management ("lyr_Catchments", dissCatch, "", "", "SINGLE_PART", "")
   
   if trim == "true":
      # Set up some variables
      descHydro = arcpy.Describe(in_hydroNet)
      nwDataset = descHydro.catalogPath
      catPath = os.path.dirname(nwDataset) # This is where hydro layers will be found
      nhdArea = catPath + os.sep + "NHDArea"
      nhdWaterbody = catPath + os.sep + "NHDWaterbody"
      clipBuffers = out_Scratch + os.sep + "clipBuffers"
      clipBuffers_prj = arcpy.env.scratchGDB + os.sep + "clipBuffers_prj" # Can NOT project to in_memory
      fillPolys = out_Scratch + os.sep + "fillPolys"
      
      ### Used repeatedly in loop
      clipFlow = "in_memory" + os.sep + "clipFlow"
      flowPoly = "in_memory" + os.sep + "flowPoly"
      
      # Make feature layers including only StreamRiver and LakePond polygons from NHD
      printMsg("Making feature layers...")
      qry = "FType = 460" # StreamRiver only
      lyrStreamRiver = arcpy.MakeFeatureLayer_management (nhdArea, "StreamRiver_Poly", qry)
      qry = "FType = 390" # LakePond only
      lyrLakePond = arcpy.MakeFeatureLayer_management (nhdWaterbody, "LakePond_Poly", qry)
      
      # Create clipping buffers
      printMsg("Creating clipping buffers...")
      clipBuff = BufferLines_scs(in_Lines, lyrStreamRiver, lyrLakePond, dissCatch, clipBuffers, out_Scratch, buffDist)
      
      # Reproject clipping buffers, if necessary
      clipBuff_prj = ProjectToMatch_vec(clipBuff, in_FlowBuff, clipBuffers_prj, copy = 0)

      # Create empty feature class to store final buffers
      printMsg("Creating empty feature class for buffers")
      sr = arcpy.Describe(clipBuff_prj).spatialReference
      fname = "flowBuffers"
      fpath = out_Scratch
      flowBuff = fpath + os.sep + fname
      
      if arcpy.Exists(flowBuff):
         arcpy.Delete_management(flowBuff)
      arcpy.CreateFeatureclass_management (fpath, fname, "POLYGON", in_Catch, "", "", sr)

      # Clip the flow buffer raster to the clipping buffers, convert to polygons, and eliminate fragments
      printMsg("Creating flow buffer polygons...")
      with  arcpy.da.SearchCursor(clipBuff_prj, ["SHAPE@", "OBJECTID"]) as myBuffers:
         for buff in myBuffers:
            try:
               clpShp = buff[0]
               clpID = buff[1]
               #printMsg("Clipping the flow buffer raster...")
               clipRasterToPoly(in_FlowBuff, clpShp, clipFlow)
               
               #printMsg("Converting flow buffer raster to polygons...")
               arcpy.RasterToPolygon_conversion (clipFlow, flowPoly, "NO_SIMPLIFY", "VALUE")
               
               #printMsg("Eliminating fragments...")
               arcpy.MakeFeatureLayer_management (flowPoly, "flowPolys")
               arcpy.SelectLayerByLocation_management("flowPolys", "INTERSECT", in_Lines, "", "NEW_SELECTION")
               
               printMsg("Appending feature %s..." %clpID)
               arcpy.Append_management ("flowPolys", flowBuff, "NO_TEST")
            except:
               printMsg("Process failure for feature %s. Passing..." %clpID)
            
      in_Polys = flowBuff
   
   else: 
      in_Polys = dissCatch
      
   # Fill in gaps 
   # Unfortunately this does not fill the 1-pixel holes at edges of shapes
   printMsg("Filling in holes...")
   arcpy. EliminatePolygonPart_management (in_Polys, fillPolys, "PERCENT", "", 99, "CONTAINED_ONLY")
   
   # Reproject final shapes, if necessary
   finPolys = ProjectToMatch_vec(fillPolys, in_Catch, out_Polys, copy = 1)
   
   # # Coalesce to create final sites - 
   # # This takes forever! Like 9 hours. Don't include unless committee really wants it
   # printMsg("Coalescing...")
   # Coalesce(fillPolys, 10, out_Polys)
   
   # timestamp
   t1 = datetime.now()
   ds = GetElapsedTime (t0, t1)
   printMsg("Completed function. Time elapsed: %s" % ds)
   
   return finPolys
   
