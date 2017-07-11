import sys, arcpy
arcpy.AddMessage(sys.version)
arcpy.AddMessage(sys.executable)

defaultGDB = arcpy.env.workspace
arcpy.AddMessage("Default workspace is %s" %defaultGDB)