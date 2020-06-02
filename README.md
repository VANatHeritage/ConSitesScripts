# ConSite Toolbox
ArcGIS toolbox and associated scripts for automated delineation of Virginia Natural Heritage Conservation Sites. Additional tools for prioritization.

### Toolbox Version Notes (last updated by K. Hazler, 2020-06-02):
#### Version 1.2: Conservation Site delineation process remains unchanged from previous version. The "Essential Conservation Sites" (ECS) process has been finalized (at least for now) since the last version, when it was still in flux. Site priorities from the ECS process were first added to Biotics for the March 2020 quarterly update, and the ECS process remains stable since that time. 

#### Version 1.1: Delineation process for Terrestrial Conservation Sites and Anthropogenic Habitat Zones remains unchanged from previous version, except for a slight modification of the shrinkwrap function to correct an anomaly that can arise when the SBB is the same as the PF. In addition to that change, this version incorporates the following changes:
- Added tools for delineating Stream Conservation Units
- Added tools for processing NWI data (ported over from another old toolbox)
- Changed some toolset names
- Moved some tools from one toolset to another (without change in functionality)
- Modified some tool parameter defaults, in part to fix a bug that manifests when a layer's link to its data source is broken
- Added tool for flattening Conservation Lands (prep for Essential ConSites input)
- Added tool to dissolve procedural features to create "site-worthy" EOs
- Added tool to automate B-ranking of sites

#### Version 1.0: This was the version used for the first major overhaul/replacement of Terrestrial Conservation Sites and Anthropomorphic Habitat Zones, starting in 2018.

For more information, contact Kirsten Hazler at kirsten.hazler@dcr.virginia.gov
