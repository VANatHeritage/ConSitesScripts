# ---------------------------------------------------------------------------
# ExportBiotics.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016-09-16
# Last Edit: 2016-09-16
# Creator:  Kirsten R. Hazler
#
# Summary:
#     Exports Biotics5 query layers for Procedural Features and Conservation Sites to a file geodatabase
# ---------------------------------------------------------------------------

# Import arcpy module
import arcpy
import os # provides access to operating system funtionality 
import sys # provides access to Python system functions
import traceback # used for error handling
from datetime import datetime as dt # for timestamping

# Script arguments
BioticsPF = arcpy.GetParameterAsText(0)
BioticsCS = arcpy.GetParameterAsText(1)
outGDB = arcpy.GetParameterAsText(2)

# Local variables:
ts = dt.now().strftime("%Y%m%d_%H%M%S") # timestamp

# Process: Copy Features (ConSites)
arcpy.AddMessage('Copying ConSite features')
outCS = outGDB + os.sep + 'ConSites_' + ts
arcpy.CopyFeatures_management(BioticsCS, outCS, "", "0", "0", "0")

# Process: Copy Features (ProcFeats)
arcpy.AddMessage('Copying ProcFeats features')
unprjPF = r'in_memory\unprjProcFeats'
arcpy.CopyFeatures_management(BioticsPF, unprjPF, "", "0", "0", "0")

# Process: Project
arcpy.AddMessage('Projecting ProcFeats features')
outPF = outGDB + os.sep + 'ProcFeats_' + ts
arcpy.Project_management(unprjPF, outPF,"PROJCS['NAD_1983_Virginia_Lambert',GEOGCS['GCS_North_American_1983',DATUM['D_North_American_1983',SPHEROID['GRS_1980',6378137.0,298.257222101]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Lambert_Conformal_Conic'],PARAMETER['False_Easting',0.0],PARAMETER['False_Northing',0.0],PARAMETER['Central_Meridian',-79.5],PARAMETER['Standard_Parallel_1',37.0],PARAMETER['Standard_Parallel_2',39.5],PARAMETER['Latitude_Of_Origin',36.0],UNIT['Meter',1.0]]", "WGS_1984_(ITRF00)_To_NAD_1983", "PROJCS['WGS_1984_Web_Mercator_Auxiliary_Sphere',GEOGCS['GCS_WGS_1984',DATUM['D_WGS_1984',SPHEROID['WGS_1984',6378137.0,298.257223563]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Mercator_Auxiliary_Sphere'],PARAMETER['False_Easting',0.0],PARAMETER['False_Northing',0.0],PARAMETER['Central_Meridian',0.0],PARAMETER['Standard_Parallel_1',0.0],PARAMETER['Auxiliary_Sphere_Type',0.0],UNIT['Meter',1.0]]", "NO_PRESERVE_SHAPE", "")

mxd = arcpy.mapping.MapDocument("CURRENT")
dataFrame = arcpy.mapping.ListDataFrames(mxd, "*")[0] 
addConSites = arcpy.mapping.Layer(outCS)
arcpy.mapping.AddLayer(dataFrame, addConSites)
addProcFeats = arcpy.mapping.Layer(outPF)
arcpy.mapping.AddLayer(dataFrame, addProcFeats)

