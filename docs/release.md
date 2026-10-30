Aarhus Plotter 1.3.1

Fixes DDO 1954 previews and exports after the old metadata endpoint started returning HTTP 404. Resolves the linked WMS source through the official Datakatalog JSON:API, retaining strict provider validation and credential masking.

No job format or database schema changes. Existing jobs and tiles are preserved. Before updating TrueNAS, verify the new image separately, stop the app and back up the complete data directory. Keep the existing bind mount and port; change only the image version. Version 1.3.0 remains available for rollback.
