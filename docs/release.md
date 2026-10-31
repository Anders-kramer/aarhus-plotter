Aarhus Plotter 1.4.0

Historical source selection with DDO 1954 retained as the default. Existing jobs, tiles and database remain compatible. GeoTIFF metadata identifies the source, period, attribution and output pixel spacing.

Lave målebordsblade requires a server-side PLOTTER_DATAFORDELER_APIKEY and successful automatic GetCapabilities and image checks in EPSG:25832 and EPSG:3857. No live authenticated Datafordeler test was possible for this release: no key is available. LW1944 and IA_1945 remain locked pending verified export rights/access. This release does not claim three new ready-to-export sources.

Tile manifests prevent cross-source/geometry reuse. Source switches invalidate preview approval, including late responses. No database schema migration. Back up the complete app dataset before updating and preserve the data bind mount. Do not interrupt active exports.
