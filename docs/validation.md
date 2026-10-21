# Validering

## Lokalt gennemført

- 36 automatiske tests består på Windows og Linux / Python 3.11.
- EPSG:4326 ↔ EPSG:25832 rundtur og Aarhus-kontrolpunkt.
- Ugyldig BBOX, tal, jobfelter, eksterne adresser og hemmeligheder afvises.
- HTTP 200 med fejl-XML, ugyldigt/tomt/ensfarvet billede, forkert størrelse,
  timeout og rate limiting.
- Syntetiske tilegrænser, GeoTIFF CRS/BBOX og A0/A1 PDF-mål og kildeangivelse.
- Annullering/genoptagelse, korrupte cachefelter, diskpladsgrænse.
- Abrupt procesafslutning under hentning og PDF-dannelse; genstart markerer
  jobbet afbrudt. Dette simulerer procesnedbrud, ikke et fysisk strømsvigt.
- Login, adgangskrav, CSRF/origin-kontrol, størrelsesgrænse, downloadbegrænsning
  og slettebekræftelse.
- JavaScript-syntaks kontrolleret.
- Browser: login, kortbaggrund, valgt ramme, koordinatindtastning og lille
  live-prøvebillede visuelt kontrolleret. Billedet viser sort-hvid bebyggelse/veje.
- Lille live-eksport på 1024 × 1024 pixels / 256 × 256 meter gennemført.
  Browserfanen blev lukket efter jobstart. Ved genåbning var jobbet færdigt.
- A0 og A1 live-PDF renderet og visuelt kontrolleret; henholdsvis 841 × 1189 og 594 × 841 mm, bevarede proportioner,
  kildeangivelse i margen. Billeddata holdes lokalt.
- Browser: tegning og flytning af ramme gennemført; 820 pixels tablet-layout
  har én kolonne og ingen vandret overflydning.
- Afhængigheder opdateret; pip-audit med alle runtime-/testafhængigheder
  fandt ingen kendte sårbarheder 20. oktober 2026.
- Linux-container bygget og kørt med UID 10001, read-only root, ingen capabilities
  og 2 GB hukommelsesgrænse. Docker-healthcheck, volume-skrivning, genstart
  og syntetisk GeoTIFF/PDF/preview-eksport består.
- GHCR v1.0.0 publiceret; anonym token- og manifesthentning gav HTTP 200.

## Release og TrueNAS – gennemført 21. oktober 2026

- v1.0.1: komplet anonym GHCR-hentning, revisionskontrol og container-eksporttest
  består i separat GitHub Actions-runner uden registry-login.
- Offentlige releasefiler hentet uden login; SHA256SUMS stemmer.
- Installeret via TrueNAS Custom App API på verificeret 26.0.0-BETA.2,
  med separat dataset, UID 10001, adgangskodefil og ledig LAN-port.
- Container-healthcheck, browserlogin og live-prøvebillede består.
- NAS-eksport af 256 × 256 meter til A1 fortsatte med lukket browserfane.
  Færdigt job bevaret efter container-genstart og nyt login.
- A0 og A1 downloadet fra NAS med login: 1024 × 1024 GeoTIFF,
  EPSG:25832, korrekt BBOX og PDF-mål 841 × 1189 / 594 × 841 mm.
- Job-API uden login afvises med HTTP 401.
- Lokale adresser, adgangskoder og billeddata er ikke publiceret.

## Begrænsninger

Fuld byeksport, faktisk strømafbrydelse og alle printerdrivere er ikke testet.
Ingen billeddata fra livetest publiceres.
