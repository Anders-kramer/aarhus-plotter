# Validering

## Lokalt gennemført

- 37 automatiske Python-tests og to JavaScript-tests består lokalt.
- Ugyldige indstillinger fjerner forældede estimater og holder eksport deaktiveret.
- Udsnit over én milliard pixels accepteres uden skalering (fra v1.1.0).
- Forsinkede fejlsvar kan ikke overskrive en nyere gyldig beregning.
- HTML og app-JavaScript kræver cache-genvalidering ved genindlæsning.
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

## Rammeredigering v1.0.3

Genskabt i NAS-browser: en forstørret ramme blev tidligere afvist, mens gamle mål stod tilbage. Efter opdatering vises 7,98 × 9,64 km og 1.230.317.855 pixels. Ved 0,5 meter accepteres samme ramme med 15.960 × 19.273 pixels. Eksisterende jobs er bevaret. GitHub Actions med 37 Python-tests, to JavaScript-tests og anonym containerhentning består.

## v1.1.0 – historisk baggrund og ressourceoverslag

- Live WMS-forespørgsel i EPSG:3857 giver et korrekt dekodet 512 × 512-billede.
- API-test verificerer kortkoordinaternes rundtur, login, størrelsesgrænse for oversigtsbilleder og afvisning af eksterne URL-felter.
- Lokalt browserkontrolleret: 1954-baggrund, zoom, redigering og skift til/fra moderne kort med bevaret ramme.
- En ramme på ca. 1,23 milliarder pixels accepteres og viser tid, diskreserve og faktisk fri plads. Ingen stor eksport blev startet som led i denne kontrol.
- Tidsintervallet er et planlægningsskøn med eksplicitte forudsætninger; ikke en målt garanti.

- NAS v1.1.0: healthy container, historisk kort og rammeredigering visuelt kontrolleret. Samme udsnit over én milliard pixels viser korrekt ressourceoverslag; tidligere jobs er bevaret. CI inklusive anonym GHCR-hentning består.
