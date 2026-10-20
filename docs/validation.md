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

## Afventer kontrol før endelig release

- Komplet anonym hentning og eksporttest af den endelige v1.0.1.
- TrueNAS-installation og eksport med lukket browser på NAS.

## Begrænsninger

Fuld byeksport, faktisk strømafbrydelse og alle printerdrivere er ikke testet.
Ingen billeddata fra livetest publiceres.
