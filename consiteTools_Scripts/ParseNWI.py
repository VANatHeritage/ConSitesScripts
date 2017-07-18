# -------------------------------------------------------------------------------------------------------
# ParseNWI.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2015-03-25
# Last Edit: 2016-01-26
# Creator:  Kirsten R. Hazler
#
# Summary:  Parses National Wetlands Inventory (NWI) codes into easily comprehensible fields, to facilitate
# processing and mapping.
#
# Because seriously, nobody has time to punch each one into the NWI Code Interpreter!
#
# This tool creates and populates the following new fields, based on the value in the NWI ATTRIBUTE field:
#     Syst - contains the System name; this is tier 1 in the NWI hierarchy
#     Subsyst - contains the Subsystem name; this is tier 2 in the NWI hierarchy
#     Cls1 - contains the primary (in some cases the only) Class name; this is tier 3 in the NWI hierarchy
#     Subcls1 - contains the primary (in some cases the ony) Subclass name; this is tier 4 in the NWI hierarchy
#     Cls2 - contains the secondary Class name for mixed NWI types
#     Subcls2 - contains the secondary Subclass name for mixed NWI types
#     Tidal - contains the tidal status portion of the water regime
#     WtrReg - contains the flood frequency portion of the water regime
#     Mods - contains any additional type modifiers
#     Exclude - contains the value 'X' to flag features to be excluded from rule assignment. 
              # Features are excluded if the Mods field codes for any of the following modifiers:
              #'Farmed' (f), 'Artificial' (r), 'Spoil' (s), or 'Excavated' (x)
#
# Usage:  Rather than using the original NWI feature class as the input table, it is recommended that 
# the table input to this tool be generated from the feature class by applying the "Tabulate NWI Codes"
# tool, so that there is only one record for each unique NWI code.  This will speed processing.
# The streamlined table can be joined back to the feature class using the ATTRIBUTE field.
# -------------------------------------------------------------------------------------------------------
#
# Import required modules
import arcpy # provides access to all ArcGIS geoprocessing functions
import os # provides access to operating system functionality such as file and directory paths
import traceback # used for error handling
import re # support for regular expressions.  Used extensively in this script!

# Arguments to be input by user...
Input_NWI = arcpy.GetParameterAsText(0) # NWI code table
NWI_fld = arcpy.GetParameterAsText(1) # The field containing the relevant NWI code.  
                                      # Default:  'ATTRIBUTE'

# Create new fields to hold relevant attributes
ListString = NWI_fld
arcpy.AddMessage('Adding and initializing NWI attribute fields...')
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
flds = [NWI_fld]
for Fld in FldList:
   FldName = Fld[0]
   FldLen = Fld[1]
   flds.append(FldName)
   arcpy.AddField_management (Input_NWI, FldName, 'TEXT', '', '', FldLen, '', 'NULLABLE', '', '')

# Set up some patterns to match
mix_mu = re.compile(r'/([1-7])?(RB|UB|AB|RS|US|EM|ML|SS|FO|RF|SB)?([1-7])?')
   # pattern for mixed map units
full_pat =  re.compile(r'^(M|E|R|L|P)([1-5])?(RB|UB|AB|RS|US|EM|ML|SS|FO|RF|SB)?([1-7])?([A-V])?(.*)$') 
   # full pattern after removing secondary type
ex_pat = re.compile(r'(f|r|s|x)', re.IGNORECASE)
   # pattern for final modifiers warranting exclusion from natural systems
   
# Set up subsystem dictionaries
dLac = {'1':'Limnetic', '2':'Littoral'}
dMarEst = {'1':'Subtidal', '2':'Intertidal'}
dRiv = {'1':'Tidal', 
        '2':'Lower Perennial',
        '3':'Upper Perennial',
        '4':'Intermittent',
        '5':'Unknown Perennial'}
        
# Set up system dictionary; note each system has its own subsystem dictionary
dSyst = {'M': ('Marine', dMarEst),
         'E': ('Estuarine', dMarEst),
         'R': ('Riverine', dRiv),
         'L': ('Lacustrine', dLac),
         'P': ('Palustrine', '')}

# Set up subclass dictionaries
# Because some mofo thought it was a good idea to have the same numeric values code for different things.
dRB = {'1': 'Bedrock',
       '2': 'Rubble'}
dUB = {'1': 'Cobble-Gravel',
       '2': 'Sand',
       '3': 'Mud',
       '4': 'Organic'}
dAB = {'1': 'Algal',
       '2': 'Aquatic Moss',
       '3': 'Rooted Vascular',
       '4': 'Floating Vascular'}
dRF = {'1': 'Coral',
       '2': 'Mollusk',
       '3': 'Worm'}
dRS = {'1': 'Bedrock',
       '2': 'Rubble'}
dUS = {'1': 'Cobble-Gravel',
       '2': 'Sand',
       '3': 'Mud',
       '4': 'Organic',
       '5': 'Vegetated'}
dSB = {'1': 'Bedrock',
       '2': 'Rubble',
       '3': 'Cobble-Gravel',
       '4': 'Sand',
       '5': 'Mud',
       '6': 'Organic',
       '7': 'Vegetated'}
dEM = {'1': 'Persistent',
       '2': 'Non-persistent',
       '5': 'Phragmites australis'}
dWd = {'1': 'Broad-leaved Deciduous',
       '2': 'Needle-leaved Deciduous',
       '3': 'Broad-leaved Evergreen',
       '4': 'Needle-leaved Evergreen',
       '5': 'Dead',
       '6': 'Deciduous',
       '7': 'Evergreen'}

# Set up class dictionary; note each class has its own subclass dictionary
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
dWtr = {'A': ('Nontidal', 'Temporarily Flooded'),
        'B': ('Nontidal', 'Saturated'),
        'C': ('Nontidal', 'Seasonally Flooded'), 
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
        'S': ('Freshwater Tidal', 'Temporarily Flooded - Tidal'),
        'R': ('Freshwater Tidal', 'Seasonally Flooded - Tidal'),
        'T': ('Freshwater Tidal', 'Semipermanently Flooded - Tidal'),
        'V': ('Freshwater Tidal', 'Permanently Flooded - Tidal')}
       
# Loop through the records and assign field attributes based on NWI codes
with arcpy.da.UpdateCursor(Input_NWI, flds) as cursor:
   for row in cursor:
      nwiCode = row[0] 
      arcpy.AddMessage('Code is %s' % nwiCode)
      
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




